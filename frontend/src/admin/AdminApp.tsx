import {
  Admin,
  Resource,
  List,
  Datagrid,
  TextField,
  BooleanField,
  NumberField,
  DateField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  BooleanInput,
  NumberInput,
  SelectInput,
  ArrayInput,
  SimpleFormIterator,
  EditButton,
  DeleteButton,
  required,
  useRecordContext,
  AuthProvider,
  FunctionField,
  Toolbar,
  SaveButton,
  useDelete,
  useRefresh,
  useNotify,
} from 'react-admin';
import { useState } from 'react';
import {
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
// Auth wird ueber den OIDC-Token im localStorage gehandhabt
import { dataProvider } from './dataProvider';
import { RichTextInput } from './components/RichTextInput';

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

// Post Status Optionen
const postStatusChoices = [
  { id: 'DRAFT', name: 'Entwurf' },
  { id: 'PUBLISHED', name: 'Veroeffentlicht' },
  { id: 'ARCHIVED', name: 'Archiviert' },
];

// Footer Section Optionen
const footerSectionChoices = [
  { id: '', name: '(Keine)' },
  { id: 'INFO', name: 'Info-Bereich' },
  { id: 'LEGAL', name: 'Rechtliches' },
];

// Custom Toolbar mit data-testid fuer E2E Tests
const PageFormToolbar = () => (
  <Toolbar>
    <SaveButton data-testid="admin-page-save-button" />
  </Toolbar>
);

// Custom Delete Button mit MUI Dialog fuer data-testid Support
const PageDeleteButton = () => {
  const record = useRecordContext();
  const [open, setOpen] = useState(false);
  const [deleteOne, { isPending }] = useDelete();
  const refresh = useRefresh();
  const notify = useNotify();

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent row click
    setOpen(true);
  };
  const handleDialogClose = () => setOpen(false);

  const handleConfirm = () => {
    deleteOne(
      'pages',
      { id: record?.id, previousData: record },
      {
        onSuccess: () => {
          notify('Element deleted', { type: 'info' });
          refresh();
        },
        onError: () => {
          notify('Error deleting element', { type: 'error' });
        },
      }
    );
    setOpen(false);
  };

  return (
    <>
      <Button
        onClick={handleClick}
        color="error"
        size="small"
        startIcon={<DeleteIcon />}
        data-testid="admin-page-delete-button"
        disabled={isPending}
      >
        Delete
      </Button>
      <Dialog open={open} onClose={handleDialogClose}>
        <DialogTitle>Delete Page</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this page?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDialogClose} data-testid="admin-cancel-delete-button">
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            color="error"
            autoFocus
            data-testid="admin-confirm-delete-button"
          >
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

// Page List
const PageList = () => (
  <List
    sort={{ field: 'sortOrder', order: 'ASC' }}
    queryOptions={{ refetchOnMount: 'always', staleTime: 0 }}
  >
    <Datagrid>
      <TextField source="id" />
      <TextField source="title" label="Titel" />
      <TextField source="slug" />
      <TextField source="visibility" label="Sichtbarkeit" />
      <BooleanField source="showInMenu" label="Im Menu" />
      <NumberField source="sortOrder" label="Sortierung" />
      <EditButton />
      <PageDeleteButton />
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
  <Edit title={<PageTitle />} mutationMode="pessimistic">
    <SimpleForm toolbar={<PageFormToolbar />}>
      <TextInput source="title" label="Titel (DE)" validate={required()} fullWidth inputProps={{ 'data-testid': 'admin-page-title-input' }} />
      <TextInput source="titleEn" label="Titel (EN)" fullWidth inputProps={{ 'data-testid': 'admin-page-title-en-input' }} />
      <TextInput source="slug" label="Slug (URL)" validate={required()} fullWidth inputProps={{ 'data-testid': 'admin-page-slug-input' }} />
      <RichTextInput
        source="content"
        label="Inhalt (DE)"
        validate={required()}
        data-testid="admin-page-content-input"
      />
      <RichTextInput
        source="contentEn"
        label="Inhalt (EN)"
        data-testid="admin-page-content-en-input"
      />
      <SelectInput
        source="visibility"
        label="Sichtbarkeit"
        choices={visibilityChoices}
        defaultValue="PUBLIC"
      />
      <SelectInput
        source="footerSection"
        label="Footer-Bereich"
        choices={footerSectionChoices}
        emptyText="(Keine)"
      />
      <BooleanInput source="showInMenu" label="Im Menu anzeigen" />
      <NumberInput source="sortOrder" label="Sortierung" defaultValue={0} inputProps={{ 'data-testid': 'admin-page-sort-input' }} />
    </SimpleForm>
  </Edit>
);

// Page Create Form
const PageCreate = () => (
  <Create>
    <SimpleForm toolbar={<PageFormToolbar />}>
      <TextInput source="title" label="Titel (DE)" validate={required()} fullWidth inputProps={{ 'data-testid': 'admin-page-title-input' }} />
      <TextInput source="titleEn" label="Titel (EN)" fullWidth inputProps={{ 'data-testid': 'admin-page-title-en-input' }} />
      <TextInput source="slug" label="Slug (URL)" validate={required()} fullWidth inputProps={{ 'data-testid': 'admin-page-slug-input' }} />
      <RichTextInput
        source="content"
        label="Inhalt (DE)"
        validate={required()}
        data-testid="admin-page-content-input"
      />
      <RichTextInput
        source="contentEn"
        label="Inhalt (EN)"
        data-testid="admin-page-content-en-input"
      />
      <SelectInput
        source="visibility"
        label="Sichtbarkeit"
        choices={visibilityChoices}
        defaultValue="PUBLIC"
      />
      <SelectInput
        source="footerSection"
        label="Footer-Bereich"
        choices={footerSectionChoices}
        emptyText="(Keine)"
      />
      <BooleanInput source="showInMenu" label="Im Menu anzeigen" defaultValue={false} />
      <NumberInput source="sortOrder" label="Sortierung" defaultValue={0} inputProps={{ 'data-testid': 'admin-page-sort-input' }} />
    </SimpleForm>
  </Create>
);

// ============================================================
// POST Resource
// ============================================================

// Post List
const PostList = () => (
  <List
    sort={{ field: 'createdAt', order: 'DESC' }}
    queryOptions={{ refetchOnMount: 'always', staleTime: 0 }}
  >
    <Datagrid>
      <TextField source="id" />
      <TextField source="title" label="Titel" />
      <TextField source="slug" />
      <FunctionField
        label="Status"
        render={(record: { status?: string }) => {
          const status = record?.status;
          const colors: Record<string, string> = {
            DRAFT: '#f59e0b',
            PUBLISHED: '#10b981',
            ARCHIVED: '#6b7280',
          };
          return (
            <span style={{ color: colors[status || ''] || '#000' }}>
              {postStatusChoices.find((c) => c.id === status)?.name || status}
            </span>
          );
        }}
      />
      <TextField source="visibility" label="Sichtbarkeit" />
      <DateField source="publishedAt" label="Veroeffentlicht" showTime />
      <EditButton />
      <DeleteButton />
    </Datagrid>
  </List>
);

// Post Title fuer Edit-Ansicht
const PostTitle = () => {
  const record = useRecordContext();
  return <span>Beitrag: {record ? `"${record.title}"` : ''}</span>;
};

// Post Edit Form
const PostEdit = () => (
  <Edit title={<PostTitle />}>
    <SimpleForm>
      <TextInput source="title" label="Titel (DE)" validate={required()} fullWidth />
      <TextInput source="titleEn" label="Titel (EN)" fullWidth />
      <TextInput source="slug" label="Slug (URL)" validate={required()} fullWidth />
      <TextInput source="excerpt" label="Auszug (DE)" multiline rows={3} fullWidth />
      <TextInput source="excerptEn" label="Auszug (EN)" multiline rows={3} fullWidth />
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
      <TextInput source="featuredImage" label="Titelbild (Bild-ID)" fullWidth />
      <SelectInput
        source="status"
        label="Status"
        choices={postStatusChoices}
      />
      <SelectInput
        source="visibility"
        label="Sichtbarkeit"
        choices={visibilityChoices}
      />
      <ArrayInput source="tags" label="Tags">
        <SimpleFormIterator inline>
          <TextInput source="" label="" helperText={false} />
        </SimpleFormIterator>
      </ArrayInput>
    </SimpleForm>
  </Edit>
);

// Post Create Form
const PostCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="title" label="Titel (DE)" validate={required()} fullWidth />
      <TextInput source="titleEn" label="Titel (EN)" fullWidth />
      <TextInput source="slug" label="Slug (URL)" validate={required()} fullWidth />
      <TextInput source="excerpt" label="Auszug (DE)" multiline rows={3} fullWidth />
      <TextInput source="excerptEn" label="Auszug (EN)" multiline rows={3} fullWidth />
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
      <TextInput source="featuredImage" label="Titelbild (Bild-ID)" fullWidth />
      <SelectInput
        source="visibility"
        label="Sichtbarkeit"
        choices={visibilityChoices}
        defaultValue="PUBLIC"
      />
      <ArrayInput source="tags" label="Tags">
        <SimpleFormIterator inline>
          <TextInput source="" label="" helperText={false} />
        </SimpleFormIterator>
      </ArrayInput>
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
      <Resource
        name="posts"
        list={PostList}
        edit={PostEdit}
        create={PostCreate}
        options={{ label: 'Beitraege' }}
      />
    </Admin>
  );
}
