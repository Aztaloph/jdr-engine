#!/usr/bin/env python3
"""Met à jour les métriques mesurables de ROADMAP.md (section auto-sync).

Champs mis à jour :
- nombre de tests (unittest discover, si --run-tests ou par défaut en CLI directe)
- nombre de sorts curated (fichiers definition.yaml)
- commit HEAD court
- date de dernière synchronisation

Usage :
    python tools/update_roadmap_metrics.py              # mesure complète (tests exécutés)
    python tools/update_roadmap_metrics.py --skip-tests # conserve le compteur tests existant
    python tools/update_roadmap_metrics.py --check    # exit 1 si ROADMAP périmée

Hook Git (pre-commit) : relance les tests seulement si tests/ ou code moteur/API est stagé.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = ROOT / "ROADMAP.md"
SPELLS_DIR = ROOT / "compendium" / "dnd5e" / "entries" / "spells"

START_MARKER = "<!-- ROADMAP-AUTO:START -->"
END_MARKER = "<!-- ROADMAP-AUTO:END -->"

TEST_COUNT_RE = re.compile(r"Tests unitaires \| \*\*(\d+)\*\*")


def run_tests_count() -> int:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
            "-q",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    match = re.search(r"Ran (\d+) tests", combined)
    if not match:
        raise RuntimeError(
            "Impossible de lire le nombre de tests depuis unittest.\n"
            f"stdout/stderr:\n{combined[-2000:]}"
        )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Suite de tests en échec (code {proc.returncode}) — "
            "métriques non mises à jour."
        )
    return int(match.group(1))


def read_existing_test_count(content: str) -> int | None:
    match = TEST_COUNT_RE.search(content)
    return int(match.group(1)) if match else None


def count_spells() -> int:
    if not SPELLS_DIR.is_dir():
        raise RuntimeError(f"Répertoire sorts introuvable : {SPELLS_DIR}")
    return len(list(SPELLS_DIR.glob("*/definition.yaml")))


def git_head_short() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def build_auto_block(tests: int, spells: int, head: str, today: str) -> str:
    return f"""{START_MARKER}
| Indicateur | Valeur |
|---|---|
| Tests unitaires | **{tests}** verts (`python -m unittest discover -s tests -p "test_*.py" -q`) |
| Sorts curated (YAML) | **{spells}** (`compendium/dnd5e/entries/spells/*/definition.yaml`) |
| Commit HEAD | `{head}` |
| Dernière sync auto | {today} |
{END_MARKER}"""


def replace_auto_section(content: str, new_block: str) -> str:
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    if not pattern.search(content):
        raise RuntimeError(
            f"Marqueurs {START_MARKER} / {END_MARKER} introuvables dans ROADMAP.md"
        )
    return pattern.sub(new_block, content, count=1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync métriques ROADMAP.md")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Vérifie que ROADMAP.md est à jour (exit 1 sinon)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Conserve le compteur de tests déjà présent dans ROADMAP.md",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Force l'exécution de la suite de tests (ignore --skip-tests)",
    )
    args = parser.parse_args()

    current = ROADMAP.read_text(encoding="utf-8")

    if args.run_tests or not args.skip_tests:
        tests = run_tests_count()
    else:
        existing = read_existing_test_count(current)
        if existing is None:
            tests = run_tests_count()
        else:
            tests = existing

    spells = count_spells()
    head = git_head_short()
    today = date.today().isoformat()
    new_block = build_auto_block(tests, spells, head, today)
    updated = replace_auto_section(current, new_block)

    if args.check:
        return 1 if updated != current else 0

    if updated != current:
        ROADMAP.write_text(updated, encoding="utf-8")
        mode = "mesurés" if (args.run_tests or not args.skip_tests) else "conservés (tests)"
        print(f"[OK] ROADMAP.md — {tests} tests ({mode}), {spells} sorts, HEAD {head}")
    else:
        print(f"[OK] ROADMAP.md déjà à jour — {tests} tests, HEAD {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
