import { Routes, Route, Link } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { Callback } from './auth/Callback';
import { Tournaments } from './pages/Tournaments';
import { TournamentDetail } from './pages/TournamentDetail';
import { TournamentCreate } from './pages/TournamentCreate';
import { PageView } from './pages/PageView';
import { AdminApp } from './admin/AdminApp';
import { Footer } from './components/Footer';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Toaster } from '@/components/ui/toaster';

function Header() {
  const auth = useAuth();

  const getInitials = (name?: string, email?: string) => {
    if (name) {
      return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    }
    if (email) {
      return email[0].toUpperCase();
    }
    return 'U';
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-primary text-primary-foreground shadow-lg">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <div className="flex items-center gap-8">
          <Link to="/" className="flex items-center gap-2" data-testid="app-title">
            <svg className="h-8 w-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M2 20L12 4l10 16H2z" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M12 4v16" strokeLinecap="round"/>
            </svg>
            <span className="text-xl font-bold tracking-tight">Segel-Bundesliga</span>
          </Link>
          {auth.isAuthenticated && (
            <nav className="hidden md:flex items-center gap-6">
              <Link
                to="/tournaments"
                className="text-sm font-medium transition-colors hover:text-secondary"
              >
                Turniere
              </Link>
            </nav>
          )}
        </div>

        <nav className="flex items-center gap-4">
          {auth.isLoading ? (
            <div className="h-8 w-8 animate-pulse rounded-full bg-primary-foreground/20" />
          ) : auth.isAuthenticated ? (
            <div className="flex items-center gap-3">
              {/* Visible user name for tests and UX */}
              <span className="hidden md:block text-sm font-medium" data-testid="user-name">
                {auth.user?.profile.name || 'Benutzer'}
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="relative h-10 w-10 rounded-full" data-testid="user-menu-button">
                    <Avatar className="h-10 w-10 border-2 border-secondary">
                      <AvatarFallback className="bg-secondary text-secondary-foreground font-semibold">
                        {getInitials(auth.user?.profile.name, auth.user?.profile.email)}
                      </AvatarFallback>
                    </Avatar>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56" align="end" forceMount>
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col space-y-1">
                      <p className="text-sm font-medium leading-none">
                        {auth.user?.profile.name || 'Benutzer'}
                      </p>
                      <p className="text-xs leading-none text-muted-foreground">
                        {auth.user?.profile.email}
                      </p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link to="/tournaments">Meine Turniere</Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => auth.signoutRedirect()}
                    className="text-destructive focus:text-destructive"
                    data-testid="logout-button"
                  >
                    Abmelden
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ) : (
            <Button
              onClick={() => auth.signinRedirect()}
              variant="secondary"
              data-testid="login-button"
            >
              Anmelden
            </Button>
          )}
        </nav>
      </div>
    </header>
  );
}

function Home() {
  const auth = useAuth();

  return (
    <main className="container mx-auto px-4 py-12">
      {/* Hero Section */}
      <div className="text-center mb-12" data-testid="welcome-message">
        <h1 className="text-4xl md:text-5xl font-bold text-primary mb-4">
          Willkommen zur Segel-Bundesliga
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Die Plattform für Regatta-Optimierung und Turnierverwaltung
        </p>
      </div>

      {/* Feature Cards */}
      <div className="grid md:grid-cols-3 gap-6 mb-12">
        <Card className="border-t-4 border-t-primary">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Turnierverwaltung
            </CardTitle>
            <CardDescription>
              Erstelle und verwalte deine Segelregatten
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Teams, Boote und Flights konfigurieren - alles an einem Ort.
            </p>
          </CardContent>
        </Card>

        <Card className="border-t-4 border-t-secondary">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <svg className="h-5 w-5 text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Automatische Optimierung
            </CardTitle>
            <CardDescription>
              Intelligente Paarungsberechnung
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Minimiere Bootswechsel und Shuttle-Fahrten automatisch.
            </p>
          </CardContent>
        </Card>

        <Card className="border-t-4 border-t-accent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <svg className="h-5 w-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Echtzeit-Fortschritt
            </CardTitle>
            <CardDescription>
              Live-Updates während der Berechnung
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Verfolge den Optimierungsfortschritt in Echtzeit.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* CTA Section */}
      {auth.isAuthenticated ? (
        <Card className="bg-primary text-primary-foreground" data-testid="auth-info">
          <CardContent className="flex flex-col md:flex-row items-center justify-between gap-4 pt-6">
            <div>
              <p className="font-semibold text-lg">Angemeldet als {auth.user?.profile.email}</p>
              <p className="text-primary-foreground/80">Bereit, ein neues Turnier zu erstellen?</p>
            </div>
            <Button asChild variant="secondary" size="lg">
              <Link to="/tournaments">Zu meinen Turnieren</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-gradient-to-r from-primary to-secondary text-white">
          <CardContent className="flex flex-col md:flex-row items-center justify-between gap-4 pt-6">
            <div>
              <p className="font-semibold text-lg">Jetzt loslegen</p>
              <p className="text-white/80">Melde dich an, um deine Turniere zu verwalten.</p>
            </div>
            <Button
              onClick={() => auth.signinRedirect()}
              variant="outline"
              size="lg"
              className="bg-white text-primary hover:bg-white/90"
            >
              Kostenlos anmelden
            </Button>
          </CardContent>
        </Card>
      )}
    </main>
  );
}

function App() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <div className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/callback" element={<Callback />} />
          <Route path="/tournaments" element={<Tournaments />} />
          <Route path="/tournaments/new" element={<TournamentCreate />} />
          <Route path="/tournaments/:id" element={<TournamentDetail />} />
          <Route path="/seite/:slug" element={<PageView />} />
          <Route path="/admin/*" element={<AdminApp />} />
        </Routes>
      </div>
      <Footer />
      <Toaster />
    </div>
  );
}

export default App;
