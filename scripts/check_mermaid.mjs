#!/usr/bin/env node
/**
 * Parse every ```mermaid block in the repo with the real mermaid renderer.
 *
 *     npm ci && node scripts/check_mermaid.mjs
 *
 * scripts/check_docs.py checks mermaid STRUCTURALLY — balanced subgraph/end,
 * reserved words used as node ids. That catches the mistakes we already know
 * about. This catches the ones we don't: it hands each block to mermaid's own
 * parser, so a diagram passes here only if mermaid can actually build it.
 *
 * We learned the difference the expensive way. A diagram with a node called
 * `call` shipped to GitHub, rendered as an error box, and a reader had to tell
 * us. `call` is a click-callback directive, not a node id — mermaid knew that
 * all along; nothing in the repo asked it.
 *
 * mermaid is a browser library, so it needs a DOM. jsdom supplies one. The
 * globals below are the minimum mermaid touches at parse time; note that
 * `navigator` is a getter-only property on Node 22, so plain assignment throws
 * and defineProperty is the way in.
 *
 * Exits non-zero if any block fails to parse, so it can gate CI.
 */

import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { JSDOM } from "jsdom";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SKIP_DIRS = new Set([".venv", "__pycache__", ".pytest_cache", "node_modules", ".git", "target", ".claude"]);
const MERMAID_BLOCK = /```mermaid\r?\n([\s\S]*?)```/g;

const dom = new JSDOM("<!doctype html><html><body></body></html>");
global.window = dom.window;
global.document = dom.window.document;
// Node 22 defines `navigator` as a getter-only global; `global.navigator = ...`
// throws. mermaid reads it during init to sniff the platform.
Object.defineProperty(global, "navigator", { value: dom.window.navigator, configurable: true });
global.DOMPurify = dom.window.DOMPurify;

const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });

/** Every *.md in the repo, skipping build and vendor directories. */
async function markdownFiles(dir) {
  const found = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      found.push(...(await markdownFiles(path.join(dir, entry.name))));
    } else if (entry.name.endsWith(".md")) {
      found.push(path.join(dir, entry.name));
    }
  }
  return found.sort();
}

const files = await markdownFiles(ROOT);
const failures = [];
let blocks = 0;

for (const file of files) {
  const relative = path.relative(ROOT, file).replaceAll(path.sep, "/");
  const source = await readFile(file, "utf8");

  for (const [index, match] of [...source.matchAll(MERMAID_BLOCK)].entries()) {
    const diagram = match[1];
    blocks += 1;
    const label = `${relative} block ${index + 1}`;
    try {
      await mermaid.parse(diagram);
      console.log(`  ok      ${label}`);
    } catch (error) {
      console.log(`  FAILED  ${label}`);
      failures.push({ label, message: (error?.message ?? String(error)).trim() });
    }
  }
}

console.log(`\n${blocks} mermaid block(s) in ${files.length} markdown files`);

if (failures.length > 0) {
  console.error(`\n${failures.length} block(s) failed to parse:`);
  for (const { label, message } of failures) {
    console.error(`\n${label}:`);
    console.error(message.split("\n").map((line) => `  ${line}`).join("\n"));
  }
  process.exit(1);
}

console.log("mermaid ok — every block parses with mermaid's own parser");
