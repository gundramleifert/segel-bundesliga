/** Whether a post's text starts with its title again (Story R-1) — the same rule as the
 *  server's `rich_text.repeats_title`, said in the editor before a save is refused: the
 *  first block, a heading or a paragraph, saying the title and nothing else. */
const words = (text: string) => text.split(/\s+/).filter(Boolean).join(" ").toLocaleLowerCase();

export function repeatsTitle(html: string, title: string): boolean {
  if (!title.trim()) return false;
  const first = new DOMParser().parseFromString(html, "text/html").body.firstElementChild;
  if (!first || !/^(H2|P)$/.test(first.tagName)) return false;
  return words(first.textContent ?? "") === words(title);
}
