"""Loading the shared ALIBI prompt set.

Same law as every stack, either game: the files under ``shared/prompts/alibi``
are sent verbatim, substitution is literal ``{{name}}`` -> string, and the
loader fails loudly on logic or variable drift. The archivist pair lives
outside the manifest (fixed contract, like ludo's judge prompt) and is loaded
separately by :func:`load_archivist`.
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

#: The stacks render exactly these into the archivist prompts — mirrored in
#: scripts/check_prompts.py, which enforces it repo-wide.
ARCHIVIST_VARIABLES = {"system.md": (), "answer.md": ("query", "documents")}


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "shared" / "prompts" / "alibi" / "manifest.yaml").exists():
            return parent
    raise FileNotFoundError("could not locate shared/prompts/alibi from " + str(here))


@dataclass(frozen=True)
class Template:
    name: str
    text: str
    variables: tuple[str, ...]

    def render(self, **values: Any) -> str:
        """Substitute every declared variable. Missing or extra ones are errors —
        a silently unsubstituted ``{{hand}}`` would reach a model as braces."""
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
    base = base or (repo_root() / "shared" / "prompts" / "alibi")
    manifest = yaml.safe_load((base / "manifest.yaml").read_text(encoding="utf-8"))

    system = tuple(_load_template(base, e) for e in manifest["system"])
    turn = {name: _load_template(base, e) for name, e in manifest["turn"].items()}

    return PromptSet(
        version=manifest["version"],
        digest=digest(base, manifest),
        system=system,
        turn=turn,
    )


def load_archivist(base: Path | None = None) -> dict[str, Template]:
    """The fixed-contract pair: ``system.md`` (no variables) and ``answer.md``."""
    base = base or (repo_root() / "shared" / "prompts" / "alibi" / "archivist")
    loaded = {}
    for filename, variables in ARCHIVIST_VARIABLES.items():
        entry = {"file": filename, "variables": list(variables)}
        loaded[filename.removesuffix(".md")] = _load_template(base, entry)
    return loaded


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
