import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { tournamentApi, optimizationApi, setAuthToken, Tournament } from '../api/client';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

interface ProgressEvent {
  type: string;
  phase?: string;
  iteration?: number;
  bestScore?: number;
  message?: string;
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'COMPLETED':
      return <Badge className="bg-green-500 hover:bg-green-600">Abgeschlossen</Badge>;
    case 'OPTIMIZING':
      return <Badge className="bg-yellow-500 hover:bg-yellow-600">Optimierung läuft</Badge>;
    case 'READY':
      return <Badge className="bg-blue-500 hover:bg-blue-600">Bereit</Badge>;
    case 'FAILED':
      return <Badge variant="destructive">Fehlgeschlagen</Badge>;
    default:
      return <Badge variant="secondary">Entwurf</Badge>;
  }
}

export function TournamentDetail() {
  const { id } = useParams<{ id: string }>();
  const auth = useAuth();
  const navigate = useNavigate();

  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [bestScore, setBestScore] = useState<number | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (auth.user?.access_token && id) {
      setAuthToken(auth.user.access_token);
      loadTournament();
    }
    return () => {
      eventSourceRef.current?.close();
    };
  }, [auth.user?.access_token, id]);

  async function loadTournament() {
    try {
      setLoading(true);
      const response = await tournamentApi.getById(Number(id));
      setTournament(response.data);

      // Check if optimization is running
      const statusResponse = await optimizationApi.getStatus(Number(id));
      setIsRunning(statusResponse.data.isRunning);

      if (statusResponse.data.isRunning) {
        connectSSE();
      }
    } catch (err) {
      setError('Fehler beim Laden des Turniers');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function connectSSE() {
    if (!auth.user?.access_token || !id) return;

    // Close existing connection
    eventSourceRef.current?.close();

    const url = `/api/optimization/${id}/progress`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      const data: ProgressEvent = JSON.parse(event.data);
      setProgress(prev => [...prev, data]);

      if (data.phase) setCurrentPhase(data.phase);
      if (data.bestScore !== undefined) setBestScore(data.bestScore);

      if (data.type === 'completed' || data.type === 'failed') {
        setIsRunning(false);
        eventSource.close();
        loadTournament();
      }
    };

    eventSource.onerror = () => {
      console.error('SSE connection error');
      eventSource.close();
    };
  }

  async function startOptimization() {
    try {
      setProgress([]);
      setBestScore(null);
      setCurrentPhase(null);

      connectSSE();
      await optimizationApi.start(Number(id));
      setIsRunning(true);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Fehler beim Starten');
      console.error(err);
    }
  }

  async function cancelOptimization() {
    // Always stop the UI state, even if API call fails
    setIsRunning(false);
    eventSourceRef.current?.close();

    try {
      await optimizationApi.cancel(Number(id));
    } catch (err) {
      console.error('Failed to cancel optimization:', err);
      // State already updated above, so UI shows start button
    }
  }

  async function deleteTournament() {
    try {
      await tournamentApi.delete(Number(id));
      navigate('/tournaments');
    } catch (err) {
      console.error(err);
    }
  }

  async function exportPdf() {
    try {
      const response = await optimizationApi.exportPdf(Number(id));

      // Create download link
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${tournament?.name.replace(/[^a-zA-Z0-9.-]/g, '_')}_schedule.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF export failed', err);
      setError('PDF Export fehlgeschlagen');
    }
  }

  const hasRequiredConfig = tournament &&
    tournament.teams.length > 0 &&
    tournament.boats.length > 0;

  if (!auth.isAuthenticated) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Alert>
          <AlertTitle>Nicht angemeldet</AlertTitle>
          <AlertDescription>
            Bitte melde dich an, um das Turnier zu sehen.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-5xl">
        <Skeleton className="h-8 w-64 mb-2" />
        <Skeleton className="h-4 w-32 mb-8" />
        <div className="grid gap-6">
          <Skeleton className="h-32" />
          <div className="grid md:grid-cols-2 gap-4">
            <Skeleton className="h-48" />
            <Skeleton className="h-48" />
          </div>
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  if (error || !tournament) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Alert variant="destructive">
          <AlertTitle>Fehler</AlertTitle>
          <AlertDescription>{error || 'Turnier nicht gefunden'}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      {/* Header */}
      <div className="mb-8">
        <Link to="/tournaments" className="text-sm text-muted-foreground hover:text-primary flex items-center gap-1 mb-2">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Zurück zu Turnieren
        </Link>
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-3xl font-bold text-primary" data-testid="tournament-name">
                {tournament.name}
              </h1>
              {getStatusBadge(tournament.status)}
            </div>
            {(tournament.location || tournament.eventDate) && (
              <p className="text-muted-foreground flex items-center gap-4">
                {tournament.location && (
                  <span className="flex items-center gap-1">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    {tournament.location}
                  </span>
                )}
                {tournament.eventDate && (
                  <span className="flex items-center gap-1">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {new Date(tournament.eventDate).toLocaleDateString('de-DE')}
                  </span>
                )}
              </p>
            )}
          </div>
          <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="text-destructive hover:text-destructive" data-testid="tournament-delete-button">
                <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Löschen
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Turnier löschen?</DialogTitle>
                <DialogDescription>
                  Das Turnier "{tournament.name}" wird unwiderruflich gelöscht. Dieser Vorgang kann nicht rückgängig gemacht werden.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => setDeleteDialogOpen(false)} data-testid="delete-cancel-button">
                  Abbrechen
                </Button>
                <Button variant="destructive" onClick={deleteTournament} data-testid="delete-confirm-button">
                  Endgültig löschen
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Stats Overview */}
      <Card className="mb-6" data-testid="tournament-stats">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Übersicht
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="text-center" data-testid="stat-flights">
              <p className="text-3xl font-bold text-primary">{tournament.flights}</p>
              <p className="text-sm text-muted-foreground">Flights</p>
            </div>
            <div className="text-center" data-testid="stat-teams">
              <p className="text-3xl font-bold text-primary">{tournament.teams.length}</p>
              <p className="text-sm text-muted-foreground">Teams</p>
            </div>
            <div className="text-center" data-testid="stat-boats">
              <p className="text-3xl font-bold text-primary">{tournament.boats.length}</p>
              <p className="text-sm text-muted-foreground">Boote</p>
            </div>
            {tournament.schedule && (
              <div className="text-center" data-testid="stat-computation-time">
                <p className="text-3xl font-bold text-secondary">
                  {(tournament.schedule.computationTimeMs / 1000).toFixed(1)}s
                </p>
                <p className="text-sm text-muted-foreground">Rechenzeit</p>
              </div>
            )}
          </div>

          {/* Cache Indicator */}
          {tournament.schedule && tournament.schedule.computationTimeMs < 2000 && (
            <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground justify-center">
              <svg className="h-4 w-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span data-testid="cache-indicator">
                <span className="text-green-600 font-medium">Aus Cache wiederverwendet</span> - Identische Konfiguration bereits optimiert
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Teams & Boats */}
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <Card data-testid="teams-section">
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <CardTitle className="text-lg flex items-center gap-2">
                <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                Teams
              </CardTitle>
              <Badge variant="secondary">{tournament.teams.length}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {tournament.teams.length === 0 ? (
              <p className="text-muted-foreground text-sm text-center py-4">
                Keine Teams vorhanden
              </p>
            ) : (
              <ScrollArea className="h-48">
                <div className="space-y-1">
                  {tournament.teams.map((team, i) => (
                    <div
                      key={team.id}
                      className="flex items-center py-2 px-3 rounded-md hover:bg-muted/50"
                    >
                      <span className="w-6 text-muted-foreground text-sm">{i + 1}.</span>
                      <span className="font-medium">{team.name}</span>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        <Card data-testid="boats-section">
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <CardTitle className="text-lg flex items-center gap-2">
                <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6z" />
                </svg>
                Boote
              </CardTitle>
              <Badge variant="secondary">{tournament.boats.length}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {tournament.boats.length === 0 ? (
              <p className="text-muted-foreground text-sm text-center py-4">
                Keine Boote vorhanden
              </p>
            ) : (
              <ScrollArea className="h-48">
                <div className="space-y-1">
                  {tournament.boats.map((boat) => (
                    <div
                      key={boat.id}
                      className="flex items-center gap-3 py-2 px-3 rounded-md hover:bg-muted/50"
                    >
                      <div
                        className="w-4 h-4 rounded-full border-2 border-white shadow"
                        style={{ backgroundColor: boat.color || '#888' }}
                      />
                      <span className="font-medium">{boat.name}</span>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Optimization Controls */}
      <Card className="mb-6" data-testid="optimization-section">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Optimierung
          </CardTitle>
          <CardDescription>
            Starte die automatische Paarungs-Optimierung
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!hasRequiredConfig ? (
            <Alert data-testid="optimization-config-warning">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <AlertTitle>Konfiguration unvollständig</AlertTitle>
              <AlertDescription>
                <p className="text-yellow-600" data-testid="optimization-warning-text">
                  Bitte zuerst Teams und Boote hinzufügen.
                </p>
              </AlertDescription>
            </Alert>
          ) : (
            <div className="space-y-4">
              <div className="flex gap-3 flex-wrap">
                {isRunning ? (
                  <Button
                    onClick={cancelOptimization}
                    variant="destructive"
                    size="lg"
                    data-testid="optimization-cancel-button"
                  >
                    <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    Abbrechen
                  </Button>
                ) : (
                  <Button
                    onClick={startOptimization}
                    size="lg"
                    className="bg-green-600 hover:bg-green-700"
                    data-testid="optimization-start-button"
                  >
                    <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Optimierung starten
                  </Button>
                )}
                {tournament.schedule && !isRunning && (
                  <Button
                    onClick={exportPdf}
                    size="lg"
                    variant="outline"
                    className="border-blue-500 text-blue-600 hover:bg-blue-50"
                    data-testid="export-pdf-button"
                  >
                    <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                    PDF exportieren
                  </Button>
                )}
              </div>

              {/* Progress */}
              {(isRunning || progress.length > 0) && (
                <Card className="border-dashed">
                  <CardContent className="pt-4">
                    <div className="flex justify-between items-center mb-3">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{currentPhase || 'Warte...'}</Badge>
                      </div>
                      <span className="text-sm font-mono text-muted-foreground">
                        Score: {bestScore?.toFixed(2) || '-'}
                      </span>
                    </div>

                    {isRunning && (
                      <Progress
                        value={100}
                        className="h-2 mb-4 [&>div]:animate-pulse"
                        data-testid="optimization-progress-bar"
                      />
                    )}

                    <ScrollArea className="h-32 rounded-md border bg-muted/30 p-3">
                      <div className="space-y-1 font-mono text-xs">
                        {progress.slice(-15).map((p, i) => (
                          <div key={i} className="text-muted-foreground">
                            <span className="text-primary">[{p.type}]</span>{' '}
                            {p.message || p.phase || ''}
                            {p.bestScore !== undefined && (
                              <span className="text-secondary ml-1">
                                Score: {p.bestScore.toFixed(2)}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Result */}
      {tournament.resultSchedule && (
        <Card data-testid="result-section">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <svg className="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Ergebnis
            </CardTitle>
            <CardDescription>
              Optimierungsergebnis der Paarungsberechnung
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-6 mb-6">
              <Card className="bg-primary/5 border-primary/20" data-testid="result-saved-shuttles">
                <CardContent className="pt-4 text-center">
                  <p className="text-3xl font-bold text-primary">{tournament.savedShuttles || 0}</p>
                  <p className="text-sm text-muted-foreground">Gesparte Shuttles</p>
                </CardContent>
              </Card>
              <Card className="bg-secondary/5 border-secondary/20" data-testid="result-boat-changes">
                <CardContent className="pt-4 text-center">
                  <p className="text-3xl font-bold text-secondary">{tournament.boatChanges || 0}</p>
                  <p className="text-sm text-muted-foreground">Boot-Wechsel</p>
                </CardContent>
              </Card>
              <Card className="bg-muted" data-testid="result-computation-time">
                <CardContent className="pt-4 text-center">
                  <p className="text-3xl font-bold">
                    {tournament.computationTimeMs ? (tournament.computationTimeMs / 1000).toFixed(1) + 's' : '-'}
                  </p>
                  <p className="text-sm text-muted-foreground">Rechenzeit</p>
                </CardContent>
              </Card>
            </div>

            <Separator className="my-4" />

            <details className="group" data-testid="result-json-toggle">
              <summary className="cursor-pointer text-sm text-primary hover:underline flex items-center gap-2">
                <svg className="h-4 w-4 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                JSON-Ergebnis anzeigen
              </summary>
              <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-sm mt-4 font-mono" data-testid="result-json-content">
                {tournament.resultSchedule}
              </pre>
            </details>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
