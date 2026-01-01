import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { tournamentApi, setAuthToken, TeamInput, BoatInput } from '../api/client';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

export function TournamentCreate() {
  const auth = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');
  const [eventDate, setEventDate] = useState('');
  const [flights, setFlights] = useState(3);

  const [teams, setTeams] = useState<TeamInput[]>([]);
  const [newTeamName, setNewTeamName] = useState('');

  const [boats, setBoats] = useState<BoatInput[]>([]);
  const [newBoatName, setNewBoatName] = useState('');
  const [newBoatColor, setNewBoatColor] = useState('#009bd9');

  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function addTeam() {
    if (!newTeamName.trim()) return;
    setTeams([...teams, { name: newTeamName.trim() }]);
    setNewTeamName('');
  }

  function removeTeam(index: number) {
    setTeams(teams.filter((_, i) => i !== index));
  }

  function addBoat() {
    if (!newBoatName.trim()) return;
    setBoats([...boats, { name: newBoatName.trim(), color: newBoatColor }]);
    setNewBoatName('');
  }

  function removeBoat(index: number) {
    setBoats(boats.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!auth.user?.access_token) return;

    setAuthToken(auth.user.access_token);
    setSaving(true);
    setError(null);

    try {
      const response = await tournamentApi.create({
        name,
        description: description || undefined,
        location: location || undefined,
        eventDate: eventDate || undefined,
        flights,
        teams: teams.length > 0 ? teams : undefined,
        boats: boats.length > 0 ? boats : undefined,
      });
      navigate(`/tournaments/${response.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Alert>
          <AlertTitle>Nicht angemeldet</AlertTitle>
          <AlertDescription>
            Bitte melde dich an, um ein Turnier zu erstellen.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      {/* Header */}
      <div className="mb-8">
        <Link to="/tournaments" className="text-sm text-muted-foreground hover:text-primary flex items-center gap-1 mb-2">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Zurück zu Turnieren
        </Link>
        <h1 className="text-3xl font-bold text-primary">Neues Turnier erstellen</h1>
        <p className="text-muted-foreground mt-1">Konfiguriere die Grunddaten, Teams und Boote</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Grunddaten
            </CardTitle>
            <CardDescription>Allgemeine Informationen zum Turnier</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name *</Label>
              <Input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="z.B. Bundesliga Spieltag 1"
                data-testid="tournament-name-input"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Beschreibung</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optionale Beschreibung des Turniers..."
                rows={2}
                data-testid="tournament-description-input"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="location">Ort</Label>
                <Input
                  id="location"
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="z.B. Kiel"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="eventDate">Datum</Label>
                <Input
                  id="eventDate"
                  type="date"
                  value={eventDate}
                  onChange={(e) => setEventDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="flights">Flights</Label>
                <Input
                  id="flights"
                  type="number"
                  min={1}
                  max={10}
                  value={flights}
                  onChange={(e) => setFlights(parseInt(e.target.value) || 3)}
                  data-testid="tournament-flights-input"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Teams */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                  Teams
                </CardTitle>
                <CardDescription>Teilnehmende Mannschaften</CardDescription>
              </div>
              <Badge variant="secondary" className="text-lg px-3">
                {teams.length}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                type="text"
                value={newTeamName}
                onChange={(e) => setNewTeamName(e.target.value)}
                placeholder="Team-Name eingeben"
                className="flex-1"
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTeam())}
                data-testid="team-name-input"
              />
              <Button
                type="button"
                onClick={addTeam}
                disabled={!newTeamName.trim()}
                data-testid="team-add-button"
              >
                <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Hinzufügen
              </Button>
            </div>

            {teams.length > 0 && (
              <div className="space-y-2" data-testid="teams-list">
                {teams.map((team, i) => (
                  <div
                    key={i}
                    className="flex justify-between items-center bg-muted/50 px-4 py-2.5 rounded-lg border"
                    data-testid={`team-item-${i}`}
                  >
                    <span className="font-medium" data-testid={`team-name-${i}`}>
                      <span className="text-muted-foreground mr-2">{i + 1}.</span>
                      {team.name}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removeTeam(i)}
                      className="text-destructive hover:text-destructive hover:bg-destructive/10"
                      data-testid={`team-remove-${i}`}
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </Button>
                  </div>
                ))}
              </div>
            )}

            {teams.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                Noch keine Teams hinzugefügt. Gib oben einen Team-Namen ein.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Boats */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6z" />
                  </svg>
                  Boote
                </CardTitle>
                <CardDescription>Verfügbare Boote für die Regatta</CardDescription>
              </div>
              <Badge variant="secondary" className="text-lg px-3">
                {boats.length}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                type="text"
                value={newBoatName}
                onChange={(e) => setNewBoatName(e.target.value)}
                placeholder="Boot-Name eingeben"
                className="flex-1"
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addBoat())}
                data-testid="boat-name-input"
              />
              <Input
                type="color"
                value={newBoatColor}
                onChange={(e) => setNewBoatColor(e.target.value)}
                className="w-14 h-10 p-1 cursor-pointer"
              />
              <Button
                type="button"
                onClick={addBoat}
                disabled={!newBoatName.trim()}
                data-testid="boat-add-button"
              >
                <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Hinzufügen
              </Button>
            </div>

            {boats.length > 0 && (
              <div className="space-y-2" data-testid="boats-list">
                {boats.map((boat, i) => (
                  <div
                    key={i}
                    className="flex justify-between items-center bg-muted/50 px-4 py-2.5 rounded-lg border"
                    data-testid={`boat-item-${i}`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className="w-5 h-5 rounded-full border-2 border-white shadow"
                        style={{ backgroundColor: boat.color }}
                      />
                      <span className="font-medium" data-testid={`boat-name-${i}`}>{boat.name}</span>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removeBoat(i)}
                      className="text-destructive hover:text-destructive hover:bg-destructive/10"
                      data-testid={`boat-remove-${i}`}
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </Button>
                  </div>
                ))}
              </div>
            )}

            {boats.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                Noch keine Boote hinzugefügt. Gib oben einen Boot-Namen ein.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Error */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Fehler</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <Button
            type="submit"
            disabled={saving || !name}
            size="lg"
            data-testid="tournament-save-button"
          >
            {saving ? (
              <>
                <svg className="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Speichern...
              </>
            ) : (
              <>
                <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Turnier erstellen
              </>
            )}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => navigate('/tournaments')}
          >
            Abbrechen
          </Button>
        </div>
      </form>
    </div>
  );
}
