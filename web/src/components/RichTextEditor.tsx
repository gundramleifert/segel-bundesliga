import { Button } from "@heroui/react";
import Image from "@tiptap/extension-image";
import { TableKit } from "@tiptap/extension-table";
import type { Transaction } from "@tiptap/pm/state";
import { EditorContent, useEditor, useEditorState, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { fetchMedia, getMediaByName, updateMedia } from "../api/generated/sbl";
import { useInvalidate } from "../api/useApi";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { filesIn, usePhotoUpload } from "../lib/usePhotoUpload";
import { ErrorMessage } from "./Blocks";
import { MediaPicker } from "./MediaPicker";
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
 * **Pictures come from the library** (Story R-2): the picture button opens `MediaPicker`,
 * which also uploads, fetches from a web address and takes a drop.
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
  const [picking, setPicking] = useState(false);
  // ProseMirror keeps the handlers it was first given, and they need the editor they are
  // handlers of: through a ref, filled once the editor exists.
  const handlers = useRef<Handlers | null>(null);
  const photo = usePhotoUpload((item) => handlers.current?.insertImage(item.url, item.alt));
  const adopting = useRef(new Set<string>());
  const [adoptError, setAdoptError] = useState<string | null>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // One heading, `h2`: the page's `h1` is the post's title, set in the form and
        // never in the text (Story R-1). A pasted heading of any level becomes this one.
        heading: { levels: [2] },
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
        const files = filesIn(event.dataTransfer?.files);
        if (moved || files.length === 0) return false;
        event.preventDefault();
        const at = view.posAtCoords({ left: event.clientX, top: event.clientY })?.pos ?? view.state.selection.from;
        void handlers.current?.insertPhotos(files, at);
        return true;
      },
      handlePaste: (view, event) => {
        const files = filesIn(event.clipboardData?.files);
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
    onUpdate: ({ editor }) => {
      onChange(editor.isEmpty ? "" : editor.getHTML());
      handlers.current?.adoptOutside();
    },
  });

  useEffect(() => {
    if (!editor) return;
    handlers.current = {
      // After the selection, never over it: a picture just inserted stays selected, and
      // `setImage` would replace it with the next one.
      insertImage: (src, alt) =>
        editor.chain().focus().insertContentAt(editor.state.selection.to, { type: "image", attrs: { src, alt } }).run(),
      // One after another, the first at `at`, each next after the one before. An upload
      // takes seconds and the writing goes on meanwhile, so `at` is carried through every
      // change made in between — a paragraph deleted above would otherwise move the
      // picture, or put `at` past the end of the text.
      insertPhotos: async (files, at) => {
        let where = at;
        const follow = ({ transaction }: { transaction: Transaction }) => {
          where = transaction.mapping.map(where);
        };
        editor.on("transaction", follow);
        try {
          for (const file of files) {
            const item = await photo.upload(file);
            if (!item || editor.isDestroyed) continue;
            editor.chain().focus().insertContentAt(where, { type: "image", attrs: { src: item.url, alt: item.alt } }).run();
            where = editor.state.selection.to;
          }
        } finally {
          editor.off("transaction", follow);
        }
      },
      openLink: () => setLinking(true),
      // A picture pasted from a web page arrives with its own server's address. It is
      // copied into the library and the address swapped (Story R-1: never hot-linked);
      // one that cannot be fetched is taken out again, with the reason. Found again by
      // its address when the copy is back, so writing on meanwhile moves nothing.
      adoptOutside: () => {
        const outside = new Set<string>();
        editor.state.doc.descendants((node) => {
          const src = String(node.attrs.src ?? "");
          if (node.type.name === "image" && !ownPicture(src) && !adopting.current.has(src)) outside.add(src);
        });
        for (const src of outside) {
          adopting.current.add(src);
          setAdoptError(null);
          fetchMedia({ url: src })
            .then((item) => replaceImages(editor, src, { src: item.url, alt: item.alt }))
            .catch((error: unknown) => {
              replaceImages(editor, src, null);
              setAdoptError(errorText(error, t("posts.adoptError")));
            })
            .finally(() => adopting.current.delete(src));
        }
      },
    };
  });

  if (!editor) return null;
  return (
    <div
      className="overflow-hidden rounded-md border border-slate-300 bg-white focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-200"
      data-testid={testId}
    >
      <Toolbar
        editor={editor}
        photo={photo}
        linking={linking}
        setLinking={setLinking}
        picking={picking}
        onPicture={() => setPicking((open) => !open)}
        testId={testId}
      />
      {picking && (
        <MediaPicker
          onPick={(item) => {
            handlers.current?.insertImage(item.url, item.alt);
            setPicking(false);
          }}
          onClose={() => setPicking(false)}
          testId={`${testId}-picker`}
        />
      )}
      <EditorContent editor={editor} />
      {photo.error && <ErrorMessage text={photo.error} testId={`${testId}-image-error`} />}
      {adoptError && <ErrorMessage text={adoptError} testId={`${testId}-adopt-error`} />}
      {/* The tips are keyboard shortcuts: on a touch screen they name keys that are not there. */}
      <p
        className={`border-t border-slate-100 px-4 py-1.5 text-xs text-slate-500 ${photo.busy ? "" : "pointer-coarse:hidden"}`}
        data-testid={`${testId}-hint`}
      >
        {photo.busy ? t("posts.photoUploading") : t("posts.editorHint")}
      </p>
    </div>
  );
}

