// Copies the four brand families out of the read-only brand assets folder into
// public/fonts, where Chromium can load them.
//
// We COPY rather than reference by absolute path because Remotion's headless
// browser resolves fonts through staticFile(), and because 04_Brand_Assets is
// read-only — nothing here writes back to it.

import { existsSync, mkdirSync, copyFileSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..", "..");
const DEST = join(HERE, "..", "public", "fonts");

const FILES = [
  "SpaceGrotesk-Medium.ttf", "SpaceGrotesk-Bold.ttf",
  "Inter_24pt-Regular.ttf",
  "FiraCode-Regular.ttf", "FiraCode-Bold.ttf",
  "JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf",
];

const systemRoot = (() => {
  const envPath = join(REPO, ".env");
  if (existsSync(envPath)) {
    const m = readFileSync(envPath, "utf8").match(/^SYSTEM_ROOT=(.+)$/m);
    if (m) return m[1].trim();
  }
  return process.env.SYSTEM_ROOT;
})();

if (!systemRoot) {
  console.error("SYSTEM_ROOT not set. Copy .env.example to .env and fill it in.");
  process.exit(1);
}

const src = join(systemRoot, "04_Brand_Assets", "Fonts");
mkdirSync(DEST, { recursive: true });

let copied = 0, missing = [];
for (const f of FILES) {
  const from = join(src, f);
  if (existsSync(from)) { copyFileSync(from, join(DEST, f)); copied++; }
  else missing.push(f);
}

console.log(`fonts: ${copied}/${FILES.length} copied from ${src}`);
if (missing.length) {
  console.error(`MISSING (type will fall back off-brand): ${missing.join(", ")}`);
  process.exit(1);
}
