import { cva, type VariantProps } from "class-variance-authority";
import { useTranslation } from "react-i18next";

/** SAP's home for SAP Sailing Analytics — where a credit links when no act page is known. */
export const SAP_SAILING_URL = "https://www.sapsailing.com";

/** SAP's logo, copied unchanged from SAP's own repository (`sailing-analytics`,
 *  `mobile/com.sap.sailing.racecommittee.app/res/drawable-xxxhdpi/sap_logo_150dp.png`).
 *  Transparent around the mark, so it stands on the light and the dark theme alike.
 *  Replace it with the file from SAP Brand Tools (brand.sap.com) once access is granted. */
export const SAP_LOGO_SRC = "/brand/sap-logo.png";

/** The credit's shapes. Only the shape varies; the wording is the same everywhere:
 *  - `long`: one line, logo and phrase side by side — under a table, in a footer;
 *  - `square`: logo above, the phrase in two lines below — a card, a sidebar, a tile;
 *  - `mark`: the logo alone, the phrase as its accessible name — where there is no room.
 *  `surface="card"` gives it its own ground and border, for a place over a photo. */
const attribution = cva(
  "group inline-flex rounded-md text-muted no-underline transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
  {
    variants: {
      shape: {
        long: "flex-row flex-wrap items-center gap-x-2 gap-y-1",
        square: "aspect-square flex-col items-center justify-center gap-2 text-center",
        mark: "items-center",
      },
      size: { sm: "text-xs", md: "text-sm" },
      surface: {
        plain: "",
        card: "border border-separator bg-surface px-3 py-2",
      },
    },
    compoundVariants: [
      { shape: "square", size: "sm", class: "w-28 p-3" },
      { shape: "square", size: "md", class: "w-36 p-4" },
    ],
    defaultVariants: { shape: "long", size: "sm", surface: "plain" },
  },
);

const logo = cva("w-auto shrink-0", {
  variants: {
    shape: { long: "", square: "", mark: "" },
    size: { sm: "", md: "" },
  },
  compoundVariants: [
    { shape: "long", size: "sm", class: "h-4" },
    { shape: "long", size: "md", class: "h-5" },
    { shape: "mark", size: "sm", class: "h-5" },
    { shape: "mark", size: "md", class: "h-7" },
    { shape: "square", size: "sm", class: "h-8" },
    { shape: "square", size: "md", class: "h-11" },
  ],
  defaultVariants: { shape: "long", size: "sm" },
});

export type SapAttributionVariants = VariantProps<typeof attribution>;

/** "Results powered by SAP Sailing Analytics", with SAP's logo, wherever results from SAP
 *  Sailing show (Story B-21). SAP's API terms require SAP branding in every end-user
 *  interface based on its data — this one component is that credit, so SAP's wording or
 *  logo changes in one file. `href` is where it leads: an act's own page at SAP where there
 *  is one, else sapsailing.com. `when` false renders nothing: a table with no result from
 *  SAP is not credited. */
export function SapAttribution({
  when = true,
  href,
  shape,
  size,
  surface,
  testId = "sap-attribution",
  className = "mt-3",
}: SapAttributionVariants & {
  when?: boolean;
  href?: string | null;
  testId?: string;
  /** Where it sits — margins and alignment, never its look (that is the variants'). */
  className?: string;
}) {
  const { t } = useTranslation();
  if (!when) return null;
  const phrase = t("sapAttribution.poweredBy");
  const name = "SAP Sailing Analytics";
  return (
    <div className={className} data-testid={testId}>
      <a
        href={href ?? SAP_SAILING_URL}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={shape === "mark" ? `${phrase} ${name}` : undefined}
        title={shape === "mark" ? `${phrase} ${name}` : undefined}
        className={attribution({ shape, size, surface })}
      >
        <img src={SAP_LOGO_SRC} alt={shape === "mark" ? "" : "SAP"} className={logo({ shape, size })} />
        {shape !== "mark" && (
          <span className={shape === "square" ? "flex flex-col leading-tight" : undefined}>
            <span>{phrase}</span>{" "}
            <span className="font-semibold text-foreground group-hover:underline">{name}</span>
          </span>
        )}
      </a>
    </div>
  );
}
