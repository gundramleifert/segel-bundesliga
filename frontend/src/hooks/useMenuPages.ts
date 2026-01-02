import { useState, useEffect } from 'react';
import { useAuth } from 'react-oidc-context';
import { api } from '@/api/client';

export interface MenuPage {
  id: number;
  title: string;
  titleEn?: string;
  slug: string;
  visibility: string;
  sortOrder: number;
  showInMenu: boolean;
  parentId?: number;
  footerSection?: 'INFO' | 'LEGAL' | null;
}

export function useMenuPages() {
  const auth = useAuth();
  const [pages, setPages] = useState<MenuPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Re-fetch when auth state changes (to show/hide INTERNAL pages)
  useEffect(() => {
    setLoading(true);
    api
      .get<MenuPage[]>('/pages/menu')
      .then((res) => setPages(res.data))
      .catch(() => setError('Fehler beim Laden der Seiten'))
      .finally(() => setLoading(false));
  }, [auth.isAuthenticated]);

  // Group pages by footer section
  const infoPages = pages.filter((p) => p.footerSection === 'INFO');
  const legalPages = pages.filter((p) => p.footerSection === 'LEGAL');
  const otherPages = pages.filter((p) => !p.footerSection);

  return {
    pages,
    infoPages,
    legalPages,
    otherPages,
    loading,
    error,
  };
}
