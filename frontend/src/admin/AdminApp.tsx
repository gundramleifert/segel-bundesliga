import {
  Admin,
  Resource,
  List,
  Datagrid,
  TextField,
  BooleanField,
  NumberField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  BooleanInput,
  NumberInput,
  SelectInput,
  EditButton,
  DeleteButton,
  required,
  useRecordContext,
  AuthProvider,
} from 'react-admin';
// Auth wird ueber den OIDC-Token im localStorage gehandhabt
import { dataProvider } from './dataProvider';

// Hole OIDC-Token aus dem Storage (react-oidc-context speichert hier)
function getOidcToken(): string | null {
  // react-oidc-context speichert im localStorage unter einem key wie:
  // oidc.user:{authority}:{client_id}
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

function getOidcUser(): { id: string; fullName: string } | null {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith('oidc.user:')) {
      try {
        const data = JSON.parse(localStorage.getItem(key) || '');
        return {
          id: data.profile?.sub || 'user',
          fullName: data.profile?.name || data.profile?.email || 'Admin',
        };
      } catch {
        return null;
      }
    }
  }
  return null;
}

// Auth Provider fuer Zitadel OIDC
const authProvider: AuthProvider = {
  login: () => {
    // Redirect zum Haupt-Login - wird von der Haupt-App gehandhabt
    window.location.href = '/';
    return Promise.resolve();
  },
  logout: () => {
    // Logout wird von der Haupt-App gehandhabt
    window.location.href = '/';
    return Promise.resolve();
  },
  checkAuth: () => {
    const token = getOidcToken();
    return token ? Promise.resolve() : Promise.reject();
  },
  checkError: (error: { status?: number }) => {
    if (error.status === 401 || error.status === 403) {
      return Promise.reject();
    }
    return Promise.resolve();
  },
  getPermissions: () => Promise.resolve(),
  getIdentity: () => {
    const user = getOidcUser();
    return user ? Promise.resolve(user) : Promise.reject();
  },
};

// Visibility Optionen
const visibilityChoices = [
  { id: 'PUBLIC', name: 'Oeffentlich' },
  { id: 'INTERNAL', name: 'Intern' },
];

// Page List
const PageList = () => (
  <List sort={{ field: 'sortOrder', order: 'ASC' }}>
    <Datagrid>
      <TextField source="id" />
      <TextField source="title" label="Titel" />
      <TextField source="slug" />
      <TextField source="visibility" label="Sichtbarkeit" />
      <BooleanField source="showInMenu" label="Im Menu" />
      <NumberField source="sortOrder" label="Sortierung" />
      <EditButton />
      <DeleteButton />
    </Datagrid>
  </List>
);

// Page Title fuer Edit-Ansicht
const PageTitle = () => {
  const record = useRecordContext();
  return <span>Seite: {record ? `"${record.title}"` : ''}</span>;
};

// Page Edit Form
const PageEdit = () => (
  <Edit title={<PageTitle />}>
    <SimpleForm>
      <TextInput source="title" label="Titel (DE)" validate={required()} fullWidth />
      <TextInput source="titleEn" label="Titel (EN)" fullWidth />
      <TextInput source="slug" label="Slug (URL)" validate={required()} fullWidth />
      <TextInput
        source="content"
        label="Inhalt (DE)"
        multiline
        rows={10}
        validate={required()}
        fullWidth
      />
      <TextInput
        source="contentEn"
        label="Inhalt (EN)"
        multiline
        rows={10}
        fullWidth
      />
      <SelectInput
        source="visibility"
        label="Sichtbarkeit"
        choices={visibilityChoices}
        defaultValue="PUBLIC"
      />
      <BooleanInput source="showInMenu" label="Im Menu anzeigen" />
      <NumberInput source="sortOrder" label="Sortierung" defaultValue={0} />
    </SimpleForm>
  </Edit>
);

// Page Create Form
const PageCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="title" label="Titel (DE)" validate={required()} fullWidth />
      <TextInput source="titleEn" label="Titel (EN)" fullWidth />
      <TextInput source="slug" label="Slug (URL)" validate={required()} fullWidth />
      <TextInput
        source="content"
        label="Inhalt (DE)"
        multiline
        rows={10}
        validate={required()}
        fullWidth
      />
      <TextInput
        source="contentEn"
        label="Inhalt (EN)"
        multiline
        rows={10}
        fullWidth
      />
      <SelectInput
        source="visibility"
        label="Sichtbarkeit"
        choices={visibilityChoices}
        defaultValue="PUBLIC"
      />
      <BooleanInput source="showInMenu" label="Im Menu anzeigen" defaultValue={false} />
      <NumberInput source="sortOrder" label="Sortierung" defaultValue={0} />
    </SimpleForm>
  </Create>
);

// Admin App
export function AdminApp() {
  return (
    <Admin dataProvider={dataProvider} authProvider={authProvider} basename="/admin">
      <Resource
        name="pages"
        list={PageList}
        edit={PageEdit}
        create={PageCreate}
        options={{ label: 'Seiten' }}
      />
    </Admin>
  );
}
