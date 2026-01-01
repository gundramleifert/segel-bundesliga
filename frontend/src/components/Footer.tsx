import { Link } from 'react-router-dom';
import { Separator } from '@/components/ui/separator';
import { useMenuPages } from '@/hooks/useMenuPages';

export function Footer() {
  const currentYear = new Date().getFullYear();
  const { infoPages, legalPages, loading } = useMenuPages();

  // Find impressum and datenschutz pages for the copyright section
  const impressumPage = legalPages.find((p) => p.slug === 'impressum');
  const datenschutzPage = legalPages.find((p) => p.slug === 'datenschutz');

  return (
    <footer className="border-t bg-muted/30 mt-auto" data-testid="footer">
      <div className="container mx-auto px-4 py-8">
        <div className="grid gap-8 md:grid-cols-3">
          {/* Logo und Beschreibung */}
          <div>
            <Link to="/" className="flex items-center gap-2 mb-3">
              <svg
                className="h-6 w-6 text-primary"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  d="M2 20L12 4l10 16H2z"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path d="M12 4v16" strokeLinecap="round" />
              </svg>
              <span className="font-semibold text-primary">Segel-Bundesliga</span>
            </Link>
            <p className="text-sm text-muted-foreground">
              Die Plattform fuer Regatta-Optimierung und Turnierverwaltung der
              Deutschen Segel-Bundesliga.
            </p>
          </div>

          {/* Seiten-Links (INFO section) */}
          <div>
            <h3 className="font-semibold mb-3">Seiten</h3>
            <nav className="flex flex-col gap-2">
              {loading ? (
                <span className="text-sm text-muted-foreground">Laden...</span>
              ) : infoPages.length > 0 ? (
                infoPages.map((page) => (
                  <Link
                    key={page.id}
                    to={`/seite/${page.slug}`}
                    className="text-sm text-muted-foreground hover:text-primary transition-colors"
                    data-testid={`footer-${page.slug}-link`}
                  >
                    {page.title}
                  </Link>
                ))
              ) : (
                <span className="text-sm text-muted-foreground">Keine Seiten</span>
              )}
            </nav>
          </div>

          {/* Rechtliches (LEGAL section) */}
          <div>
            <h3 className="font-semibold mb-3">Rechtliches</h3>
            <nav className="flex flex-col gap-2">
              {loading ? (
                <span className="text-sm text-muted-foreground">Laden...</span>
              ) : legalPages.length > 0 ? (
                legalPages.map((page) => (
                  <Link
                    key={page.id}
                    to={`/seite/${page.slug}`}
                    className="text-sm text-muted-foreground hover:text-primary transition-colors"
                    data-testid={`footer-${page.slug}-link`}
                  >
                    {page.title}
                  </Link>
                ))
              ) : (
                <span className="text-sm text-muted-foreground">Keine Seiten</span>
              )}
            </nav>
          </div>
        </div>

        <Separator className="my-6" />

        {/* Copyright */}
        <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-muted-foreground">
          <p>&copy; {currentYear} Deutsche Segel-Bundesliga. Alle Rechte vorbehalten.</p>
          <div className="flex gap-4">
            {impressumPage && (
              <Link to={`/seite/${impressumPage.slug}`} className="hover:text-primary transition-colors">
                {impressumPage.title}
              </Link>
            )}
            {datenschutzPage && (
              <Link to={`/seite/${datenschutzPage.slug}`} className="hover:text-primary transition-colors">
                {datenschutzPage.title}
              </Link>
            )}
          </div>
        </div>
      </div>
    </footer>
  );
}
