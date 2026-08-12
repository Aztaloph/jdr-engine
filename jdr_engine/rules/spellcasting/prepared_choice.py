# jdr_engine/rules/spellcasting/prepared_choice.py
"""Re-préparation des sorts — clerc, druide, paladin, magicien (SRD 2014, repos long)."""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.choices_schema import get_specialization_id
from jdr_engine.rules.effective_scores import get_effective_ability_modifier
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.spellcasting.model import (
    SpellcastingFamily,
    casting_ability_for_class,
    get_spellcasting_family,
    prepared_capacity_for_class,
)
from jdr_engine.rules.spellcasting.pools import (
    filter_spells_by_max_level,
    get_filtered_leveled_pool,
    max_castable_spell_level,
)
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots
from jdr_engine.rules.spellcasting.state import (
    get_cantrips_known,
    get_domain_spells,
    get_spellbook,
    get_spellcasting_state,
)

PREPARED_RECHOICE_CLASSES: tuple[str, ...] = ("cleric", "druid", "paladin", "wizard")


class PreparedChoiceError(Exception):
    """Choix de sorts préparés invalide ou non autorisé."""


@dataclass(frozen=True)
class PreparedChoiceContext:
    """Contexte UI / validation pour /preparer-sorts."""

    character_name: str
    class_id: str
    level: int
    pool: tuple[str, ...]
    quota: int
    srd_quota: int
    domain_spells: tuple[str, ...]
    paladin_no_slots_notice: str | None
    pool_capped_notice: str | None


def requires_prepared_rechoice_class(class_id: str) -> bool:
    return class_id in PREPARED_RECHOICE_CLASSES


def is_prepared_rechoice_pending(character: Character) -> bool:
    state = get_spellcasting_state(character)
    return bool(state.get("prepared_rechoice_pending"))


def mark_prepared_rechoice_pending(
    character: Character,
    *,
    pending: bool,
) -> Character:
    choices = dict(character.choices or {})
    state = dict(get_spellcasting_state(character))
    if pending:
        state["prepared_rechoice_pending"] = True
    else:
        state.pop("prepared_rechoice_pending", None)
    choices["spellcasting"] = state
    character.choices = choices
    return character


def _resolved_domain_spells(character: Character) -> tuple[str, ...]:
    """Sorts de domaine clerc — état persisté ou dérivés de la spécialisation."""
    if character.class_id != "cleric":
        return ()
    stored = get_domain_spells(character)
    if stored:
        return tuple(stored)
    from jdr_engine.rules.spellcasting.preparation import (
        get_domain_spells as domain_at_level,
    )

    domain_id = get_specialization_id(character.choices or {})
    return domain_at_level(domain_id, character.level)


def get_prepared_spell_pool(
    character: Character,
    *,
    engine: RuleEngine,
) -> tuple[str, ...]:
    """
    Pool fermé pour /preparer-sorts.

    PREPARED (clerc, druide, paladin) : liste de classe filtrée par niveau.
    WIZARD_HYBRID : grimoire personnel filtré par niveau (jamais la liste SRD).
    """
    family = get_spellcasting_family(character.class_id)
    if family == SpellcastingFamily.WIZARD_HYBRID:
        book = get_spellbook(character)
        max_level = max_castable_spell_level(character.class_id, character.level)
        return tuple(
            filter_spells_by_max_level(book, max_level, engine=engine)
        )
    return tuple(
        get_filtered_leveled_pool(
            character.class_id,
            character.level,
            engine=engine,
        )
    )


def get_selectable_prepared_pool(
    character: Character,
    *,
    engine: RuleEngine,
) -> tuple[str, ...]:
    """Pool joueur — sorts de domaine clerc exclus (toujours préparés, hors quota)."""
    pool = get_prepared_spell_pool(character, engine=engine)
    if character.class_id == "cleric":
        domain = set(_resolved_domain_spells(character))
        pool = tuple(spell_id for spell_id in pool if spell_id not in domain)
    return pool


def get_player_prepared_quota(character: Character, *, engine: RuleEngine) -> int:
    """Quota SRD — nombre de sorts que le joueur doit choisir (hors domaine clerc)."""
    ability_id = casting_ability_for_class(character.class_id)
    mod = get_effective_ability_modifier(character, engine, ability_id)
    return prepared_capacity_for_class(
        character.class_id,
        mod,
        character.level,
    )


def get_effective_prepared_quota(character: Character, *, engine: RuleEngine) -> int:
    """
    Quota effectif pour la re-préparation.

    Plafonné par la taille du pool curated (compendium partiel — cf. level-up A2).
    """
    srd_quota = get_player_prepared_quota(character, engine=engine)
    selectable = get_selectable_prepared_pool(character, engine=engine)
    if not selectable:
        return srd_quota
    return min(srd_quota, len(selectable))


