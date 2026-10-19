import { Button } from "@heroui/react";
import Image from "@tiptap/extension-image";
import { TableKit } from "@tiptap/extension-table";
import { EditorContent, useEditor, useEditorState, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { INPUT_CLASS } from "../lib/admin";
import { photosIn, usePhotoUpload } from "../lib/usePhotoUpload";
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
 * **A picture is dropped or pasted, a link is Ctrl+K** — the two things editorial does in
 * every article, so neither should need the toolbar (Story R-1). A dropped or pasted
 * picture is uploaded and placed where it fell or where the cursor is.
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
  const [linking, setLinking] = useState(false);
  // ProseMirror keeps the handlers it was first given, and they need the editor they are
  // handlers of: through a ref, filled once the editor exists.
  const handlers = useRef<Handlers | null>(null);
  const photo = usePhotoUpload((src, alt) => handlers.current?.insertImage(src, alt));

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
      handleDrop: (view, event, _slice, moved) => {
        const files = photosIn(event.dataTransfer?.files);
        if (moved || files.length === 0) return false;
        event.preventDefault();
        const at = view.posAtCoords({ left: event.clientX, top: event.clientY })?.pos ?? view.state.selection.from;
        void handlers.current?.insertPhotos(files, at);
        return true;
      },
      handlePaste: (view, event) => {
        const files = photosIn(event.clipboardData?.files);
        if (files.length === 0) return false;
        void handlers.current?.insertPhotos(files, view.state.selection.from);
        return true;
      },
      handleKeyDown: (_view, event) => {
        if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "k") return false;
        event.preventDefault();
        handlers.current?.openLink();
        return true;
      },
    },
    // The empty editor is one empty paragraph; the server stores that as no text at all.
    onUpdate: ({ editor }) => onChange(editor.isEmpty ? "" : editor.getHTML()),
  });

  useEffect(() => {
    if (!editor) return;
    handlers.current = {
      insertImage: (src, alt) => editor.chain().focus().setImage({ src, alt }).run(),
      // One after another, the first at `at`, each next after the one before.
      insertPhotos: async (files, at) => {
        for (const [i, file] of files.entries()) {
          const done = await photo.upload(file);
          if (!done) continue;
          const where = i === 0 ? at : editor.state.selection.to;
          editor.chain().focus().insertContentAt(where, { type: "image", attrs: { src: done.url, alt: done.name } }).run();
        }
      },
      openLink: () => setLinking(true),
    };
  });

  if (!editor) return null;
  return (
    <div
      className="overflow-hidden rounded-md border border-slate-300 bg-white focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-200"
      data-testid={testId}
    >
      <Toolbar editor={editor} photo={photo} linking={linking} setLinking={setLinking} testId={testId} />
      <EditorContent editor={editor} />
      <p className="border-t border-slate-100 px-4 py-1.5 text-xs text-slate-500" data-testid={`${testId}-hint`}>
        {photo.busy ? t("posts.photoUploading") : t("posts.editorHint")}
      </p>
    </div>
  );
}

type Handlers = {
  insertImage: (src: string, alt: string) => void;
  insertPhotos: (files: File[], at: number) => Promise<void>;
  openLink: () => void;
};

type Style = "paragraph" | "h2" | "h3";

type Chain = ReturnType<Editor["chain"]>;

/** A toggle of the toolbar: the mark or node it switches (also what `isActive` asks), its
 *  label's key, its testid and glyph, and the command. One list drives the buttons and
 *  the "is it on here?" state, so a new toggle is one line — and one tag on the server. */
type Toggle = { name: string; label: string; testId: string; glyph: ReactNode; toggle: (chain: Chain) => Chain };

