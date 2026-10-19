import { Button } from "@heroui/react";
import Image from "@tiptap/extension-image";
import { TableKit } from "@tiptap/extension-table";
import { EditorContent, useEditor, useEditorState, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { uploadPostPhoto } from "../api/generated/sbl";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { ErrorMessage } from "./Blocks";
import { Select } from "./Select";
import { Tip } from "./Tip";

/** The editor editorial writes news and releases in — Story R-1.
 *
 * **TipTap** (MIT), chosen on 2026-10-19 over CKEditor 5 and TinyMCE (GPL or commercial)
 * and Plate (the same score, less established, and its own shadcn components beside
 * HeroUI). TipTap is headless: it is only the editable area, and the toolbar here is
 * built from the site's own pieces — HeroUI buttons, `Tip`, `Select` — so the editor looks
 * like the rest of the administration.
 *
 * **WordPress, not Markdown** is what editorial knows, so every control is a button with
 * a tooltip, the paragraph style a dropdown like WordPress's classic editor. The toolbar
 * makes exactly what the server keeps (`api/app/services/rich_text.py`); a control added
 * here needs its element added there, or it is silently dropped on save.
 *
 * The default export, so the editing page loads it with `React.lazy`: TipTap and
 * ProseMirror are a few hundred kilobytes that no reader of the site needs.
 */
export default function RichTextEditor({
  value,
  onChange,
  testId,
}: {
  value: string;
  onChange: (html: string) => void;
  testId: string;
}) {
  const { t } = useTranslation("admin");
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
        code: false,
        codeBlock: false,
        link: { openOnClick: false, autolink: true, defaultProtocol: "https" },
      }),
      Image,
      TableKit.configure({ table: { resizable: false } }),
    ],
    content: value,
    editorProps: {
      attributes: {
        class: "rich-text min-h-72 px-4 py-3 text-base leading-relaxed text-slate-700 outline-none",
        "data-testid": `${testId}-content`,
        "aria-label": t("posts.bodyLabel"),
      },
    },
    // The empty editor is one empty paragraph; the server stores that as no text at all.
    onUpdate: ({ editor }) => onChange(editor.isEmpty ? "" : editor.getHTML()),
  });

  if (!editor) return null;
  return (
    <div
      className="overflow-hidden rounded-md border border-slate-300 bg-white focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-200"
      data-testid={testId}
    >
      <Toolbar editor={editor} testId={testId} />
      <EditorContent editor={editor} />
    </div>
  );
}

type Style = "paragraph" | "h2" | "h3";

function Toolbar({ editor, testId }: { editor: Editor; testId: string }) {
  const { t } = useTranslation("admin");
  const [linking, setLinking] = useState(false);
  // Read through `useEditorState`, so the toolbar re-renders when the selection moves —
  // the editor object itself never changes identity.
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      style: (e.isActive("heading", { level: 2 }) ? "h2" : e.isActive("heading", { level: 3 }) ? "h3" : "paragraph") as Style,
      bold: e.isActive("bold"),
      italic: e.isActive("italic"),
      underline: e.isActive("underline"),
      strike: e.isActive("strike"),
      bulletList: e.isActive("bulletList"),
      orderedList: e.isActive("orderedList"),
      blockquote: e.isActive("blockquote"),
      link: e.isActive("link"),
      table: e.isActive("table"),
    }),
  });

  const setStyle = (style: Style) => {
    const chain = editor.chain().focus();
    if (style === "paragraph") chain.setParagraph().run();
    else chain.setHeading({ level: style === "h2" ? 2 : 3 }).run();
  };

  return (
    <div className="border-b border-slate-200 bg-slate-50">
      <div className="flex flex-wrap items-center gap-1 px-2 py-1.5" role="toolbar" aria-label={t("posts.toolbarLabel")}>
        <Select
          size="inline"
          value={state.style}
          onChange={(e) => setStyle(e.target.value as Style)}
          testId={`${testId}-style`}
          aria-label={t("posts.styleLabel")}
        >
          <option value="paragraph">{t("posts.styleParagraph")}</option>
          <option value="h2">{t("posts.styleHeading")}</option>
          <option value="h3">{t("posts.styleSubheading")}</option>
        </Select>
        <Divider />
        <Tool label={t("posts.bold")} active={state.bold} onPress={() => editor.chain().focus().toggleBold().run()} testId={`${testId}-bold`}>
          <span className="font-bold">B</span>
        </Tool>
        <Tool label={t("posts.italic")} active={state.italic} onPress={() => editor.chain().focus().toggleItalic().run()} testId={`${testId}-italic`}>
          <span className="font-serif italic">I</span>
        </Tool>
        <Tool label={t("posts.underline")} active={state.underline} onPress={() => editor.chain().focus().toggleUnderline().run()} testId={`${testId}-underline`}>
          <span className="underline">U</span>
        </Tool>
        <Tool label={t("posts.strike")} active={state.strike} onPress={() => editor.chain().focus().toggleStrike().run()} testId={`${testId}-strike`}>
          <span className="line-through">S</span>
        </Tool>
        <Divider />
        <Tool label={t("posts.bulletList")} active={state.bulletList} onPress={() => editor.chain().focus().toggleBulletList().run()} testId={`${testId}-bullet-list`}>
          •≡
        </Tool>
        <Tool label={t("posts.orderedList")} active={state.orderedList} onPress={() => editor.chain().focus().toggleOrderedList().run()} testId={`${testId}-ordered-list`}>
          1.≡
        </Tool>
        <Tool label={t("posts.quote")} active={state.blockquote} onPress={() => editor.chain().focus().toggleBlockquote().run()} testId={`${testId}-quote`}>
          ❝
        </Tool>
        <Divider />
        <Tool label={t("posts.link")} active={state.link || linking} onPress={() => setLinking((open) => !open)} testId={`${testId}-link`}>
          🔗
        </Tool>
        <ImageTool editor={editor} testId={testId} />
        <Tool
          label={t("posts.table")}
          active={state.table}
          onPress={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
          testId={`${testId}-table`}
        >
          ▦
        </Tool>
        <Divider />
        <Tool label={t("posts.undo")} onPress={() => editor.chain().focus().undo().run()} testId={`${testId}-undo`}>
          ↶
        </Tool>
        <Tool label={t("posts.redo")} onPress={() => editor.chain().focus().redo().run()} testId={`${testId}-redo`}>
          ↷
        </Tool>
      </div>
      {linking && <LinkBar editor={editor} onClose={() => setLinking(false)} testId={testId} />}
      {state.table && <TableBar editor={editor} testId={testId} />}
    </div>
  );
}

