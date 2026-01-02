import { useInput, InputProps } from 'react-admin';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Image from '@tiptap/extension-image';
import Link from '@tiptap/extension-link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { InputLabel, FormControl, FormHelperText } from '@mui/material';

interface ImageUploadConfig {
  maxFileSize: number;
  maxWidth: number;
  maxHeight: number;
  allowedContentTypes: string[];
  allowedExtensions: string[];
}

interface RichTextInputProps extends Omit<InputProps, 'source'> {
  source: string;
  label?: string;
  'data-testid'?: string;
}

// Toolbar Component
function EditorToolbar({
  editor,
  onImageUpload,
}: {
  editor: ReturnType<typeof useEditor>;
  onImageUpload: () => void;
}) {
  if (!editor) return null;

  const buttonStyle = (isActive: boolean) => ({
    padding: '4px 8px',
    margin: '2px',
    border: '1px solid #ccc',
    borderRadius: '4px',
    background: isActive ? '#e0e0e0' : '#fff',
    cursor: 'pointer',
    fontSize: '14px',
  });

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '2px',
        padding: '8px',
        borderBottom: '1px solid #ccc',
        background: '#f5f5f5',
      }}
    >
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleBold().run()}
        style={buttonStyle(editor.isActive('bold'))}
        title="Fett"
      >
        <strong>B</strong>
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleItalic().run()}
        style={buttonStyle(editor.isActive('italic'))}
        title="Kursiv"
      >
        <em>I</em>
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleStrike().run()}
        style={buttonStyle(editor.isActive('strike'))}
        title="Durchgestrichen"
      >
        <s>S</s>
      </button>
      <span style={{ width: '1px', background: '#ccc', margin: '0 4px' }} />
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        style={buttonStyle(editor.isActive('heading', { level: 1 }))}
        title="Ueberschrift 1"
      >
        H1
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        style={buttonStyle(editor.isActive('heading', { level: 2 }))}
        title="Ueberschrift 2"
      >
        H2
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        style={buttonStyle(editor.isActive('heading', { level: 3 }))}
        title="Ueberschrift 3"
      >
        H3
      </button>
      <span style={{ width: '1px', background: '#ccc', margin: '0 4px' }} />
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        style={buttonStyle(editor.isActive('bulletList'))}
        title="Aufzaehlung"
      >
        &bull; Liste
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        style={buttonStyle(editor.isActive('orderedList'))}
        title="Nummerierung"
      >
        1. Liste
      </button>
      <span style={{ width: '1px', background: '#ccc', margin: '0 4px' }} />
      <button
        type="button"
        onClick={() => {
          const url = window.prompt('Link URL:');
          if (url) {
            editor.chain().focus().setLink({ href: url }).run();
          }
        }}
        style={buttonStyle(editor.isActive('link'))}
        title="Link einfuegen"
      >
        Link
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().unsetLink().run()}
        style={buttonStyle(false)}
        disabled={!editor.isActive('link')}
        title="Link entfernen"
      >
        Unlink
      </button>
      <button
        type="button"
        onClick={onImageUpload}
        style={buttonStyle(false)}
        title="Bild hochladen"
      >
        Bild
      </button>
      <span style={{ width: '1px', background: '#ccc', margin: '0 4px' }} />
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        style={buttonStyle(editor.isActive('blockquote'))}
        title="Zitat"
      >
        Zitat
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
        style={buttonStyle(editor.isActive('codeBlock'))}
        title="Code-Block"
      >
        Code
      </button>
      <span style={{ width: '1px', background: '#ccc', margin: '0 4px' }} />
      <button
        type="button"
        onClick={() => editor.chain().focus().undo().run()}
        style={buttonStyle(false)}
        disabled={!editor.can().undo()}
        title="Rueckgaengig"
      >
        Undo
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().redo().run()}
        style={buttonStyle(false)}
        disabled={!editor.can().redo()}
        title="Wiederholen"
      >
        Redo
      </button>
    </div>
  );
}

// Get OIDC token for API calls
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

// Default config (fallback if API fails)
const DEFAULT_CONFIG: ImageUploadConfig = {
  maxFileSize: 2 * 1024 * 1024,
  maxWidth: 1920,
  maxHeight: 1080,
  allowedContentTypes: ['image/jpeg', 'image/png'],
  allowedExtensions: ['.jpg', '.jpeg', '.png'],
};

