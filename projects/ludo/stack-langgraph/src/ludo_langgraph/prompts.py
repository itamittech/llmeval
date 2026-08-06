"""Loading the shared prompt set.

Every stack loads the same files from ``shared/prompts/ludo`` and sends them
verbatim. This module is this stack's copy of that contract — stacks cannot
share code (a shortcut between them would destroy the comparison), so each
carries its own loader and the digest proves they agree byte for byte.

The whole template language is ``{{name}}`` -> string. No conditionals, no
loops, no filters — see shared/prompts/README.md for why: template logic would
have to be implemented identically in two languages, and the places they
disagreed would be silent parity breaks in the one file whose job is to
guarantee parity.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

#: Anything a template engine would treat as control flow. Rendering must fail
#: loudly rather than quietly emit it, or a stack could smuggle logic in.
LOGIC = re.compile(r"\{\{[#/^>!]|\{%|\$\{|\{\{\s*\w+\s*\|")

VARIABLE = re.compile(r"\{\{(\w+)\}\}")


def repo_root() -> Path:
    """Walk up to the repository root, which is where ``shared/`` lives."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "shared" / "prompts" / "ludo" / "manifest.yaml").exists():
            return parent
    raise FileNotFoundError("could not locate shared/prompts/ludo from " + str(here))


@dataclass(frozen=True)
class Template:
    name: str
    text: str
    variables: tuple[str, ...]

    def render(self, **values: Any) -> str:
        """Substitute every declared variable. Missing or extra ones are errors.

        Strict on purpose. A silently unsubstituted ``{{board}}`` would reach a
        model as literal braces and produce plausible-looking nonsense; a
        stack quietly passing an undeclared variable would be a divergence the
        other two stacks do not have.
        """
        missing = set(self.variables) - set(values)
        if missing:
            raise KeyError(f"{self.name}: missing {sorted(missing)}")
        extra = set(values) - set(self.variables)
        if extra:
            raise KeyError(f"{self.name}: undeclared {sorted(extra)}")

        text = self.text
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", str(value))
        return text


@dataclass(frozen=True)
class PromptSet:
    """The loaded prompt set, plus the provenance a transcript records."""

    version: int
    digest: str
    system: tuple[Template, ...]
    turn: dict[str, Template]

    def system_prompt(self, **values: Any) -> str:
        """The cacheable layer: every ``system/`` template, concatenated in order.

        Stable for the whole game, which is what makes it prompt-cacheable.
        Anything that changes per turn belongs in a ``turn/`` template instead.
        """
        return "\n\n".join(t.render(**{k: values[k] for k in t.variables})
                           for t in self.system)

    def provenance(self) -> dict[str, Any]:
        """The ``game_started.prompt_set`` payload."""
        return {"version": self.version, "hash": self.digest}


def _load_template(base: Path, entry: dict[str, Any]) -> Template:
    path = base / entry["file"]
    text = path.read_text(encoding="utf-8")

    if LOGIC.search(text):
        raise ValueError(
            f"{entry['file']}: template logic found. Render it in code and pass "
            f"the result in as one variable — see shared/prompts/README.md"
        )

    declared = tuple(entry.get("variables") or ())
    used = set(VARIABLE.findall(text))
    if used != set(declared):
        raise ValueError(
            f"{entry['file']}: manifest declares {sorted(declared)}, "
            f"template uses {sorted(used)}"
        )
    return Template(entry["file"], text, declared)


def load(base: Path | None = None) -> PromptSet:
    """Load and validate the prompt set, and compute its digest."""
    base = base or (repo_root() / "shared" / "prompts" / "ludo")
    manifest = yaml.safe_load((base / "manifest.yaml").read_text(encoding="utf-8"))

    system = tuple(_load_template(base, e) for e in manifest["system"])
    turn = {name: _load_template(base, e) for name, e in manifest["turn"].items()}

    return PromptSet(
        version=manifest["version"],
        digest=digest(base, manifest),
        system=system,
        turn=turn,
    )


def digest(base: Path, manifest: dict[str, Any]) -> str:
    """Content hash over the manifest and every template it names.

    Recorded in ``game_started`` so a transcript names exactly the prompts that
    produced it. A version number alone can be forgotten on the way out the
    door; a hash cannot. Order is taken from the manifest rather than from the
    filesystem, so two checkouts hash the same regardless of directory order.
    """
    h = hashlib.sha256()
    h.update(str(manifest["version"]).encode("utf-8"))
    entries = list(manifest["system"]) + list(manifest["turn"].values())
    for entry in entries:
        h.update(entry["file"].encode("utf-8"))
        h.update(b"\0")
        h.update((base / entry["file"]).read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()
