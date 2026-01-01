import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '@/api/client';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface PageData {
  id: number;
  title: string;
  titleEn?: string;
  slug: string;
  content: string;
  contentEn?: string;
  visibility: string;
  updatedAt: string;
}

export function PageView() {
  const { slug } = useParams<{ slug: string }>();
  const [page, setPage] = useState<PageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;

    setLoading(true);
    setError(null);

    api
      .get<PageData>(`/pages/public/${slug}`)
      .then((res) => setPage(res.data))
      .catch((err) => {
        if (err.response?.status === 404) {
          setError('Seite nicht gefunden');
        } else {
          setError('Fehler beim Laden der Seite');
        }
      })
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <Skeleton className="h-10 w-2/3 mb-4" />
        <Skeleton className="h-4 w-full mb-2" />
        <Skeleton className="h-4 w-full mb-2" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <Alert variant="destructive">
          <AlertTitle>Fehler</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <div className="mt-4">
          <Link to="/" className="text-primary hover:underline">
            Zurueck zur Startseite
          </Link>
        </div>
      </div>
    );
  }

  if (!page) return null;

  return (
    <main className="container mx-auto px-4 py-8 max-w-4xl" data-testid="page-view">
      <article>
        <header className="mb-8">
          <h1
            className="text-3xl md:text-4xl font-bold text-primary mb-2"
            data-testid="page-title"
          >
            {page.title}
          </h1>
          <p className="text-sm text-muted-foreground">
            Zuletzt aktualisiert:{' '}
            {new Date(page.updatedAt).toLocaleDateString('de-DE', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric',
            })}
          </p>
        </header>

        <div
          className="prose prose-slate max-w-none dark:prose-invert"
          data-testid="page-content"
          dangerouslySetInnerHTML={{ __html: page.content }}
        />
      </article>
    </main>
  );
}