function Tool({
  label,
  active = false,
  onPress,
  testId,
  children,
}: {
  label: string;
  active?: boolean;
  onPress: () => void;
  testId: string;
  children: ReactNode;
}) {
  // `preventFocusOnPress`: a toolbar button must not take the focus from the text. Without
  // it the press moved the focus to the button and the editor's `focus()` got it back a
  // moment too late — the next keystroke was lost and bold stayed on (found by
  // e2e/editorial.spec.ts). Tab still reaches every button.
  return (
    <Tip text={label}>
      <Button
        size="sm"
        variant={active ? "primary" : "ghost"}
        isIconOnly
        preventFocusOnPress
        aria-label={label}
        aria-pressed={active}
        onPress={onPress}
        data-testid={testId}
        className="text-base"
      >
        {children}
      </Button>
    </Tip>
  );
}

function Divider() {
  return <span aria-hidden className="mx-1 h-5 w-px bg-slate-300" />;
}

/** The address of a link, typed in a row under the toolbar — not the browser's `prompt`,
 *  which blocks the page and cannot be styled or translated. */
function LinkBar({ editor, onClose, testId }: { editor: Editor; onClose: () => void; testId: string }) {
  const { t } = useTranslation("admin");
  const [href, setHref] = useState<string>(() => editor.getAttributes("link").href ?? "");

  const apply = () => {
    const chain = editor.chain().focus().extendMarkRange("link");
    if (href.trim()) chain.setLink({ href: href.trim() }).run();
    else chain.unsetLink().run();
    onClose();
  };

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 px-2 py-1.5">
      <input
        className={`${INPUT_CLASS} max-w-md flex-1`}
        value={href}
        onChange={(e) => setHref(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            apply();
          }
          if (e.key === "Escape") onClose();
        }}
        placeholder={t("posts.linkPlaceholder")}
        aria-label={t("posts.linkLabel")}
        autoFocus
        data-testid={`${testId}-link-input`}
      />
      <Button size="sm" onPress={apply} data-testid={`${testId}-link-apply`}>
        {t("posts.linkApply")}
      </Button>
      {editor.isActive("link") && (
        <Button
          size="sm"
          variant="ghost"
          onPress={() => {
            editor.chain().focus().extendMarkRange("link").unsetLink().run();
            onClose();
          }}
          data-testid={`${testId}-link-remove`}
        >
          {t("posts.linkRemove")}
        </Button>
      )}
    </div>
  );
}

/** A picture in the text: uploaded like the post's own picture, then inserted. */
function ImageTool({ editor, testId }: { editor: Editor; testId: string }) {
  const { t } = useTranslation("admin");
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const { url } = await uploadPostPhoto({ file });
      editor.chain().focus().setImage({ src: url, alt: file.name.replace(/\.[^.]+$/, "") }).run();
    } catch (e) {
      setError(errorText(e, t("posts.photoError")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Tool label={busy ? t("posts.photoUploading") : t("posts.image")} onPress={() => input.current?.click()} testId={`${testId}-image`}>
        🖼
      </Tool>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png"
        className="hidden"
        data-testid={`${testId}-image-input`}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void upload(file);
        }}
      />
      {error && <ErrorMessage text={error} testId={`${testId}-image-error`} />}
    </>
  );
}

/** Rows and columns, shown while the cursor is in a table. */
function TableBar({ editor, testId }: { editor: Editor; testId: string }) {
  const { t } = useTranslation("admin");
  const actions: [string, string, () => boolean][] = [
    ["rowAfter", t("posts.tableRowAdd"), () => editor.chain().focus().addRowAfter().run()],
    ["colAfter", t("posts.tableColumnAdd"), () => editor.chain().focus().addColumnAfter().run()],
    ["rowDelete", t("posts.tableRowDelete"), () => editor.chain().focus().deleteRow().run()],
    ["colDelete", t("posts.tableColumnDelete"), () => editor.chain().focus().deleteColumn().run()],
    ["delete", t("posts.tableDelete"), () => editor.chain().focus().deleteTable().run()],
  ];
  return (
    <div className="flex flex-wrap items-center gap-1 border-t border-slate-200 px-2 py-1.5" data-testid={`${testId}-table-bar`}>
      {actions.map(([key, label, run]) => (
        <Button key={key} size="sm" variant="ghost" preventFocusOnPress onPress={() => run()} data-testid={`${testId}-table-${key}`}>
          {label}
        </Button>
      ))}
    </div>
  );
}
