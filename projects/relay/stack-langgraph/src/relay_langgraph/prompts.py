"""Loading the shared RELAY prompt set.

Same law as every stack in every game: the files under ``shared/prompts/relay``
are sent verbatim, substitution is literal ``{{name}}`` -> string, and the
loader fails loudly on logic or variable drift. The anchor prompt lives outside
the manifest (fixed contract, like ludo's judge and alibi's archivist) and is
loaded by :func:`load_anchor`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

LOGIC = re.compile(r"\{\{[#/^>!]|\{%|\$\{|\{\{\s*\w+\s*\|")
VARIABLE = re.compile(r"\{\{(\w+)\}\}")

#: The stacks render exactly this into the anchor prompt — mirrored in
#: scripts/check_prompts.py, which enforces it repo-wide. One variable, because
#: the anchor is a model doing one call, not an agent with a situation.
ANCHOR_VARIABLES = {"solve.md": ("stage",)}


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "shared" / "prompts" / "relay" / "manifest.yaml").exists():
            return parent
    raise FileNotFoundError("could not locate shared/prompts/relay from " + str(here))


@dataclass(frozen=True)
class Template:
    name: str
    text: str
    variables: tuple[str, ...]

    def render(self, **values: Any) -> str:
        """Substitute every declared variable. Missing or extra ones are errors —
        a silently unsubstituted ``{{stage}}`` would reach a model as braces."""
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
    version: int
    digest: str
    system: tuple[Template, ...]
    turn: dict[str, Template]

    def system_prompt(self, **values: Any) -> str:
        """The cacheable layer: every ``system/`` template, concatenated in order."""
        return "\n\n".join(t.render(**{k: values[k] for k in t.variables})
                           for t in self.system)

    def provenance(self) -> dict[str, Any]:
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
    base = base or (repo_root() / "shared" / "prompts" / "relay")
    manifest = yaml.safe_load((base / "manifest.yaml").read_text(encoding="utf-8"))

    system = tuple(_load_template(base, e) for e in manifest["system"])
    turn = {name: _load_template(base, e) for name, e in manifest["turn"].items()}

    return PromptSet(version=manifest["version"], digest=digest(base, manifest),
                     system=system, turn=turn)


def load_anchor(base: Path | None = None) -> Template:
    """The fixed-contract outsider: one template, one variable."""
    base = base or (repo_root() / "shared" / "prompts" / "relay" / "anchor")
    return _load_template(base, {"file": "solve.md",
                                 "variables": list(ANCHOR_VARIABLES["solve.md"])})


def digest(base: Path, manifest: dict[str, Any]) -> str:
    """Content hash over the manifest and every template it names — recorded in
    ``game_started`` so a transcript names exactly the prompts that produced it."""
    h = hashlib.sha256()
    h.update(str(manifest["version"]).encode("utf-8"))
    entries = list(manifest["system"]) + list(manifest["turn"].values())
    for entry in entries:
        h.update(entry["file"].encode("utf-8"))
        h.update(b"\0")
        h.update((base / entry["file"]).read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()
