#!/usr/bin/env python3
"""Verify the documentation still hangs together.

Docs in this repo are a deliverable, not a byproduct — a doc describing code
that no longer exists actively misleads a reader who trusts it. This catches
the mechanical half of that problem.

    python scripts/check_docs.py

Checks:
  1. every relative markdown link points at a file that exists
  2. every #anchor points at a heading that exists in the target file
  3. mermaid node ids don't collide with reserved keywords
  4. mermaid blocks have balanced subgraph/end and braces

The mermaid half is STRUCTURAL — a hand-written list of mistakes we have
already made. It cannot tell you whether a diagram renders, and a block can
pass every check here and still fail on GitHub. `scripts/check_mermaid.mjs`
answers that question properly, by handing each block to mermaid's own parser.

Run both. Neither subsumes the other, in either direction: this one catches
reserved-word node ids that mermaid currently tolerates but that break the
moment an edge is reordered, and runs without node installed; that one catches
every malformed diagram nobody here thought to hand-code a rule for.

What NEITHER can check: whether the prose is still true. Only you can do that —
see the change map in CLAUDE.md.

Exits non-zero if anything fails, so it can gate CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", "node_modules", ".git", "target", ".claude"}

# Using any of these as a mermaid node id is a latent break: a node called
# `call` at the start of a statement parses as a click-callback directive and
# takes the whole diagram down. As an arrow target it happens to survive —
# which is worse, because it survives until someone reorders the edges. Flagged
# in every position deliberately; check_mermaid.mjs reports what breaks TODAY.
MERMAID_RESERVED = {
    "call", "click", "class", "classdef", "style", "linkstyle",
    "graph", "flowchart", "href", "default", "interpolate", "callback",
}

FENCE = re.compile(r"```.*?```", re.S)
MERMAID = re.compile(r"```mermaid\n(.*?)```", re.S)
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
BLOCK_OPEN = re.compile(r"^(subgraph|loop|alt|opt|par|critical|rect)\b")


def markdown_files(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*.md")
        if not any(part in SKIP_DIRS for part in p.parts)
    )


def anchor(heading: str) -> str:
    """Approximate GitHub's heading -> anchor slug."""
    text = heading.lstrip("#").strip().lower()
    return re.sub(r"[^\w\s-]", "", text).replace(" ", "-")


def check_links(files: list[Path]) -> list[str]:
    anchors = {
        f: {anchor(line) for line in f.read_text(encoding="utf-8").splitlines()
            if line.startswith("#")}
        for f in files
    }
    problems, count = [], 0

    for path in files:
        body = FENCE.sub("", path.read_text(encoding="utf-8"))
        for match in LINK.finditer(body):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            count += 1
            file_part, _, frag = target.partition("#")
            resolved = (path.parent / file_part).resolve() if file_part else path.resolve()

            if file_part and not resolved.exists():
                problems.append(f"{path}: broken link -> {target}")
                continue
            known = next((a for f, a in anchors.items() if f.resolve() == resolved), None)
            if frag and known is not None and frag not in known:
                problems.append(f"{path}: missing anchor -> {target}")

    print(f"  links   : {count} checked")
    return problems


#: A node id is a bare word immediately followed by a shape opener or an edge.
#: `flowchart TB` and `style foo ...` are statements, not node ids, so a plain
#: "line starts with a reserved word" test produces false positives.
ARROW = r"(?:-{2,3}>|-\.-+>|={2,3}>|-{3}|-\.-)"
NODE_AT_LINE_START = re.compile(r"^([A-Za-z_]\w*)\s*(?:[\[({]|" + ARROW + r")")
NODE_AFTER_ARROW = re.compile(ARROW + r"\s*(?:\|[^|]*\|\s*)?([A-Za-z_]\w*)\s*[\[({]")


def reserved_node_ids(lines: list[str]) -> set[str]:
    found = set()
    for line in lines:
        for match in (NODE_AT_LINE_START.match(line), *NODE_AFTER_ARROW.finditer(line)):
            if match and match.group(1).lower() in MERMAID_RESERVED:
                found.add(match.group(1))
    return found


def check_mermaid(files: list[Path]) -> list[str]:
    problems, blocks = [], 0

    for path in files:
        for index, source in enumerate(MERMAID.findall(path.read_text(encoding="utf-8")), 1):
            blocks += 1
            lines = [ln.strip() for ln in source.splitlines() if ln.strip()]
            label = f"{path} mermaid block {index}"

            opens = sum(1 for ln in lines if BLOCK_OPEN.match(ln))
            ends = sum(1 for ln in lines if ln == "end")
            if opens != ends:
                problems.append(f"{label}: {opens} block opener(s) but {ends} 'end'")
            if source.count("{") != source.count("}"):
                problems.append(f"{label}: unbalanced braces")

            if not lines[0].startswith(("flowchart", "graph")):
                continue
            for name in reserved_node_ids(lines[1:]):
                problems.append(
                    f"{label}: '{name}' is a reserved mermaid keyword — rename the node. "
                    f"Where it starts a statement the whole diagram fails to parse; "
                    f"elsewhere it survives only until someone reorders the edges"
                )

    print(f"  mermaid : {blocks} block(s) checked")
    return problems


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    files = markdown_files(root)
    print(f"checking {len(files)} markdown files")

    problems = check_links(files) + check_mermaid(files)

    if problems:
        print(f"\n{len(problems)} problem(s):", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    print("\ndocs ok")
    print("Reminder: this checks structure, not truth. Re-read what you changed.")
    print("Mermaid here is structural too — run scripts/check_mermaid.mjs to")
    print("confirm the diagrams actually render.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
