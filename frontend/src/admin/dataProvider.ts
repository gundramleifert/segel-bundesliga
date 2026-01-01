import { DataProvider, fetchUtils, Identifier, RaRecord } from 'react-admin';

const apiUrl = '/api';

// Hole OIDC-Token aus dem Storage (react-oidc-context speichert hier)
function getOidcToken(): string | null {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith('oidc.user:')) {
      try {
        const data = JSON.parse(localStorage.getItem(key) || '');
        return data.access_token || null;
      } catch {
        return null;
      }
    }
  }
  return null;
}

const httpClient = (url: string, options: fetchUtils.Options = {}) => {
  const token = getOidcToken();
  const headers = new Headers(options.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return fetchUtils.fetchJson(url, { ...options, headers });
};

/**
 * DataProvider fuer Spring Data Page API Format
 *
 * Spring Page Response: { content: [], totalElements: number, ... }
 * React-Admin erwartet: { data: [], total: number }
 */
export const dataProvider: DataProvider = {
  getList: async (resource, params) => {
    const page = params.pagination?.page ?? 1;
    const perPage = params.pagination?.perPage ?? 10;
    const field = params.sort?.field ?? 'id';
    const order = params.sort?.order ?? 'ASC';

    const queryParams: Record<string, string> = {
      page: String(page - 1), // Spring Data ist 0-basiert
      size: String(perPage),
      sort: `${field},${order.toLowerCase()}`,
    };

    // Filter hinzufuegen
    if (params.filter) {
      Object.keys(params.filter).forEach(key => {
        queryParams[key] = String(params.filter[key]);
      });
    }

    const queryString = new URLSearchParams(queryParams).toString();
    const url = `${apiUrl}/${resource}?${queryString}`;

    const { json } = await httpClient(url);

    // Spring Data Page Format -> React-Admin Format
    return {
      data: json.content.map((item: RaRecord) => ({
        ...item,
        id: item.id ?? 0,
      })),
      total: json.totalElements ?? json.content.length,
    };
  },

  getOne: async (resource, params) => {
    const { json } = await httpClient(`${apiUrl}/${resource}/${params.id}`);
    return { data: { ...json, id: json.id ?? params.id } };
  },

  getMany: async (resource, params) => {
    const responses = await Promise.all(
      params.ids.map(id => httpClient(`${apiUrl}/${resource}/${id}`))
    );
    return {
      data: responses.map(({ json }) => ({ ...json, id: json.id })),
    };
  },

  getManyReference: async (resource, params) => {
    const page = params.pagination?.page ?? 1;
    const perPage = params.pagination?.perPage ?? 10;
    const field = params.sort?.field ?? 'id';
    const order = params.sort?.order ?? 'ASC';

    const queryParams: Record<string, string> = {
      page: String(page - 1),
      size: String(perPage),
      sort: `${field},${order.toLowerCase()}`,
      [params.target]: String(params.id),
    };

    const queryString = new URLSearchParams(queryParams).toString();
    const url = `${apiUrl}/${resource}?${queryString}`;

    const { json } = await httpClient(url);

    return {
      data: json.content.map((item: RaRecord) => ({
        ...item,
        id: item.id ?? 0,
      })),
      total: json.totalElements ?? json.content.length,
    };
  },

  create: async (resource, params) => {
    const { json } = await httpClient(`${apiUrl}/${resource}`, {
      method: 'POST',
      body: JSON.stringify(params.data),
    });
    return { data: { ...json, id: json.id } };
  },

  update: async (resource, params) => {
    const { json } = await httpClient(`${apiUrl}/${resource}/${params.id}`, {
      method: 'PUT',
      body: JSON.stringify(params.data),
    });
    return { data: { ...json, id: json.id ?? params.id } };
  },

  updateMany: async (resource, params) => {
    await Promise.all(
      params.ids.map(id =>
        httpClient(`${apiUrl}/${resource}/${id}`, {
          method: 'PUT',
          body: JSON.stringify(params.data),
        })
      )
    );
    return { data: params.ids };
  },

  delete: async <RecordType extends RaRecord = RaRecord>(
    resource: string,
    params: { id: Identifier; previousData?: RecordType }
  ) => {
    await httpClient(`${apiUrl}/${resource}/${params.id}`, {
      method: 'DELETE',
    });
    return { data: { id: params.id } as RecordType };
  },

  deleteMany: async (resource, params) => {
    await Promise.all(
      params.ids.map(id =>
        httpClient(`${apiUrl}/${resource}/${id}`, {
          method: 'DELETE',
        })
      )
    );
    return { data: params.ids };
  },
};