/** The site's own pictures: the library's, and the files under `/media/` — the same rule
 *  as the server's `rich_text.own_picture`. */
const ownPicture = (src: string) => /^\/(api\/media|media)\/[\w.-]+$/.test(src);

/** The library name in a picture's address, if it is the library's. */
const libraryName = (src: string) => /^\/api\/media\/([0-9a-f]{32})/.exec(src)?.[1] ?? null;

/** Every picture with address `src` gets `attrs` — or, with `null`, is taken out. */
function replaceImages(editor: Editor, src: string, attrs: { src: string; alt: string } | null) {
  if (editor.isDestroyed) return;
  const found: { pos: number; size: number }[] = [];
  editor.state.doc.descendants((node, pos) => {
    if (node.type.name === "image" && node.attrs.src === src) found.push({ pos, size: node.nodeSize });
  });
  const tr = editor.state.tr;
  // From the end, so each position is still right when it is changed.
  for (const { pos, size } of found.reverse()) {
    if (attrs) tr.setNodeMarkup(pos, undefined, { ...editor.state.doc.nodeAt(pos)?.attrs, ...attrs });
    else tr.delete(pos, pos + size);
  }
  if (found.length) editor.view.dispatch(tr);
}

type Handlers = {
  adoptOutside: () => void;
  insertImage: (src: string, alt: string) => void;
  insertPhotos: (files: File[], at: number) => Promise<void>;
  openLink: () => void;
};

