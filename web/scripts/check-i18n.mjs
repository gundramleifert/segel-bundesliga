// Parses every locale message as ICU MessageFormat, the way `i18next-icu` does at runtime.
// A message that fails to parse is otherwise rendered raw — braces and all — with no error,
// and a left-over i18next `{{name}}` is such a message. Also checks that every language has
// the source's keys and the same placeholders, so a translation cannot drop a `{count}`.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import IntlMessageFormat from "intl-messageformat";

// Element types of the ICU AST (`@formatjs/icu-messageformat-parser`'s TYPE enum, which
// intl-messageformat does not re-export).
const ARGUMENT = new Set([1, 2, 3, 4]); // argument, number, date, time
const BRANCHING = new Set([5, 6]); // select, plural

const root = new URL("../src/i18n/locales/", import.meta.url).pathname;
const source = "en";
const languages = readdirSync(root);
const errors = [];

function flatten(obj, prefix = "", out = new Map()) {
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out.set(path, value);
    else flatten(value, path, out);
  }
  return out;
}

function placeholders(elements, out = new Set()) {
  for (const el of elements) {
    if (ARGUMENT.has(el.type) || BRANCHING.has(el.type)) out.add(el.value);
    if (BRANCHING.has(el.type)) {
      for (const option of Object.values(el.options)) placeholders(option.value, out);
    }
  }
  return out;
}

const messages = {};
for (const lang of languages) {
  messages[lang] = new Map();
  for (const file of readdirSync(join(root, lang))) {
    const ns = file.replace(/\.json$/, "");
    const flat = flatten(JSON.parse(readFileSync(join(root, lang, file), "utf8")));
    for (const [key, text] of flat) {
      const id = `${ns}:${key}`;
      try {
        const ast = new IntlMessageFormat(text, lang, undefined, { ignoreTag: true }).getAst();
        messages[lang].set(id, placeholders(ast));
      } catch (err) {
        errors.push(`${lang} ${id}: ${err.message} in ${JSON.stringify(text)}`);
      }
    }
  }
}

const sorted = (set) => [...set].sort().join(", ");
for (const lang of languages.filter((l) => l !== source)) {
  for (const [id, vars] of messages[source]) {
    const theirs = messages[lang].get(id);
    if (!theirs) errors.push(`${lang} ${id}: missing (present in ${source})`);
    else if (sorted(vars) !== sorted(theirs))
      errors.push(`${lang} ${id}: placeholders {${sorted(theirs)}} differ from ${source}'s {${sorted(vars)}}`);
  }
  for (const id of messages[lang].keys())
    if (!messages[source].has(id)) errors.push(`${lang} ${id}: not in ${source}`);
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
const total = Object.values(messages).reduce((n, m) => n + m.size, 0);
console.log(`${total} messages in ${languages.length} languages parse as ICU`);
