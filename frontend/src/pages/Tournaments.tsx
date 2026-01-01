import { useState, useEffect } from 'react';
import { useAuth } from 'react-oidc-context';
import { Link } from 'react-router-dom';
import { tournamentApi, setAuthToken, TournamentListItem } from '../api/client';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

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

export function Tournaments() {
  const auth = useAuth();
  const [tournaments, setTournaments] = useState<TournamentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (auth.user?.access_token) {
      setAuthToken(auth.user.access_token);
      loadTournaments();
    }
  }, [auth.user?.access_token]);

  async function loadTournaments() {
    try {
      setLoading(true);
      const response = await tournamentApi.getMy();
      setTournaments(response.data.content || []);
    } catch (err) {
      setError('Fehler beim Laden der Turniere');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Alert>
          <AlertTitle>Nicht angemeldet</AlertTitle>
          <AlertDescription>
            Bitte melde dich an, um deine Turniere zu sehen.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-primary" data-testid="tournaments-title">
            Meine Turniere
          </h1>
          <p className="text-muted-foreground mt-1">
            Verwalte deine Segelregatten und starte Optimierungen
          </p>
        </div>
        <Button asChild size="lg" data-testid="tournament-create-button">
          <Link to="/tournaments/new">
            <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Neues Turnier
          </Link>
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Fehler</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : tournaments.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent>
            <svg
              className="mx-auto h-16 w-16 text-muted-foreground/50 mb-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
            <p className="text-lg font-medium text-muted-foreground mb-2">
              Noch keine Turniere vorhanden
            </p>
            <p className="text-sm text-muted-foreground mb-6">
              Erstelle dein erstes Turnier, um loszulegen.
            </p>
            <Button asChild>
              <Link to="/tournaments/new">Erstes Turnier erstellen</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {tournaments.map((t) => (
            <Link key={t.id} to={`/tournaments/${t.id}`} data-testid={`tournament-item-${t.id}`}>
              <Card className="h-full transition-all hover:shadow-lg hover:border-primary/50 cursor-pointer">
                <CardHeader className="pb-3">
                  <div className="flex justify-between items-start gap-2">
                    <CardTitle className="text-lg">{t.name}</CardTitle>
                    {getStatusBadge(t.status)}
                  </div>
                  {(t.location || t.eventDate) && (
                    <CardDescription className="flex items-center gap-2 mt-1">
                      {t.location && (
                        <span className="flex items-center gap-1">
                          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          {t.location}
                        </span>
                      )}
                      {t.eventDate && (
                        <span className="flex items-center gap-1">
                          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                          {new Date(t.eventDate).toLocaleDateString('de-DE')}
                        </span>
                      )}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  <div className="flex gap-4 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                      </svg>
                      {t.teamCount} Teams
                    </span>
                    <span className="flex items-center gap-1">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6z" />
                      </svg>
                      {t.boatCount} Boote
                    </span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