type Style = "paragraph" | "h2";

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
  picking,
  onPicture,
  testId,
}: {
  editor: Editor;
  photo: PhotoUpload;
  linking: boolean;
  setLinking: (open: boolean | ((open: boolean) => boolean)) => void;
  picking: boolean;
  onPicture: () => void;
  testId: string;
}) {
  const { t } = useTranslation("admin");
  // Read through `useEditorState`, so the toolbar re-renders when the selection moves —
  // the editor object itself never changes identity.
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      style: (e.isActive("heading", { level: 2 }) ? "h2" : "paragraph") as Style,
      active: Object.fromEntries([...MARKS, ...BLOCKS].map((f) => [f.name, e.isActive(f.name)])),
      link: e.isActive("link"),
      table: e.isActive("table"),
      image: e.isActive("image") ? String(e.getAttributes("image").src ?? "") : null,
    }),
  });

  // Every command starts from the text's focus, so the cursor stays where it was.
  const run = (command: (chain: Chain) => Chain) => command(editor.chain().focus()).run();
  const setStyle = (style: Style) =>
    run((c) => (style === "paragraph" ? c.setParagraph() : c.setHeading({ level: 2 })));
  const toggles = (list: Toggle[]) =>
    list.map((f) => (
      <Tool key={f.name} label={t(f.label)} active={state.active[f.name]} onPress={() => run(f.toggle)} testId={`${testId}-${f.testId}`}>
        {f.glyph}
      </Tool>
    ));

  return (
    <div className="border-b border-slate-200 bg-slate-50">
      {/* One row on a phone, scrolled sideways inside itself: wrapped, it took three lines
          of a small screen and left "redo" alone on the last. */}
      <div
        className="flex flex-nowrap items-center gap-1 overflow-x-auto px-2 py-1.5 *:shrink-0 sm:flex-wrap"
        role="toolbar"
        aria-label={t("posts.toolbarLabel")}
      >
        <Select
          size="inline"
          value={state.style}
          onChange={(e) => setStyle(e.target.value as Style)}
          testId={`${testId}-style`}
          aria-label={t("posts.styleLabel")}
        >
          <option value="paragraph">{t("posts.styleParagraph")}</option>
          <option value="h2">{t("posts.styleHeading")}</option>
        </Select>
        <Divider />
        {toggles(MARKS)}
        <Divider />
        {toggles(BLOCKS)}
        <Divider />
        <Tool label={t("posts.link")} active={state.link || linking} onPress={() => setLinking((open) => !open)} testId={`${testId}-link`}>
          🔗
        </Tool>
        <Tool label={photo.busy ? t("posts.photoUploading") : t("posts.image")} active={picking} onPress={onPicture} testId={`${testId}-image`}>
          🖼
        </Tool>
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
      {state.image !== null && <ImageBar editor={editor} src={state.image} key={state.image} testId={testId} />}
    </div>
  );
}

/** With a picture selected: its alt text — the library's, when it is a library picture, so
 *  correcting it here corrects it in every post that shows it (Story R-1) — and its credit,
 *  which the public page shows as the caption. */
function ImageBar({ editor, src, testId }: { editor: Editor; src: string; testId: string }) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const name = libraryName(src);
  const [entry, setEntry] = useState<{ id: number; credit: string | null } | null>(null);
  const [alt, setAlt] = useState(String(editor.getAttributes("image").alt ?? ""));
  const [state, setState] = useState<"idle" | "saving" | "saved" | "failed">("idle");

  useEffect(() => {
    if (!name) return;
    let live = true;
    getMediaByName(name)
      .then((item) => {
        if (!live) return;
        setEntry({ id: item.id, credit: item.credit ?? null });
        setAlt(item.alt);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [name]);

  const save = async () => {
    setState("saving");
    try {
      if (entry) {
        await updateMedia(entry.id, { alt });
        invalidate("/api/admin/media");
      }
      editor.chain().updateAttributes("image", { alt }).run();
      setState("saved");
    } catch {
      setState("failed");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 px-3 py-2 text-sm" data-testid={`${testId}-image-bar`}>
      <label className="flex min-w-0 flex-1 items-center gap-2">
        <span className="shrink-0 text-slate-600">{t("posts.imageAlt")}</span>
        <input
          className={`${INPUT_CLASS} min-w-0 flex-1 py-1`}
          value={alt}
          onChange={(e) => {
            setAlt(e.target.value);
            setState("idle");
          }}
          onKeyDown={(e: KeyboardEvent) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void save();
            }
          }}
          data-testid={`${testId}-image-alt-input`}
        />
      </label>
      <Button size="sm" variant="outline" isDisabled={state === "saving"} onPress={() => void save()} data-testid={`${testId}-image-alt-save`}>
        {entry ? t("posts.imageAltSaveLibrary") : t("posts.imageAltSave")}
      </Button>
      <span className="text-xs text-slate-500" data-testid={`${testId}-image-alt-state`} data-state={state}>
        {state === "saved" ? t("posts.imageAltSaved") : state === "failed" ? t("posts.imageAltFailed") : ""}
      </span>
      {entry && (
        <span className="basis-full text-xs text-slate-500" data-testid={`${testId}-image-credit`}>
          {entry.credit ? t("posts.imageCaption", { credit: entry.credit }) : t("posts.imageNoCredit")}
        </span>
      )}
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
