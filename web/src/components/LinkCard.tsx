import { Card } from "@heroui/react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/** A card that is a link to one thing — a club, a series, a matchday.
 *
 * Three lists had built this shape by hand and had already drifted: the same hover
 * treatment written three times, the description under the title in one and under the
 * whole row in another, `block group` in two places and `group block h-full` in the
 * third. None of that was a decision anybody made.
 *
 * The header is one row — `lead`, then title and description, then `aside` — because that
 * is what all three wanted: a crest or a logo on the left, a status badge on the right.
 * `h-full` on the card so cards in a row line up with the tallest, which only works if
 * the link is `h-full` too.
 */
export function LinkCard({
  to,
  testId,
  title,
  description,
  lead,
  aside,
  children,
}: {
  to: string;
  testId?: string;
  title: ReactNode;
  description?: ReactNode;
  /** Crest, logo, or nothing — to the left of the title. */
  lead?: ReactNode;
  /** A badge or similar, pushed to the right of the row. */
  aside?: ReactNode;
  /** The card's body, below the header. Most cards have none. */
  children?: ReactNode;
}) {
  return (
    <Link to={to} data-testid={testId} className="group block h-full">
      <Card className="h-full transition-shadow group-hover:shadow-md">
        <Card.Header>
          <div className="flex items-start gap-3">
            {lead}
            {/* `min-w-0` so a long name truncates instead of pushing the badge out of the
                card — and, through the page's grid, the page past the viewport (A-10). */}
            <div className="min-w-0 flex-1">
              <Card.Title className="truncate text-base">{title}</Card.Title>
              {description && <Card.Description>{description}</Card.Description>}
            </div>
            {aside}
          </div>
        </Card.Header>
        {children && <Card.Content>{children}</Card.Content>}
      </Card>
    </Link>
  );
}
