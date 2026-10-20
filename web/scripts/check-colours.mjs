// Every colour on a page is a name, never a shade (index.css, "colours"): `text-muted`, not
// `text-slate-500`. A shade has one value, so a page that names one stops working in the
// other theme — and the next page copies it. This finds every shade class in the source
// outside the few files whose colours are not the theme's, each listed with its reason.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("../src/", import.meta.url).pathname;

/** What lies on a picture and is part of it — a play button, the map's marks — or is a
 *  picture itself, keeps its colours in either theme. */
const FIXED = {
  "prototype/": "the throwaway prototype of issue #14",
  "components/site/Cards.tsx": "the play button on a video's still",
  "components/site/Frame.tsx": "the logo's white plate",
  "components/site/DevSwitch.tsx": "a development tool over the picture",
  "components/Lightbox.tsx": "a photo viewer: black, whatever the page",
  "components/CrestEditor.tsx": "the shade over a crest being replaced",
  "components/FinishOrderPad.tsx": "the boats' own colours",
  "pages/Live.tsx": "what is drawn on the map",
  "components/Tip.tsx": "a tooltip, dark in either theme",
};

const SHADE =
  /(?<![\w/[-])(?:[a-z-]+:)*(?:bg|text|border|ring|divide|from|via|to|outline|fill|stroke|accent|decoration)(?:-[trblxyse])?-(?:white|black|slate|gray|zinc|neutral|stone|brand|amber|emerald|green|red|rose|sky|blue|yellow|orange|indigo|violet|purple|teal|lime|cyan|pink|ink|page)(?:-\d{2,3})?(?:\/\d+)?(?![\w/-])/g;

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      if (name !== "generated") yield* files(path);
    } else if (/\.tsx?$/.test(name)) yield path;
  }
}

const errors = [];
for (const path of files(root)) {
  const rel = relative(root, path);
  if (Object.keys(FIXED).some((fixed) => rel === fixed || (fixed.endsWith("/") && rel.startsWith(fixed)))) continue;
  readFileSync(path, "utf8")
    .split("\n")
    .forEach((line, i) => {
      for (const [shade] of line.matchAll(SHADE)) errors.push(`${rel}:${i + 1}: ${shade}`);
    });
}

if (errors.length) {
  console.error(`${errors.length} shade classes — name the colour instead (index.css, "colours"):`);
  for (const e of errors) console.error(`  ${e}`);
  process.exit(1);
}
console.log("every colour outside the pictures is a name");
