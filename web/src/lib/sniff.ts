/** The type a file *is*, from its first bytes — never its name or `File.type`, which a
 *  browser takes from the extension (`docs/gotchas`). Only the types this site accepts are
 *  known; anything else answers `null`. The server decides again on its own (libmagic,
 *  `api/app/services/uploads.py`); this is for saying "not that kind of file" before the
 *  upload, not instead of it. */
const SIGNATURES: [type: string, matches: (bytes: Uint8Array) => boolean][] = [
  ["application/pdf", (b) => ascii(b, 0, "%PDF")],
  ["image/png", (b) => [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a].every((v, i) => b[i] === v)],
  ["image/jpeg", (b) => b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff],
  ["image/webp", (b) => ascii(b, 0, "RIFF") && ascii(b, 8, "WEBP")],
];

function ascii(bytes: Uint8Array, at: number, text: string): boolean {
  return [...text].every((char, i) => bytes[at + i] === char.charCodeAt(0));
}

export async function sniff(file: Blob): Promise<string | null> {
  const bytes = new Uint8Array(await file.slice(0, 16).arrayBuffer());
  return SIGNATURES.find(([, matches]) => matches(bytes))?.[0] ?? null;
}

/** Whether a sniffed type is one of `accept` (as for `<input accept>`, `image/*` allowed). */
export function accepted(type: string | null, accept: string): boolean {
  if (!type) return false;
  return accept
    .split(",")
    .map((t) => t.trim())
    .some((t) => (t.endsWith("/*") ? type.startsWith(t.slice(0, -1)) : type === t));
}
