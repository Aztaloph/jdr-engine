#!/usr/bin/env python
"""Liste les personnages de data/bot.db (ids pour le lobby web / tests manuels)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jdr_engine.persistence.database import get_connection, init_database


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Affiche les character_id présents dans la base locale.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Chemin SQLite (défaut : data/bot.db du dépôt).",
    )
    args = parser.parse_args()

    db_path = init_database(args.db)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, nom, classe, niveau
            FROM personnages
            ORDER BY nom COLLATE NOCASE
            """
        ).fetchall()

    if not rows:
        print("Aucun personnage en base.", file=sys.stderr)
        return 1

    print(f"{len(rows)} personnage(s) — base : {db_path}\n")
    print(f"{'ID':<10}  {'Nom':<24}  {'Classe':<12}  Niv.")
    print("-" * 58)
    for row in rows:
        print(f"{row['id']:<10}  {row['nom']:<24}  {row['classe']:<12}  {row['niveau']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
