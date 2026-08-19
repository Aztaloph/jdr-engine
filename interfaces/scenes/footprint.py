"""Emprise axis-aligned après rotation quart de tour — jalon S."""

from __future__ import annotations


def effective_footprint(width: int, height: int, quarter_turns: int) -> tuple[int, int]:
    """
    Retourne (largeur_effective, hauteur_effective) en cases.

    Règle actée : quarter_turns impair → emprise h×w ; pair → w×h.
    """
    if quarter_turns % 2 == 1:
        return height, width
    return width, height
