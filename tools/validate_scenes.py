#!/usr/bin/env python3
"""Valide les fichiers scene.json v1 (jalon S — lot Sa)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interfaces.scenes.validate import validate_scene_document

FIXTURES_DIR = ROOT / "data" / "scenes" / "fixtures"


def validate_file(path: Path) -> int:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[X] {path.name} — JSON invalide : {exc}")
        return 1

    report = validate_scene_document(raw)
    if report.ok:
        print(f"[OK] {path.name}")
        return 0

    print(f"[X] {path.name} — {report.error_count} erreur(s)")
    for issue in report.issues:
        if issue.level != "error":
            continue
        ref = f" ({issue.ref})" if issue.ref else ""
        print(f"  [X] [{issue.code}] {issue.message}{ref}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Valide scene.json v1")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Fichiers scene.json (défaut : data/scenes/fixtures/*.json)",
    )
    args = parser.parse_args()

    if args.paths:
        paths = [Path(p) for p in args.paths]
    else:
        if not FIXTURES_DIR.is_dir():
            print(f"[ERREUR] Répertoire introuvable : {FIXTURES_DIR}")
            return 1
        paths = sorted(FIXTURES_DIR.glob("*.json"))

    if not paths:
        print("[ERREUR] Aucun fichier à valider.")
        return 1

    failures = 0
    for path in paths:
        failures += validate_file(path)

    if failures:
        print(f"[X] Validation échouée ({failures} fichier(s))")
        return 1

    print(f"[OK] Scènes valides ({len(paths)} fichier(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