const MARKS: Toggle[] = [
  { name: "bold", label: "posts.bold", testId: "bold", glyph: <span className="font-bold">B</span>, toggle: (c) => c.toggleBold() },
  { name: "italic", label: "posts.italic", testId: "italic", glyph: <span className="font-serif italic">I</span>, toggle: (c) => c.toggleItalic() },
  { name: "underline", label: "posts.underline", testId: "underline", glyph: <span className="underline">U</span>, toggle: (c) => c.toggleUnderline() },
  { name: "strike", label: "posts.strike", testId: "strike", glyph: <span className="line-through">S</span>, toggle: (c) => c.toggleStrike() },
];

const BLOCKS: Toggle[] = [
  { name: "bulletList", label: "posts.bulletList", testId: "bullet-list", glyph: "•≡", toggle: (c) => c.toggleBulletList() },
  { name: "orderedList", label: "posts.orderedList", testId: "ordered-list", glyph: "1.≡", toggle: (c) => c.toggleOrderedList() },
  { name: "blockquote", label: "posts.quote", testId: "quote", glyph: "❝", toggle: (c) => c.toggleBlockquote() },
];

type PhotoUpload = ReturnType<typeof usePhotoUpload>;

function Toolbar({
  editor,
  photo,
  linking,
  setLinking,
  testId,
}: {
  editor: Editor;
  photo: PhotoUpload;
  linking: boolean;
  setLinking: (open: boolean | ((open: boolean) => boolean)) => void;
  testId: string;
}) {
  const { t } = useTranslation("admin");
  // Read through `useEditorState`, so the toolbar re-renders when the selection moves —
  // the editor object itself never changes identity.
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      style: (e.isActive("heading", { level: 2 }) ? "h2" : e.isActive("heading", { level: 3 }) ? "h3" : "paragraph") as Style,
      active: Object.fromEntries([...MARKS, ...BLOCKS].map((f) => [f.name, e.isActive(f.name)])),
      link: e.isActive("link"),
      table: e.isActive("table"),
    }),
  });

  // Every command starts from the text's focus, so the cursor stays where it was.
  const run = (command: (chain: Chain) => Chain) => command(editor.chain().focus()).run();
  const setStyle = (style: Style) =>
    run((c) => (style === "paragraph" ? c.setParagraph() : c.setHeading({ level: style === "h2" ? 2 : 3 })));
  const toggles = (list: Toggle[]) =>
    list.map((f) => (
      <Tool key={f.name} label={t(f.label)} active={state.active[f.name]} onPress={() => run(f.toggle)} testId={`${testId}-${f.testId}`}>
        {f.glyph}
      </Tool>
    ));

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
        {toggles(MARKS)}
        <Divider />
        {toggles(BLOCKS)}
        <Divider />
        <Tool label={t("posts.link")} active={state.link || linking} onPress={() => setLinking((open) => !open)} testId={`${testId}-link`}>
          🔗
        </Tool>
        <ImageTool photo={photo} testId={testId} />
        <Tool
          label={t("posts.table")}
          active={state.table}
          onPress={() => run((c) => c.insertTable({ rows: 3, cols: 3, withHeaderRow: true }))}
          testId={`${testId}-table`}
        >
          ▦
        </Tool>
        <Divider />
        <Tool label={t("posts.undo")} onPress={() => run((c) => c.undo())} testId={`${testId}-undo`}>
          ↶
        </Tool>
        <Tool label={t("posts.redo")} onPress={() => run((c) => c.redo())} testId={`${testId}-redo`}>
          ↷
        </Tool>
      </div>
      {linking ? (
        <LinkBar editor={editor} onClose={() => setLinking(false)} testId={testId} />
      ) : (
        state.link && <LinkInfo editor={editor} onChange={() => setLinking(true)} testId={testId} />
      )}
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

/** What was typed as a link's address, as the address: `example.com` gets its `https://`,
 *  an email address its `mailto:`; a full address, a path on this site (`/1-liga/…`) or
 *  an anchor stays as it is. Empty means "no link". */
