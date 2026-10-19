/** Text from the site's editor, shown as it was written — Story R-1.
 *
 * The HTML is inserted as it is because **the server already cleaned it**
 * (`api/app/services/rich_text.py`, on every write) to the few elements the editor's
 * toolbar makes. Nothing else may be passed here: this component is safe only for text
 * that came through that cleaner. Styled by `.rich-text` in `index.css`, which the
 * editor uses too, so what editorial sees is what is shown.
 */
export function RichText({ html, className = "", testId }: { html: string; className?: string; testId?: string }) {
  return <div className={`rich-text ${className}`} data-testid={testId} dangerouslySetInnerHTML={{ __html: html }} />;
}