export function RichTextInput({ source, label, 'data-testid': testId, ...props }: RichTextInputProps) {
  const {
    field,
    fieldState: { error },
  } = useInput({ source, ...props });

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadConfig, setUploadConfig] = useState<ImageUploadConfig>(DEFAULT_CONFIG);

  // Fetch upload config from backend
  useEffect(() => {
    fetch('/api/storage/config')
      .then((res) => res.json())
      .then((config) => setUploadConfig(config))
      .catch(() => console.warn('Failed to load upload config, using defaults'));
  }, []);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Image.configure({
        HTMLAttributes: {
          class: 'rich-text-image',
        },
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'rich-text-link',
        },
      }),
    ],
    content: field.value || '',
    onUpdate: ({ editor }) => {
      field.onChange(editor.getHTML());
    },
  });

  // Sync field value with editor when it changes externally
  useEffect(() => {
    if (editor && field.value !== editor.getHTML()) {
      editor.commands.setContent(field.value || '');
    }
  }, [field.value, editor]);

  const handleImageUpload = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file || !editor) return;

      // Check file type
      if (!uploadConfig.allowedContentTypes.includes(file.type)) {
        alert(`Nur ${uploadConfig.allowedExtensions.join(', ')} Bilder sind erlaubt.`);
        e.target.value = '';
        return;
      }

      // Check file size
      if (file.size > uploadConfig.maxFileSize) {
        const maxMB = Math.round(uploadConfig.maxFileSize / (1024 * 1024));
        alert(`Maximale Dateigröße ist ${maxMB} MB.`);
        e.target.value = '';
        return;
      }

      // Check image dimensions
      const img = new window.Image();
      const objectUrl = URL.createObjectURL(file);

      const dimensionCheck = new Promise<boolean>((resolve) => {
        img.onload = () => {
          URL.revokeObjectURL(objectUrl);
          if (img.width > uploadConfig.maxWidth || img.height > uploadConfig.maxHeight) {
            alert(`Maximale Bildgröße ist ${uploadConfig.maxWidth}x${uploadConfig.maxHeight} Pixel (hochgeladen: ${img.width}x${img.height}).`);
            resolve(false);
          } else {
            resolve(true);
          }
        };
        img.onerror = () => {
          URL.revokeObjectURL(objectUrl);
          alert('Bild konnte nicht gelesen werden.');
          resolve(false);
        };
        img.src = objectUrl;
      });

      if (!(await dimensionCheck)) {
        e.target.value = '';
        return;
      }

      const token = getOidcToken();
      if (!token) {
        alert('Nicht angemeldet. Bitte erneut einloggen.');
        return;
      }

      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await fetch('/api/storage/upload', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.message || 'Upload fehlgeschlagen');
        }

        const data = await response.json();
        // Use proxy URL instead of presigned URL (presigned URLs expire after 60 minutes)
        editor.chain().focus().setImage({ src: `/api/images/${data.objectId}` }).run();
      } catch (err) {
        console.error('Image upload error:', err);
        alert(err instanceof Error ? err.message : 'Bild-Upload fehlgeschlagen. Bitte erneut versuchen.');
      }

      // Reset file input
      e.target.value = '';
    },
    [editor, uploadConfig]
  );

  return (
    <FormControl fullWidth error={!!error} style={{ marginBottom: '16px' }}>
      {label && (
        <InputLabel
          shrink
          style={{ position: 'relative', transform: 'none', marginBottom: '8px' }}
        >
          {label}
        </InputLabel>
      )}
      <div
        data-testid={testId}
        style={{
          border: error ? '1px solid #d32f2f' : '1px solid #ccc',
          borderRadius: '4px',
          overflow: 'hidden',
        }}
      >
        <EditorToolbar editor={editor} onImageUpload={handleImageUpload} />
        <EditorContent
          editor={editor}
          style={{
            minHeight: '200px',
            padding: '12px',
          }}
        />
      </div>
      {error && <FormHelperText>{error.message}</FormHelperText>}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
      <style>{`
        .ProseMirror {
          outline: none;
          min-height: 180px;
        }
        .ProseMirror p {
          margin: 0 0 0.5em 0;
        }
        .ProseMirror h1 {
          font-size: 2em;
          font-weight: bold;
          margin: 1em 0 0.5em 0;
        }
        .ProseMirror h2 {
          font-size: 1.5em;
          font-weight: bold;
          margin: 1em 0 0.5em 0;
        }
        .ProseMirror h3 {
          font-size: 1.25em;
          font-weight: bold;
          margin: 1em 0 0.5em 0;
        }
        .ProseMirror ul {
          padding-left: 1.5em;
          margin: 0.5em 0;
          list-style-type: disc;
        }
        .ProseMirror ol {
          padding-left: 1.5em;
          margin: 0.5em 0;
          list-style-type: decimal;
        }
        .ProseMirror li {
          margin: 0.25em 0;
        }
        .ProseMirror blockquote {
          border-left: 3px solid #ccc;
          padding-left: 1em;
          margin: 0.5em 0;
          color: #666;
        }
        .ProseMirror pre {
          background: #f5f5f5;
          padding: 0.75em 1em;
          border-radius: 4px;
          overflow-x: auto;
        }
        .ProseMirror code {
          background: #f5f5f5;
          padding: 0.2em 0.4em;
          border-radius: 3px;
          font-family: monospace;
        }
        .ProseMirror hr {
          border: none;
          border-top: 2px solid #ccc;
          margin: 1.5em 0;
        }
        .ProseMirror s, .ProseMirror strike {
          text-decoration: line-through;
        }
        .ProseMirror a {
          color: #1976d2;
          text-decoration: underline;
          cursor: pointer;
        }
        .ProseMirror strong, .ProseMirror b {
          font-weight: bold;
        }
        .ProseMirror em, .ProseMirror i {
          font-style: italic;
        }
        .rich-text-image {
          max-width: 100%;
          height: auto;
          display: block;
          margin: 1em 0;
        }
        .rich-text-link {
          color: #1976d2;
          text-decoration: underline;
        }
      `}</style>
    </FormControl>
  );
}