function linkTarget(typed: string): string {
  const value = typed.trim();
  if (!value || /^(https?:|mailto:|\/|#)/i.test(value)) return value;
  if (/^[^\s@/]+@[^\s@/]+\.[^\s@/]+$/.test(value)) return `mailto:${value}`;
  return `https://${value}`;
}

/** The address of a link, typed in a row under the toolbar — not the browser's `prompt`,
 *  which blocks the page and cannot be styled or translated. With no text selected and no
 *  link under the cursor there is nothing to link yet, so the row asks for the text too. */
function LinkBar({ editor, onClose, testId }: { editor: Editor; onClose: () => void; testId: string }) {
  const { t } = useTranslation("admin");
  const [href, setHref] = useState<string>(() => editor.getAttributes("link").href ?? "");
  const [text, setText] = useState("");
  const inLink = editor.isActive("link");
  const insert = editor.state.selection.empty && !inLink;

  const close = () => {
    onClose();
    editor.commands.focus();
  };
  const apply = () => {
    const target = linkTarget(href);
    const chain = editor.chain().focus();
    if (!target) chain.extendMarkRange("link").unsetLink().run();
    else if (insert) {
      const label = text.trim() || href.trim();
      chain.insertContent({ type: "text", text: label, marks: [{ type: "link", attrs: { href: target } }] }).run();
    } else chain.extendMarkRange("link").setLink({ href: target }).run();
    onClose();
  };
  const keys = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      apply();
    }
    if (e.key === "Escape") close();
  };

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 px-2 py-1.5">
      <input
        className={`${INPUT_CLASS} max-w-md flex-1`}
        value={href}
        onChange={(e) => setHref(e.target.value)}
        onKeyDown={keys}
        placeholder={t("posts.linkPlaceholder")}
        aria-label={t("posts.linkLabel")}
        autoFocus
        data-testid={`${testId}-link-input`}
      />
      {insert && (
        <input
          className={`${INPUT_CLASS} max-w-xs flex-1`}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={keys}
          placeholder={t("posts.linkTextPlaceholder")}
          aria-label={t("posts.linkTextLabel")}
          data-testid={`${testId}-link-text-input`}
        />
      )}
      <Button size="sm" onPress={apply} data-testid={`${testId}-link-apply`}>
        {t("posts.linkApply")}
      </Button>
      <Button size="sm" variant="ghost" onPress={close} data-testid={`${testId}-link-cancel`}>
        {t("posts.linkCancel")}
      </Button>
    </div>
  );
}

/** Where the link under the cursor leads, with a way to open, change or remove it — so a
 *  link can be checked without hovering, and changed without finding the toolbar's button. */
function LinkInfo({ editor, onChange, testId }: { editor: Editor; onChange: () => void; testId: string }) {
  const { t } = useTranslation("admin");
  const href: string = editor.getAttributes("link").href ?? "";
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 px-3 py-1.5 text-sm" data-testid={`${testId}-link-info`}>
      <span className="text-slate-500">{t("posts.linkLeadsTo")}</span>
      <a href={href} target="_blank" rel="noopener noreferrer" className="min-w-0 truncate text-brand-700 underline" data-testid={`${testId}-link-info-href`}>
        {href}
      </a>
      <span className="flex-1" />
      <Button size="sm" variant="ghost" preventFocusOnPress onPress={onChange} data-testid={`${testId}-link-change`}>
        {t("posts.linkChange")}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        preventFocusOnPress
        onPress={() => editor.chain().focus().extendMarkRange("link").unsetLink().run()}
        data-testid={`${testId}-link-remove`}
      >
        {t("posts.linkRemove")}
      </Button>
    </div>
  );
}

/** A picture in the text, chosen from a folder — the same upload as a dropped one. */
function ImageTool({ photo, testId }: { photo: PhotoUpload; testId: string }) {
  const { t } = useTranslation("admin");
  return (
    <>
      <Tool label={photo.busy ? t("posts.photoUploading") : t("posts.image")} onPress={photo.pick} testId={`${testId}-image`}>
        🖼
      </Tool>
      <input {...photo.input} data-testid={`${testId}-image-input`} />
      {photo.error && <ErrorMessage text={photo.error} testId={`${testId}-image-error`} />}
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