def prepared_pool_capped_notice(
    character: Character,
    *,
    engine: RuleEngine,
) -> str | None:
    """Message UX quand le catalogue curated est plus petit que le quota SRD."""
    srd_quota = get_player_prepared_quota(character, engine=engine)
    effective = get_effective_prepared_quota(character, engine=engine)
    if effective >= srd_quota:
        return None
    selectable_count = len(get_selectable_prepared_pool(character, engine=engine))
    if character.class_id == "cleric":
        return (
            f"Catalogue partiel — seulement **{selectable_count}** sort(s) "
            f"disponible(s) hors domaine (quota SRD : {srd_quota})."
        )
    return (
        f"Catalogue partiel — seulement **{selectable_count}** sort(s) "
        f"disponible(s) (quota SRD : {srd_quota})."
    )


def paladin_no_slots_notice(character: Character) -> str | None:
    """Message UX paladin niv. 1 — préparés OK, cast impossible."""
    if character.class_id != "paladin" or character.level >= 2:
        return None
    if get_max_spell_slots("paladin", character.level):
        return None
    return (
        "Sorts préparés enregistrés — **aucun emplacement de sort avant le niveau 2**."
    )


def build_prepared_choice_context(
    character: Character,
    *,
    engine: RuleEngine,
) -> PreparedChoiceContext:
    domain = _resolved_domain_spells(character) if character.class_id == "cleric" else ()
    return PreparedChoiceContext(
        character_name=character.name,
        class_id=character.class_id,
        level=character.level,
        pool=get_selectable_prepared_pool(character, engine=engine),
        quota=get_effective_prepared_quota(character, engine=engine),
        srd_quota=get_player_prepared_quota(character, engine=engine),
        domain_spells=domain,
        paladin_no_slots_notice=paladin_no_slots_notice(character),
        pool_capped_notice=prepared_pool_capped_notice(character, engine=engine),
    )


def validate_prepared_selection(
    character: Character,
    engine: RuleEngine,
    selected: list[str] | tuple[str, ...],
    *,
    require_pending: bool = True,
) -> tuple[str, ...]:
    """
    Valide une sélection de sorts préparés (pool fermé, quota strict).

    ``require_pending=False`` : tests / outils internes uniquement.
    """
    if not requires_prepared_rechoice_class(character.class_id):
        raise PreparedChoiceError(
            "Cette classe ne prépare pas ses sorts de cette manière."
        )

    if require_pending and not is_prepared_rechoice_pending(character):
        raise PreparedChoiceError(
            "Re-préparation disponible uniquement après un **repos long**."
        )

    pool = set(get_selectable_prepared_pool(character, engine=engine))
    if not pool:
        if character.class_id == "wizard":
            raise PreparedChoiceError(
                "Aucun sort disponible dans votre grimoire à ce niveau."
            )
        raise PreparedChoiceError(
            "Aucun sort disponible dans le pool de votre classe à ce niveau."
        )

    domain = set(_resolved_domain_spells(character))
    chosen = list(dict.fromkeys(str(spell_id).strip() for spell_id in selected if spell_id))
    quota = get_effective_prepared_quota(character, engine=engine)
    cantrips = set(get_cantrips_known(character))

    if len(chosen) != quota:
        raise PreparedChoiceError(
            f"Choisissez exactement **{quota}** sort(s) préparé(s), "
            f"{len(chosen)} sélectionné(s)."
        )

    invalid_cantrips = [spell_id for spell_id in chosen if spell_id in cantrips]
    if invalid_cantrips:
        raise PreparedChoiceError(
            "Les tours de magie ne font pas partie de la préparation."
        )

    invalid_pool = [spell_id for spell_id in chosen if spell_id not in pool]
    if invalid_pool:
        if character.class_id == "wizard":
            raise PreparedChoiceError(
                f"Sort(s) hors grimoire : {', '.join(invalid_pool)}."
            )
        raise PreparedChoiceError(
            f"Sort(s) hors liste de classe : {', '.join(invalid_pool)}."
        )

    invalid_domain = [spell_id for spell_id in chosen if spell_id in domain]
    if invalid_domain:
        raise PreparedChoiceError(
            "Les sorts de domaine sont toujours préparés — ne les sélectionnez pas."
        )

    for spell_id in chosen:
        if engine.get_entity("spell", spell_id) is None:
            raise PreparedChoiceError(f"Sort inconnu : **{spell_id}**.")

    return tuple(chosen)


def apply_prepared_selection(
    character: Character,
    engine: RuleEngine,
    selected: list[str] | tuple[str, ...],
    *,
    require_pending: bool = True,
) -> Character:
    """Persiste ``spells_prepared`` et efface ``prepared_rechoice_pending``."""
    validated = validate_prepared_selection(
        character,
        engine,
        selected,
        require_pending=require_pending,
    )
    choices = dict(character.choices or {})
    state = dict(get_spellcasting_state(character))
    state["spells_prepared"] = list(validated)
    if character.class_id == "cleric":
        domain_id = get_specialization_id(choices)
        from jdr_engine.rules.spellcasting.preparation import get_domain_spells as domain_at_level

        state["domain_spells"] = list(
            domain_at_level(domain_id, character.level)
        )
    state.pop("prepared_rechoice_pending", None)
    choices["spellcasting"] = state
    character.choices = choices
    return character
