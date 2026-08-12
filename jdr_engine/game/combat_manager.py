# jdr_engine/game/combat_manager.py
"""Orchestration de rencontre — lots C1–C2 (cycle de vie) et C3a (attaque)."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable

from jdr_engine.core.events.bus import EventBus
from jdr_engine.core.events.combat_events import (
    ActionConsumed,
    AttackRollResolved,
    CombatantJoined,
    CombatEnded,
    CombatStarted,
    ConcentrationBroken,
    ConditionApplied,
    ConditionRemoved,
    DamageDealt,
    InitiativeRolled,
    RoundStarted,
    SavingThrowResolved,
    SpellCast,
    TurnEnded,
    TurnStarted,
)
from jdr_engine.dice.d20 import D20Mode, D20RollRequest, D20RollResult, RandInt
from jdr_engine.domain.combat.action_budget import (
    ActionBudgetExhaustedError,
    ActionKind,
    fresh_action_budget,
)
from jdr_engine.domain.combat.combat_state import (
    COMBAT_STATE_VERSION,
    CombatState,
    sql_status_from_combat,
    utc_now_iso,
)
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.domain.combat.active_effect import ActiveEffect
from jdr_engine.persistence.combat_repository import (
    CombatNotFoundError,
    CombatRecord,
    OpenCombatExistsError,
    SqliteCombatRepository,
)
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.combat.attack_roll import AttackHitOutcome, resolve_attack_hit
from jdr_engine.rules.combat.buffs.hunters_mark import roll_hunters_mark_bonus
from jdr_engine.rules.combat.buffs.hex import roll_hex_bonus
from jdr_engine.rules.combat.conditions.catalog import (
    PHASE1_CONDITIONS,
    validate_phase1_condition,
)
from jdr_engine.rules.combat.concentration_save import concentration_save_dc
from jdr_engine.rules.combat.damage import (
    DamageApplicationResult,
    DamageRollResult,
    apply_damage_to_hp,
    roll_damage,
)
from jdr_engine.rules.combat.initiative import (
    InitiativeRollResult,
    insert_combatant_into_initiative_order,
    next_active_turn_index,
    roll_initiative,
    sort_initiative_order,
)
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.effects.registry import ActiveEffectRegistry
from jdr_engine.rules.effects.collect import (
    hex_bonus_applies_for_target,
    hunters_mark_bonus_applies_for_target,
)
from jdr_engine.rules.combat.saving_throw import (
    damage_after_save,
    save_succeeded,
)
from jdr_engine.rules.combat.overlay_cast import (
    OVERLAY_CAST_REGISTRY,
    UPCAST_COMBAT_SPELLS,
)
from jdr_engine.rules.combat.spell_resolution import (
    CombatSpellEffect,
    build_save_request,
    build_spell_attack_request,
    compute_spell_save_dc,
    half_on_save_for_spell,
    load_combat_spell,
    require_spell_attack_type,
    resolve_spell_damage_notation,
    resolve_spell_healing_amount,
    save_ability_for_spell,
    spell_combat_action_kind,
)
from jdr_engine.rules.roll_effects import roll_d20_for_combatant
from jdr_engine.rules.spellcasting.cast import (
    SpellCastError,
    _is_auto_hit_spell,
    cast_spell as resolve_spell_cast,
)
from jdr_engine.rules.spellcasting.state import consume_spell_slot, spell_is_available
from jdr_engine.rules.spellcasting.concentration import (
    clear_concentration,
    get_active_concentration,
    set_concentration,
)


def _is_multi_attack_spell(spell_def: dict, effect: dict) -> bool:
    """Sort avec plusieurs jets d'attaque distincts (ex. rayon ardent)."""
    if _is_auto_hit_spell(spell_def, effect):
        return False
    return int(effect.get("attacks", effect.get("instances", 1))) > 1


def _spell_attack_instances(effect: dict) -> int:
    return max(1, int(effect.get("attacks", effect.get("instances", 1))))


if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Alias rétrocompatibilité.
ActiveCombatExistsError = OpenCombatExistsError


class CombatCharacterNotFoundError(Exception):
    """Personnage requis pour le combat introuvable."""


class CombatStatusError(Exception):
    """Opération interdite pour le statut courant du combat."""


class InsufficientCombatantsError(Exception):
    """Nombre de combattants insuffisant pour l'opération."""


class CombatantNotFoundError(Exception):
    """Combattant introuvable dans la rencontre."""


class NotCombatantTurnError(Exception):
    """Action tentée hors du tour du combattant."""


@dataclass(frozen=True)
class AttackRollResolution:
    """Résultat complet d'un jet d'attaque (sans application des dégâts)."""

    d20: D20RollResult
    outcome: AttackHitOutcome


@dataclass(frozen=True)
class DamageResolution:
    """Résultat d'un jet et d'une application de dégâts."""

    roll: DamageRollResult | None
    application: DamageApplicationResult


@dataclass(frozen=True)
class SpellAttackOutcome:
    """Attaque de sort — jet et dégâts éventuels."""

    spell: CombatSpellEffect
    attack: AttackRollResolution
    damage: DamageResolution | None = None


@dataclass(frozen=True)
class SpellSaveOutcome:
    """Sort à sauvegarde — jet DD, dégâts ajustés."""

    spell: CombatSpellEffect
    save_dc: int
    save_total: int
    succeeded: bool
    damage_roll: DamageRollResult
    damage: DamageResolution


@dataclass(frozen=True)
class SpellAutoHitOutcome:
    """Sort à touché automatique (ex. projectile magique) — dégâts sans jet vs CA."""

    spell: CombatSpellEffect
    damage_total: int
    damage_notation: str
    damage: DamageResolution | None = None


@dataclass(frozen=True)
class SpellMultiAttackOutcome:
    """Attaque de sort multi-projectiles (ex. rayon ardent)."""

    spell: CombatSpellEffect
    attacks: tuple[AttackRollResolution, ...]
    damage: tuple[DamageResolution, ...]


@dataclass(frozen=True)
class SpellHealOutcome:
    """Sort de soins — restauration des PV de la cible."""

    spell: CombatSpellEffect
    healing_total: int
    healing_applied: int
    healing_rolls: tuple[int, ...]
    healing_capped: bool
    hp_before: int
    hp_after: int


class CombatManager:
    """
    Machine de cycle de vie combat — création, initiative, tours, attaque (C3a).

    Publie les événements de cycle sur l'EventBus injecté.
    """

    def __init__(
        self,
        event_bus: EventBus,
        combat_repository: SqliteCombatRepository,
        character_repository: SqliteCharacterRepository,
        engine: RuleEngine,
    ) -> None:
        self._bus = event_bus
        self._combats = combat_repository
        self._characters = character_repository
        self._engine = engine
        self._effect_registries: dict[str, ActiveEffectRegistry] = {}

    def create_combat(
        self,
        guild_id: str,
        channel_id: str,
        character_ids: list[str] | None = None,
    ) -> CombatState:
        """Ouvre un combat en ``preparing`` ; publie ``CombatStarted``."""
        combatants: dict[str, Combatant] = {}
        resolved_character_ids: list[str] = []

        for character_id in character_ids or []:
            combatant = self._build_combatant(character_id)
            combatants[combatant.combatant_id] = combatant
            resolved_character_ids.append(character_id)

        state = CombatState(
            schema_version=COMBAT_STATE_VERSION,
            ruleset_id=self._engine.ruleset_id,
            round_number=0,
            turn_index=0,
            initiative_order=(),
            combatants=combatants,
            status="preparing",
            started_at=utc_now_iso(),
            guild_id=str(guild_id),
            channel_id=str(channel_id),
        )

        combat_id = self._combats.insert(guild_id, channel_id, state)
        state.combat_id = str(combat_id)

        self._bus.publish(
            CombatStarted(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id,
                guild_id=str(guild_id),
                channel_id=str(channel_id),
                character_ids=tuple(resolved_character_ids),
            )
        )
        return state

    def add_combatant(
        self,
        combat_id: int,
        character_id: str,
        *,
        rng: Callable[[], int] | None = None,
    ) -> CombatState:
        """
        Ajoute un PJ en ``preparing`` ou en ``active`` (initiative + ordre figé).

        En combat actif, l'index de tour continue de désigner le même combattant.
        """
        state = self._require_state(combat_id)
        if state.status == "ended":
            raise CombatStatusError("Combat déjà terminé.")
        for existing in state.combatants.values():
            if existing.character_id == character_id:
                raise CombatStatusError(
                    f"Le personnage {character_id!r} participe déjà à cette rencontre."
                )

        combatant = self._build_combatant(character_id)

        if state.status == "preparing":
            state.combatants[combatant.combatant_id] = combatant
            self._persist(state)
            return state

        if state.status != "active":
            raise CombatStatusError(
                "Les combattants ne peuvent être ajoutés qu'en préparation ou "
                "pendant un combat actif."
            )
        if not state.initiative_order:
            raise CombatStatusError("Aucune séquence d'initiative établie.")

        character = self._require_character(character_id)
        sheet = build_character_sheet(character, self._engine)
        roll = roll_initiative(combatant.combatant_id, sheet.initiative, rng=rng)
        combatant = replace(combatant, initiative_total=roll.total)

        current_turn_id = state.initiative_order[state.turn_index]
        initiative_totals = {
            cid: int(state.combatants[cid].initiative_total or 0)
            for cid in state.initiative_order
        }
        new_order = insert_combatant_into_initiative_order(
            state.initiative_order,
            combatant.combatant_id,
            roll.total,
            initiative_totals=initiative_totals,
        )
        inserted_at = new_order.index(combatant.combatant_id)

        state.combatants[combatant.combatant_id] = combatant
        state.initiative_order = new_order
        state.turn_index = new_order.index(current_turn_id)
        self._persist(state)

        self._bus.publish(
            CombatantJoined(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=combatant.combatant_id,
                character_id=character_id,
                initiative_order=new_order,
                inserted_at_index=inserted_at,
            )
        )
        return state

    def activate_combat(
        self,
        combat_id: int,
        *,
        rng: Callable[[], int] | None = None,
    ) -> CombatState:
        """
        Passe en ``active``, calcule l'initiative (ordre figé), démarre le tour 1.

        Requiert au moins deux combattants actifs.
        """
        state = self._require_state(combat_id)
        if state.status != "preparing":
            raise CombatStatusError(
                "Seul un combat en préparation peut être activé."
            )
        active = [c for c in state.combatants.values() if c.is_active]
        if len(active) < 2:
            raise InsufficientCombatantsError(
                "Au moins deux combattants sont requis pour activer le combat."
            )

        rolls = self._roll_initiative_for_combatants(active, rng=rng)
        order = sort_initiative_order(rolls)
        roll_by_id = {r.combatant_id: r for r in rolls}

        updated_combatants = dict(state.combatants)
        for combatant_id, roll in roll_by_id.items():
            old = updated_combatants[combatant_id]
            updated_combatants[combatant_id] = replace(
                old, initiative_total=roll.total
            ).with_action_budget(fresh_action_budget())

        state.combatants = updated_combatants
        state.initiative_order = order
        state.status = "active"
        state.round_number = 1
        state.turn_index = 0
        self._persist(state)

        record = self._combats.get_by_id(combat_id)
        assert record is not None
        self._publish_initiative_events(record, rolls, order)
        self._publish_turn_started(state)
        return state

    def advance_turn(self, combat_id: int) -> CombatState:
        """Termine le tour courant et démarre le suivant (combattants inactifs ignorés)."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError(
                "L'avancement de tour n'est possible qu'en combat actif."
            )
        if not state.initiative_order:
            raise CombatStatusError("Aucune séquence d'initiative établie.")

        current_id = state.initiative_order[state.turn_index]
        self._bus.publish(
            TurnEnded(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=current_id,
                round_number=state.round_number,
                turn_index=state.turn_index,
            )
        )

        def _is_active(combatant_id: str) -> bool:
            return state.combatants[combatant_id].is_active

        result = next_active_turn_index(
            state.initiative_order,
            state.turn_index,
            is_active=_is_active,
        )
        if result is None:
            return self.close_combat(
                combat_id, reason="no_active_combatants"
            )

        new_index, delta_round = result
        if delta_round:
            state.round_number += 1
            self._tick_active_effects(combat_id, state.round_number)
            self._bus.publish(
                RoundStarted(
                    ruleset_id=state.ruleset_id,
                    combat_id=state.combat_id or str(combat_id),
                    guild_id=state.guild_id or "",
                    channel_id=state.channel_id or "",
                    round_number=state.round_number,
                )
            )
        state.turn_index = new_index
        self._persist(state)
        self._publish_turn_started(state)
        return state

    def remove_combatant(self, combat_id: int, combatant_id: str) -> CombatState:
        """Marque un combattant inactif ; conserve sa place dans l'initiative."""
        state = self._require_state(combat_id)
        if state.status == "ended":
            raise CombatStatusError("Combat déjà terminé.")
        if combatant_id not in state.combatants:
            raise ValueError(f"Combattant introuvable : {combatant_id!r}.")
        old = state.combatants[combatant_id]
        state.combatants[combatant_id] = replace(old, is_active=False)
        self._persist(state)
        return state

    def apply_condition(
        self,
        combat_id: int,
        combatant_id: str,
        condition_id: str,
    ) -> CombatState:
        """Applique une condition phase 1 via le registre d'effets actifs."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError(
                "Les conditions ne s'appliquent qu'en combat actif."
            )
        normalized = validate_phase1_condition(condition_id)
        self._require_combatant(state, combatant_id)
        if self.query_active_effects(
            combat_id,
            effect_id=normalized,
            target_id=combatant_id,
            source_id=normalized,
        ):
            return state

        self._add_manual_condition_effect(
            combat_id,
            condition_id=normalized,
            target_id=combatant_id,
            applied_at_round=state.round_number,
        )
        state = self._require_state(combat_id)
        self._persist(state)
        self._bus.publish(
            ConditionApplied(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=combatant_id,
                condition_id=normalized,
            )
        )
        return state

    def remove_condition(
        self,
        combat_id: int,
        combatant_id: str,
        condition_id: str,
    ) -> CombatState:
        """Retire une condition phase 1 du registre (seul chemin de sortie en C6)."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError(
                "Les conditions ne se retirent qu'en combat actif."
            )
        normalized = validate_phase1_condition(condition_id)
        self._require_combatant(state, combatant_id)
        if not self.query_active_effects(
            combat_id,
            effect_id=normalized,
            target_id=combatant_id,
            source_id=normalized,
        ):
            raise ValueError(
                f"Le combattant {combatant_id!r} n'a pas la condition {normalized!r}."
            )

        self._registry_for(combat_id).remove_matching(
            effect_id=normalized,
            source_id=normalized,
            target_id=combatant_id,
        )
        self._persist(state)
        self._bus.publish(
            ConditionRemoved(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=combatant_id,
                condition_id=normalized,
            )
        )
        return state

    def resolve_attack_roll(
        self,
        combat_id: int,
        attacker_id: str,
        target_id: str,
        request: D20RollRequest,
        *,
        rng: RandInt | None = None,
        consume_action: bool = True,
    ) -> AttackRollResolution:
        """
        Résout un jet d'attaque vs la CA cible — sans modifier les PV.

        Délègue le d20 à ``roll_d20_for_character`` (moteur de jets existant).
        Publie ``AttackRollResolved``.
        """
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError(
                "Les attaques ne sont possibles qu'en combat actif."
            )
        if request.roll_type != "attack":
            raise ValueError("roll_type doit être 'attack' pour un jet d'attaque.")

        if consume_action:
            self._consume_budget(combat_id, attacker_id, "action")

        state = self._require_state(combat_id)
        attacker = self._require_combatant(state, attacker_id)
        target = self._require_combatant(state, target_id)
        character = self._require_character(attacker.character_id)

        registry = self._registry_for(combat_id)
        d20 = roll_d20_for_combatant(
            request, character, attacker, self._engine,
            effect_registry=registry,
            defender_id=target_id,
            rng=rng,
        )
        outcome = resolve_attack_hit(d20, target.ac)

        self._bus.publish(
            AttackRollResolved(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                attacker_id=attacker_id,
                target_id=target_id,
                target_ac=target.ac,
                hit=outcome.hit,
                critical=outcome.critical,
                automatic_miss=outcome.automatic_miss,
                attack_total=d20.total,
                kept_d20=d20.kept_value,
            )
        )
        return AttackRollResolution(d20=d20, outcome=outcome)

    def apply_damage(
        self,
        combat_id: int,
        target_id: str,
        damage_notation: str = "",
        *,
        damage_amount: int | None = None,
        critical: bool = False,
        source_id: str | None = None,
        rng: RandInt | None = None,
        dice_notation_label: str | None = None,
        spell_damage: bool = False,
    ) -> tuple[CombatState, DamageResolution]:
        """
        Applique des dégâts aux PV du combattant (overlay).

        Soit ``damage_notation`` (jet de dés), soit ``damage_amount`` (montant fixe).
        ``spell_damage=True`` active les bonus réservés aux dégâts de sort (ex. maléfice).
        Publie ``DamageDealt``. Persiste l'état combat.
        """
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError(
                "Les dégâts ne s'appliquent qu'en combat actif."
            )
        target = self._require_combatant(state, target_id)
        if source_id is not None:
            self._require_combatant(state, source_id)

        registry = self._registry_for(combat_id)

        if damage_amount is not None:
            if damage_amount < 0:
                raise ValueError("Les dégâts ne peuvent pas être négatifs.")
            damage_roll = None
            amount = damage_amount
            notation = dice_notation_label or str(damage_amount)
        else:
            if not damage_notation:
                raise ValueError(
                    "damage_notation ou damage_amount requis pour apply_damage."
                )
            damage_roll = roll_damage(damage_notation, critical=critical, rng=rng)
            amount = damage_roll.total
            notation = damage_roll.dice_notation

        if amount > 0 and hunters_mark_bonus_applies_for_target(
            registry, target_id, source_id
        ):
            mark_bonus = roll_hunters_mark_bonus(rng=rng)
            amount += mark_bonus
            notation = f"{notation}+{mark_bonus} (hunters_mark)"

        if spell_damage and amount > 0 and hex_bonus_applies_for_target(
            registry, target_id, source_id
        ):
            hex_bonus = roll_hex_bonus(rng=rng)
            amount += hex_bonus
            notation = f"{notation}+{hex_bonus} (hex)"

        application = apply_damage_to_hp(target.hp_current, amount)

        state.combatants[target_id] = target.with_hp(application.hp_after)
        self._persist(state)

        self._bus.publish(
            DamageDealt(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                source_id=source_id,
                target_id=target_id,
                damage=application.damage_dealt,
                hp_before=application.hp_before,
                hp_after=application.hp_after,
                critical=critical,
                dice_notation=notation,
            )
        )
        state = self._resolve_concentration_after_damage(
            state,
            combat_id,
            target_id,
            application.damage_dealt,
            rng=rng,
        )
        return state, DamageResolution(roll=damage_roll, application=application)

    def cast_spell_attack(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        spell_id: str,
        *,
        base_mode: D20Mode = "normal",
        rng: RandInt | None = None,
        locale: str = "fr",
    ) -> tuple[CombatState, SpellAttackOutcome]:
        """Attaque de sort — réutilise ``resolve_attack_hit`` et ``apply_damage``."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)

        spell = load_combat_spell(self._engine, spell_id, locale=locale)
        if spell.effect_type != "spell_attack":
            raise SpellCastError(f"{spell_id!r} n'est pas une attaque de sort.")

        action_kind = spell_combat_action_kind(spell, locale=locale)
        self._consume_budget(combat_id, caster_id, action_kind)

        updated_char = consume_spell_slot(caster_char, spell.spell_level)
        self._characters.save(updated_char)

        state = self._require_state(combat_id)
        self._publish_spell_cast(state, caster_id, spell, (target_id,))

        request = build_spell_attack_request(
            caster_char,
            self._engine,
            base_mode=base_mode,
            attack_type=require_spell_attack_type(spell),
        )
        attack = self.resolve_attack_roll(
            combat_id, caster_id, target_id, request, rng=rng, consume_action=False
        )

        damage_resolution = None
        state = self._require_state(combat_id)
        if attack.outcome.hit:
            notation = resolve_spell_damage_notation(
                spell, caster_char, self._engine
            )
            state, damage_resolution = self.apply_damage(
                combat_id,
                target_id,
                notation,
                critical=attack.outcome.critical,
                source_id=caster_id,
                rng=rng,
                spell_damage=True,
            )

        return state, SpellAttackOutcome(
            spell=spell,
            attack=attack,
            damage=damage_resolution,
        )

    def cast_spell_save(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        spell_id: str,
        *,
        rng: RandInt | None = None,
        locale: str = "fr",
    ) -> tuple[CombatState, SpellSaveOutcome]:
        """Sort à sauvegarde — DD calculé, moitié des dégâts si réussite."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        target = self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)
        target_char = self._require_character(target.character_id)

        spell = load_combat_spell(self._engine, spell_id, locale=locale)
        if spell.effect_type != "saving_throw":
            raise SpellCastError(f"{spell_id!r} n'est pas un sort à sauvegarde.")

        action_kind = spell_combat_action_kind(spell, locale=locale)
        self._consume_budget(combat_id, caster_id, action_kind)

        updated_char = consume_spell_slot(caster_char, spell.spell_level)
        self._characters.save(updated_char)

        state = self._require_state(combat_id)
        self._publish_spell_cast(state, caster_id, spell, (target_id,))

        notation = resolve_spell_damage_notation(spell, caster_char, self._engine)
        damage_roll = roll_damage(notation, rng=rng)
        save_dc = compute_spell_save_dc(caster_char, self._engine)
        save_ability = save_ability_for_spell(spell)
        save_request = build_save_request(
            target_char, self._engine, save_ability
        )
        registry = self._registry_for(combat_id)
        d20 = roll_d20_for_combatant(
            save_request, target_char, target, self._engine,
            effect_registry=registry,
            rng=rng,
        )
        succeeded = save_succeeded(d20.total, save_dc)
        half = half_on_save_for_spell(spell)
        final_damage = damage_after_save(
            damage_roll.total,
            save_succeeded_flag=succeeded,
            half_on_save=half,
        )

        state = self._require_state(combat_id)
        self._bus.publish(
            SavingThrowResolved(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                caster_id=caster_id,
                target_id=target_id,
                spell_id=spell_id,
                save_ability=save_ability,
                save_dc=save_dc,
                save_total=d20.total,
                succeeded=succeeded,
                damage_before_save=damage_roll.total,
                damage_applied=final_damage,
            )
        )

        state, damage_resolution = self.apply_damage(
            combat_id,
            target_id,
            damage_amount=final_damage,
            source_id=caster_id,
            dice_notation_label=f"{notation} → {final_damage}",
            spell_damage=True,
        )

        return state, SpellSaveOutcome(
            spell=spell,
            save_dc=save_dc,
            save_total=d20.total,
            succeeded=succeeded,
            damage_roll=damage_roll,
            damage=damage_resolution,
        )

    def cast_spell_auto_hit(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        spell_id: str,
        *,
        rng: RandInt | None = None,
        locale: str = "fr",
    ) -> tuple[CombatState, SpellAutoHitOutcome]:
        """Sort à touché automatique — dégâts sans jet d'attaque vs CA."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)

        spell = load_combat_spell(self._engine, spell_id, locale=locale)
        if spell.effect_type != "spell_attack":
            raise SpellCastError(f"{spell_id!r} n'est pas une attaque de sort.")
        if not _is_auto_hit_spell(spell.spell_def, spell.effect):
            raise SpellCastError(
                f"{spell_id!r} n'est pas un sort à touché automatique."
            )

        action_kind = spell_combat_action_kind(spell, locale=locale)
        self._consume_budget(combat_id, caster_id, action_kind)

        updated_char = consume_spell_slot(caster_char, spell.spell_level)
        self._characters.save(updated_char)

        state = self._require_state(combat_id)
        self._publish_spell_cast(state, caster_id, spell, (target_id,))

        result = resolve_spell_cast(
            updated_char,
            spell_id,
            self._engine,
            rng=rng,
            persist_slots=False,
            locale=locale,
        )

        damage_resolution = None
        state = self._require_state(combat_id)
        damage_total = result.damage_total or 0
        if damage_total > 0:
            notation = result.damage_notation or str(damage_total)
            state, damage_resolution = self.apply_damage(
                combat_id,
                target_id,
                damage_amount=damage_total,
                source_id=caster_id,
                dice_notation_label=notation,
                spell_damage=True,
            )

        return state, SpellAutoHitOutcome(
            spell=spell,
            damage_total=damage_total,
            damage_notation=result.damage_notation or "",
            damage=damage_resolution,
        )

    def cast_spell_multi_attack(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        spell_id: str,
        *,
        base_mode: D20Mode = "normal",
        rng: RandInt | None = None,
        locale: str = "fr",
    ) -> tuple[CombatState, SpellMultiAttackOutcome]:
        """Attaque de sort à plusieurs projectiles — un jet vs CA par rayon."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)

        spell = load_combat_spell(self._engine, spell_id, locale=locale)
        if spell.effect_type != "spell_attack":
            raise SpellCastError(f"{spell_id!r} n'est pas une attaque de sort.")
        if not _is_multi_attack_spell(spell.spell_def, spell.effect):
            raise SpellCastError(f"{spell_id!r} n'est pas un sort multi-attaque.")

        instances = _spell_attack_instances(spell.effect)
        action_kind = spell_combat_action_kind(spell, locale=locale)
        self._consume_budget(combat_id, caster_id, action_kind)

        updated_char = consume_spell_slot(caster_char, spell.spell_level)
        self._characters.save(updated_char)

        state = self._require_state(combat_id)
        self._publish_spell_cast(state, caster_id, spell, (target_id,))

        request = build_spell_attack_request(
            caster_char,
            self._engine,
            base_mode=base_mode,
            attack_type=require_spell_attack_type(spell),
        )
        notation = resolve_spell_damage_notation(spell, caster_char, self._engine)

        attacks: list[AttackRollResolution] = []
        damages: list[DamageResolution] = []
        for _index in range(instances):
            attack = self.resolve_attack_roll(
                combat_id,
                caster_id,
                target_id,
                request,
                rng=rng,
                consume_action=False,
            )
            attacks.append(attack)
            if attack.outcome.hit:
                state, damage_resolution = self.apply_damage(
                    combat_id,
                    target_id,
                    notation,
                    critical=attack.outcome.critical,
                    source_id=caster_id,
                    rng=rng,
                    spell_damage=True,
                )
                damages.append(damage_resolution)

        state = self._require_state(combat_id)
        return state, SpellMultiAttackOutcome(
            spell=spell,
            attacks=tuple(attacks),
            damage=tuple(damages),
        )

    def cast_spell_heal(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        spell_id: str,
        *,
        rng: RandInt | None = None,
        locale: str = "fr",
    ) -> tuple[CombatState, SpellHealOutcome]:
        """Sort de soins — restaure les PV de la cible touchée."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        target = self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)

        spell = load_combat_spell(self._engine, spell_id, locale=locale)
        if spell.effect_type != "healing":
            raise SpellCastError(f"{spell_id!r} n'est pas un sort de soins.")

        action_kind = spell_combat_action_kind(spell, locale=locale)
        self._consume_budget(combat_id, caster_id, action_kind)

        updated_char = consume_spell_slot(caster_char, spell.spell_level)
        self._characters.save(updated_char)

        state = self._require_state(combat_id)
        self._publish_spell_cast(state, caster_id, spell, (target_id,))

        heal_total, heal_rolls, _notation = resolve_spell_healing_amount(
            spell, updated_char, self._engine, rng=rng
        )
        hp_before = target.hp_current
        hp_after = min(target.hp_max, hp_before + heal_total)
        healing_applied = hp_after - hp_before
        capped = healing_applied < heal_total

        state.combatants[target_id] = target.with_hp(hp_after)
        self._persist(state)
        self._sync_character_from_combatant(state.combatants[target_id])

        return self._require_state(combat_id), SpellHealOutcome(
            spell=spell,
            healing_total=heal_total,
            healing_applied=healing_applied,
            healing_rolls=tuple(heal_rolls),
            healing_capped=capped,
            hp_before=hp_before,
            hp_after=hp_after,
        )

    def heal_combatant(
        self,
        combat_id: int,
        combatant_id: str,
        *,
        hp_current: int | None = None,
    ) -> CombatState:
        """Outil MJ — restaure les PV du combattant et synchronise la fiche."""
        state = self._require_state(combat_id)
        combatant = self._require_combatant(state, combatant_id)
        if hp_current is None:
            new_hp = combatant.hp_max
        else:
            new_hp = min(max(1, hp_current), combatant.hp_max)

        updated = combatant.with_hp(new_hp)
        state.combatants[combatant_id] = updated
        self._persist(state)
        self._sync_character_from_combatant(updated)
        return self._require_state(combat_id)

    def refresh_combatant_from_sheet(
        self,
        combat_id: int,
        combatant_id: str,
    ) -> CombatState:
        """Outil MJ — réaligne l'overlay combat sur la fiche persistante."""
        state = self._require_state(combat_id)
        combatant = self._require_combatant(state, combatant_id)
        character = self._require_character(combatant.character_id)
        sheet = build_character_sheet(character, self._engine)
        updated = replace(
            combatant,
            hp_current=sheet.hp_current,
            hp_max=sheet.hp_max,
            ac=sheet.ac,
            is_active=sheet.hp_current > 0,
        )
        state.combatants[combatant_id] = updated
        self._persist(state)
        return self._require_state(combat_id)

    def cast_hunters_mark(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        *,
        locale: str = "fr",
    ) -> CombatState:
        """Pose la concentration et marque la cible (overlay combat)."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)

        spell = load_combat_spell(self._engine, "hunters_mark", locale=locale)
        self._consume_budget(combat_id, caster_id, "bonus_action")

        state = self._require_state(combat_id)
        caster = self._require_combatant(state, caster_id)
        previous_spell_id = caster.concentration_spell_id
        if previous_spell_id and previous_spell_id != spell.spell_id:
            state = self._clear_concentration_spell_overlay_effects(
                state, caster_id, previous_spell_id
            )
        state = self._clear_hunters_marks_from_caster(state, caster_id)

        self._publish_spell_cast(state, caster_id, spell, (target_id,))

        updated_char, _interrupted = set_concentration(
            caster_char, spell.spell_id, spell.spell_name
        )
        self._characters.save(updated_char)

        state.combatants[caster_id] = caster.with_concentration(
            spell.spell_id, spell.spell_name
        )
        self._add_concentration_effect(
            combat_id,
            effect_id="hunters_mark",
            source_id=caster_id,
            target_id=target_id,
            applied_at_round=state.round_number,
        )
        self._persist(state)
        return self._require_state(combat_id)

    def cast_bless(
        self,
        combat_id: int,
        caster_id: str,
        target_ids: list[str],
        *,
        locale: str = "fr",
    ) -> CombatState:
        """Bénédiction — concentration + buff overlay sur jusqu'à 3 cibles."""
        if len(target_ids) > 3:
            raise ValueError("Bénédiction : maximum 3 cibles (SRD 2014).")

        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        for target_id in target_ids:
            self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)

        spell = load_combat_spell(self._engine, "bless", locale=locale)
        self._consume_budget(combat_id, caster_id, "action")

        state = self._require_state(combat_id)
        caster = self._require_combatant(state, caster_id)
        previous_spell_id = caster.concentration_spell_id
        if previous_spell_id and previous_spell_id != spell.spell_id:
            state = self._clear_concentration_spell_overlay_effects(
                state, caster_id, previous_spell_id
            )

        self._publish_spell_cast(
            state, caster_id, spell, tuple(target_ids)
        )

        updated_char, _interrupted = set_concentration(
            caster_char, spell.spell_id, spell.spell_name
        )
        self._characters.save(updated_char)

        state.combatants[caster_id] = caster.with_concentration(
            spell.spell_id, spell.spell_name
        )
        for target_id in target_ids:
            self._add_concentration_effect(
                combat_id,
                effect_id="blessed",
                source_id=caster_id,
                target_id=target_id,
                applied_at_round=state.round_number,
            )
        self._persist(state)
        return self._require_state(combat_id)

    def cast_hex(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        *,
        locale: str = "fr",
    ) -> CombatState:
        """Pose la concentration et maudit la cible (overlay combat)."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)

        spell = load_combat_spell(self._engine, "hex", locale=locale)
        self._consume_budget(combat_id, caster_id, "action")

        state = self._require_state(combat_id)
        caster = self._require_combatant(state, caster_id)
        previous_spell_id = caster.concentration_spell_id
        if previous_spell_id and previous_spell_id != spell.spell_id:
            state = self._clear_concentration_spell_overlay_effects(
                state, caster_id, previous_spell_id
            )
        state = self._clear_hex_from_caster(state, caster_id)

        self._publish_spell_cast(state, caster_id, spell, (target_id,))

        updated_char, _interrupted = set_concentration(
            caster_char, spell.spell_id, spell.spell_name
        )
        self._characters.save(updated_char)

        state.combatants[caster_id] = caster.with_concentration(
            spell.spell_id, spell.spell_name
        )
        self._add_concentration_effect(
            combat_id,
            effect_id="hexed",
            source_id=caster_id,
            target_id=target_id,
            applied_at_round=state.round_number,
        )
        self._persist(state)
        return self._require_state(combat_id)

    def cast_shield(
        self,
        combat_id: int,
        caster_id: str,
        *,
        locale: str = "fr",
    ) -> CombatState:
        """
        Banc de test B4f — horloge ``rounds`` via le sort curated ``shield``.

        Approximation de banc : ``duration_rounds=1`` fixe depuis le round de cast.
        N'implémente ni le +5 CA ; consomme réaction (hors tour propre) et
        emplacement niv. 1. Usage interne / tests — aucune surface MJ.
        """
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        caster_char = self._require_character(caster.character_id)
        if not spell_is_available(caster_char, "shield"):
            raise SpellCastError("Le sort shield n'est pas disponible sur la fiche.")

        if self._current_turn_combatant_id(state) == caster_id:
            raise NotCombatantTurnError(
                "Shield ne peut être lancé qu'en réaction, hors du tour propre."
            )

        self._consume_budget(
            combat_id,
            caster_id,
            "reaction",
            require_own_turn=False,
        )

        spell = load_combat_spell(self._engine, "shield", locale=locale)
        updated_char = consume_spell_slot(caster_char, spell.spell_level)
        self._characters.save(updated_char)

        state = self._require_state(combat_id)
        caster = self._require_combatant(state, caster_id)
        self._publish_spell_cast(state, caster_id, spell, (caster_id,))

        registry = self._registry_for(combat_id)
        registry.remove_matching(
            effect_id="shielded",
            source_id=caster_id,
            target_id=caster_id,
        )
        self.add_active_effect(
            combat_id,
            ActiveEffect(
                effect_id="shielded",
                source_id=caster_id,
                target_id=caster_id,
                applied_at_round=state.round_number,
                expiry_mode="rounds",
                duration_rounds=1,
            ),
        )
        self._persist(state)
        return self._require_state(combat_id)

    def cast_spell(
        self,
        combat_id: int,
        caster_id: str,
        spell_id: str,
        target_ids: list[str],
        *,
        slot_level: int | None = None,
        locale: str = "fr",
        rng: RandInt | None = None,
    ) -> CombatState:
        """
        Lance un sort en combat — dispatch unifié overlay, attaque ou sauvegarde.

        Les sorts overlay (registre ADR-006) délèguent aux méthodes dédiées ;
        les autres sont routés via ``load_combat_spell`` et ``effect_type``.
        """
        state = self._require_state(combat_id)
        if spell_id in OVERLAY_CAST_REGISTRY:
            spec = OVERLAY_CAST_REGISTRY[spell_id]
            if state.status != "active":
                raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")
            if slot_level is not None and spell_id not in UPCAST_COMBAT_SPELLS:
                raise SpellCastError(
                    f"slot_level non pris en charge pour {spell_id!r} en combat."
                )
            count = len(target_ids)
            if count < spec.min_targets or count > spec.max_targets:
                raise SpellCastError(
                    f"Sort {spell_id!r} : entre {spec.min_targets} et "
                    f"{spec.max_targets} cible(s) attendue(s), {count} reçue(s)."
                )
            caster_char = self._require_character(
                self._require_combatant(state, caster_id).character_id
            )
            if not spell_is_available(caster_char, spell_id):
                raise SpellCastError(
                    f"Le sort {spell_id!r} n'est pas disponible sur la fiche."
                )
            is_own_turn = self._current_turn_combatant_id(state) == caster_id
            if spec.require_own_turn and not is_own_turn:
                raise NotCombatantTurnError(
                    f"Seul le combattant actif peut lancer {spell_id!r}."
                )
            if not spec.require_own_turn and is_own_turn:
                raise NotCombatantTurnError(
                    f"Le sort {spell_id!r} n'est lançable qu'en réaction, "
                    "hors du tour propre."
                )
            if spell_id == "hunters_mark":
                return self.cast_hunters_mark(
                    combat_id, caster_id, target_ids[0], locale=locale
                )
            if spell_id == "bless":
                return self.cast_bless(
                    combat_id, caster_id, target_ids, locale=locale
                )
            if spell_id == "hex":
                return self.cast_hex(
                    combat_id, caster_id, target_ids[0], locale=locale
                )
            if spell_id == "shield":
                return self.cast_shield(combat_id, caster_id, locale=locale)

        if slot_level is not None:
            raise SpellCastError(
                f"slot_level non pris en charge pour {spell_id!r} en combat."
            )

        spell = load_combat_spell(self._engine, spell_id, locale=locale)
        if spell.effect_type == "spell_attack":
            if len(target_ids) != 1:
                raise SpellCastError(
                    f"Attaque de sort : exactement 1 cible attendue, "
                    f"{len(target_ids)} reçue(s)."
                )
            if _is_auto_hit_spell(spell.spell_def, spell.effect):
                state, _outcome = self.cast_spell_auto_hit(
                    combat_id,
                    caster_id,
                    target_ids[0],
                    spell_id,
                    locale=locale,
                    rng=rng,
                )
                return state
            if _is_multi_attack_spell(spell.spell_def, spell.effect):
                state, _outcome = self.cast_spell_multi_attack(
                    combat_id,
                    caster_id,
                    target_ids[0],
                    spell_id,
                    locale=locale,
                    rng=rng,
                )
                return state
            state, _outcome = self.cast_spell_attack(
                combat_id,
                caster_id,
                target_ids[0],
                spell_id,
                locale=locale,
                rng=rng,
            )
            return state
        if spell.effect_type == "saving_throw":
            if len(target_ids) != 1:
                raise SpellCastError(
                    f"Sort à sauvegarde : exactement 1 cible attendue, "
                    f"{len(target_ids)} reçue(s)."
                )
            state, _outcome = self.cast_spell_save(
                combat_id,
                caster_id,
                target_ids[0],
                spell_id,
                locale=locale,
                rng=rng,
            )
            return state
        if spell.effect_type == "healing":
            if len(target_ids) != 1:
                raise SpellCastError(
                    f"Sort de soins : exactement 1 cible attendue, "
                    f"{len(target_ids)} reçue(s)."
                )
            state, _outcome = self.cast_spell_heal(
                combat_id,
                caster_id,
                target_ids[0],
                spell_id,
                locale=locale,
                rng=rng,
            )
            return state
        raise SpellCastError(
            f"Sort {spell_id!r} : effet {spell.effect_type!r} non lançable "
            f"via cast combat."
        )

    def consume_reaction(self, combat_id: int, combatant_id: str) -> CombatState:
        """Consomme la réaction hors du tour propre du combattant."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Combat non actif.")
        if self._current_turn_combatant_id(state) == combatant_id:
            raise NotCombatantTurnError(
                "La réaction n'est consommable que hors du tour propre du combattant."
            )
        self._consume_budget(
            combat_id,
            combatant_id,
            "reaction",
            require_own_turn=False,
        )
        return self._require_state(combat_id)

    def active_effect_registry(self, combat_id: int) -> ActiveEffectRegistry:
        """Registre in-memory des effets actifs pour une rencontre."""
        return self._registry_for(combat_id)

    def add_active_effect(self, combat_id: int, effect: ActiveEffect) -> None:
        """Enregistre un effet actif (API publique — lot ADR-006)."""
        self._registry_for(combat_id).add(effect)

    def remove_active_effect(self, combat_id: int, effect: ActiveEffect) -> bool:
        """Retire un effet actif par identité stable."""
        return self._registry_for(combat_id).remove(effect)

    def query_active_effects(
        self,
        combat_id: int,
        *,
        effect_id: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> tuple[ActiveEffect, ...]:
        """Interroge le registre d'effets actifs."""
        return self._registry_for(combat_id).query(
            effect_id=effect_id,
            source_id=source_id,
            target_id=target_id,
        )

    def load_combat(self, combat_id: int) -> CombatState:
        """Charge un combat par identifiant SQL et reconstruit le registre d'effets."""
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        state = record.state
        if state.status == "ended":
            return state

        updated: dict[str, Combatant] = {}
        changed = False
        for combatant_id, combatant in state.combatants.items():
            hydrated = self._hydrate_combatant_concentration(combatant)
            updated[combatant_id] = hydrated
            if hydrated is not combatant:
                changed = True
        if changed:
            state = replace(state, combatants=updated)
        self._sync_effect_registry_from_state(combat_id, state, force=True)
        raw_blob = self._combats.get_state_blob(combat_id)
        if raw_blob is not None and self._hydrate_legacy_combatant_conditions(
            combat_id, state, raw_blob
        ):
            state = self._require_state(combat_id)
            rehydrated: dict[str, Combatant] = {}
            for combatant_id, combatant in state.combatants.items():
                rehydrated[combatant_id] = self._hydrate_combatant_concentration(
                    combatant
                )
            state = replace(state, combatants=rehydrated)
        return self._with_registry_effects(state)

    def load_open_combat(
        self,
        guild_id: str,
        channel_id: str,
    ) -> CombatState | None:
        """Retourne le combat ouvert (preparing ou active) du salon, ou ``None``."""
        record = self._combats.get_open_by_channel(guild_id, channel_id)
        if record is None:
            return None
        return record.state

    def load_active_combat(
        self,
        guild_id: str,
        channel_id: str,
    ) -> CombatState | None:
        """Alias C1 — combat ouvert (preparing ou active)."""
        return self.load_open_combat(guild_id, channel_id)

    def save_combat(self, state: CombatState) -> None:
        """Persiste l'état complet du combat (blob JSON)."""
        if state.combat_id is None:
            raise ValueError("combat_id requis pour sauvegarder.")
        combat_id = int(state.combat_id)
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        sql_status = sql_status_from_combat(state.status)
        self._combats.save(
            CombatRecord(
                combat_id=combat_id,
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                sql_status=sql_status,
                state=state,
            )
        )

    def close_combat(self, combat_id: int, *, reason: str = "closed") -> CombatState:
        """Clôture un combat ouvert ; sync fiche puis publie ``CombatEnded`` (ADR-005).

        ``reason`` est transmis tel quel à ``CombatEnded``. Valeurs canoniques moteur :
        ``"closed"`` (défaut, clôture manuelle) ;
        ``"no_active_combatants"`` (auto-close ``advance_turn``, ADR-005 §5).
        """
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        if record.state.status == "ended":
            return record.state

        state = record.state
        self._sync_effect_registry_from_state(combat_id, state, force=True)
        for combatant in state.combatants.values():
            self._sync_character_from_combatant(combatant)

        state = replace(
            state,
            status="ended",
            ended_at=utc_now_iso(),
            active_effects=self._registry_for(combat_id).all_effects(),
        )

        self._combats.save(
            CombatRecord(
                combat_id=record.combat_id,
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                sql_status="ended",
                state=state,
            )
        )

        self._bus.publish(
            CombatEnded(
                ruleset_id=state.ruleset_id,
                combat_id=str(combat_id),
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                reason=reason,
            )
        )
        self._effect_registries.pop(str(combat_id), None)
        return state

    def _resolve_concentration_after_damage(
        self,
        state: CombatState,
        combat_id: int,
        target_id: str,
        damage_dealt: int,
        *,
        rng: RandInt | None = None,
    ) -> CombatState:
        """Save CON après dégâts si la cible concentre un sort (lot C5)."""
        if damage_dealt <= 0:
            return state

        target = state.combatants[target_id]
        character = self._require_character(target.character_id)
        persisted = get_active_concentration(character)
        overlay_id = target.concentration_spell_id

        if overlay_id is None and persisted is None:
            return state

        if overlay_id is not None:
            spell_id = overlay_id
            spell_name = target.concentration_spell_name or overlay_id
        else:
            assert persisted is not None
            spell_id = persisted["spell_id"]
            spell_name = persisted["spell_name"]

        save_dc = concentration_save_dc(damage_dealt)
        save_request = build_save_request(character, self._engine, "con")
        registry = self._registry_for(combat_id)
        d20 = roll_d20_for_combatant(
            save_request, character, target, self._engine,
            effect_registry=registry,
            rng=rng,
        )
        if save_succeeded(d20.total, save_dc):
            return state

        updated_char = clear_concentration(character)
        self._characters.save(updated_char)

        state.combatants[target_id] = target.without_concentration()
        state = self._clear_concentration_spell_overlay_effects(
            state, target_id, spell_id
        )
        state = self._with_registry_effects(state)
        self._persist(state)

        self._bus.publish(
            ConcentrationBroken(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=target_id,
                character_id=target.character_id,
                spell_id=spell_id,
                spell_name=spell_name,
                damage_taken=damage_dealt,
                save_dc=save_dc,
                save_total=d20.total,
            )
        )
        return state

    def _clear_hunters_marks_from_caster(
        self,
        state: CombatState,
        caster_combatant_id: str,
    ) -> CombatState:
        """Retire toutes les marques posées par ``caster_combatant_id``."""
        if state.combat_id is None:
            return state
        self._registry_for(int(state.combat_id)).remove_matching(
            effect_id="hunters_mark",
            source_id=caster_combatant_id,
        )
        return state

    def _clear_hex_from_caster(
        self,
        state: CombatState,
        caster_combatant_id: str,
    ) -> CombatState:
        """Retire tous les maléfices posés par ``caster_combatant_id``."""
        if state.combat_id is None:
            return state
        self._registry_for(int(state.combat_id)).remove_matching(
            effect_id="hexed",
            source_id=caster_combatant_id,
        )
        return state

    def _clear_concentration_spell_overlay_effects(
        self,
        state: CombatState,
        caster_combatant_id: str,
        spell_id: str,
    ) -> CombatState:
        """Nettoie les buffs liés à un sort de concentration rompu (lot B4 / ADR-006)."""
        if state.combat_id is None:
            return state
        combat_id = int(state.combat_id)
        if spell_id == "hunters_mark":
            return self._clear_hunters_marks_from_caster(state, caster_combatant_id)
        if spell_id == "bless":
            self._registry_for(combat_id).remove_matching(
                effect_id="blessed",
                source_id=caster_combatant_id,
            )
        if spell_id == "hex":
            return self._clear_hex_from_caster(state, caster_combatant_id)
        return state

    def _sync_character_from_combatant(self, combatant: Combatant) -> None:
        """Sync PV et concentration overlay → fiche (ADR-005, ordre canonique close)."""
        character = self._require_character(combatant.character_id)
        character = replace(character, hp_current=combatant.hp_current)

        overlay_id = combatant.concentration_spell_id
        if overlay_id is not None:
            spell_name = combatant.concentration_spell_name or overlay_id
            character, _interrupted = set_concentration(
                character, overlay_id, spell_name
            )
        elif get_active_concentration(character) is not None:
            character = clear_concentration(character)

        self._characters.save(character)

    def _hydrate_combatant_concentration(self, combatant: Combatant) -> Combatant:
        """Hydrate l'overlay concentration depuis la fiche si absent (ADR-005 §3)."""
        if combatant.concentration_spell_id is not None:
            return combatant
        character = self._characters.get_by_id(combatant.character_id)
        if character is None:
            return combatant
        persisted = get_active_concentration(character)
        if persisted is None:
            return combatant
        return combatant.with_concentration(
            persisted["spell_id"],
            persisted["spell_name"],
        )

    def _hydrate_legacy_combatant_conditions(
        self,
        combat_id: int,
        state: CombatState,
        raw_blob: dict,
    ) -> bool:
        """
        Convertit ``combatants[].conditions`` legacy → registre (best-effort).

        Sans bump ``COMBAT_STATE_VERSION`` — même politique que l'hydratation
        concentration (ADR-005). Réécrit le blob sans la clé ``conditions``.

        Retourne ``True`` si le blob a été réécrit (rechargement nécessaire).
        """
        if state.status == "ended":
            return False

        raw_combatants = raw_blob.get("combatants") or {}
        has_legacy = any(
            isinstance(payload, dict) and payload.get("conditions")
            for payload in raw_combatants.values()
        )
        if not has_legacy:
            return False

        registry = self._registry_for(combat_id)
        existing = {
            (effect.effect_id, effect.target_id)
            for effect in registry.all_effects()
            if effect.effect_id in PHASE1_CONDITIONS
        }
        for combatant_id, payload in raw_combatants.items():
            if not isinstance(payload, dict):
                continue
            legacy = payload.get("conditions") or []
            if not legacy:
                continue
            target_id = str(combatant_id)
            for condition_id in legacy:
                normalized = str(condition_id).strip()
                if normalized not in PHASE1_CONDITIONS:
                    continue
                key = (normalized, target_id)
                if key in existing:
                    continue
                self._add_manual_condition_effect(
                    combat_id,
                    condition_id=normalized,
                    target_id=target_id,
                    applied_at_round=state.round_number,
                )
                existing.add(key)

        self._persist(self._require_state(combat_id))
        return True

    def _registry_for(self, combat_id: int | str) -> ActiveEffectRegistry:
        key = str(combat_id)
        registry = self._effect_registries.get(key)
        if registry is None:
            registry = ActiveEffectRegistry()
            self._effect_registries[key] = registry
        return registry

    def _tick_active_effects(self, combat_id: int, round_number: int) -> None:
        self._registry_for(combat_id).tick(round_number)

    def _sync_effect_registry_from_state(
        self,
        combat_id: int,
        state: CombatState,
        *,
        force: bool,
    ) -> None:
        """
        Reconstruit le registre depuis ``state.active_effects``.

        ``force=False`` : skip si un registre existe déjà — source de vérité
        runtime intra-session (``_require_state``).
        ``force=True`` : relecture obligatoire depuis le blob persisté
        (``load_combat``, ``close_combat`` — même pattern qu'ADR-005).
        """
        key = str(combat_id)
        if not force and key in self._effect_registries:
            return
        registry = ActiveEffectRegistry()
        for effect in state.active_effects:
            registry.add(effect)
        self._effect_registries[key] = registry

    def _with_registry_effects(self, state: CombatState) -> CombatState:
        if state.combat_id is None:
            return state
        return replace(
            state,
            active_effects=self._registry_for(int(state.combat_id)).all_effects(),
        )

    def _add_concentration_effect(
        self,
        combat_id: int,
        *,
        effect_id: str,
        source_id: str,
        target_id: str,
        applied_at_round: int,
    ) -> None:
        self.add_active_effect(
            combat_id,
            ActiveEffect(
                effect_id=effect_id,
                source_id=source_id,
                target_id=target_id,
                applied_at_round=applied_at_round,
                expiry_mode="concentration",
            ),
        )

    def _add_manual_condition_effect(
        self,
        combat_id: int,
        *,
        condition_id: str,
        target_id: str,
        applied_at_round: int,
    ) -> None:
        """
        Enregistre une condition phase 1 dans le registre (``expiry_mode=manual``).

        Convention : pas de lanceur tracé en C6 — ``source_id`` reprend
        ``condition_id`` pour l'identité stable ``(condition_id, condition_id,
        target_id)`` et la cohérence avec les ``source_id`` déjà émis dans
        les ``effects[]`` d20 (``"poisoned"``, ``"frightened"``, etc.).
        """
        self.add_active_effect(
            combat_id,
            ActiveEffect(
                effect_id=condition_id,
                source_id=condition_id,
                target_id=target_id,
                applied_at_round=applied_at_round,
                expiry_mode="manual",
            ),
        )

    def _build_combatant(self, character_id: str) -> Combatant:
        character = self._characters.get_by_id(character_id)
        if character is None:
            raise CombatCharacterNotFoundError(
                f"Personnage introuvable pour le combat : {character_id!r}."
            )
        sheet = build_character_sheet(character, self._engine)
        combatant_id = str(uuid.uuid4())[:8]
        return Combatant(
            combatant_id=combatant_id,
            display_name=sheet.name,
            kind="player_character",
            character_id=character_id,
            hp_current=sheet.hp_current,
            hp_max=sheet.hp_max,
            ac=sheet.ac,
        )

    def _require_character(self, character_id: str):
        character = self._characters.get_by_id(character_id)
        if character is None:
            raise CombatCharacterNotFoundError(
                f"Personnage introuvable : {character_id!r}."
            )
        return character

    def _publish_spell_cast(
        self,
        state: CombatState,
        caster_id: str,
        spell: CombatSpellEffect,
        target_ids: tuple[str, ...],
    ) -> None:
        self._bus.publish(
            SpellCast(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or "",
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                caster_id=caster_id,
                spell_id=spell.spell_id,
                spell_name=spell.spell_name,
                effect_type=spell.effect_type,
                target_ids=target_ids,
            )
        )

    def _require_combatant(self, state: CombatState, combatant_id: str) -> Combatant:
        combatant = state.combatants.get(combatant_id)
        if combatant is None:
            raise CombatantNotFoundError(
                f"Combattant introuvable dans la rencontre : {combatant_id!r}."
            )
        return combatant

    def _roll_initiative_for_combatants(
        self,
        combatants: list[Combatant],
        *,
        rng: Callable[[], int] | None,
    ) -> list[InitiativeRollResult]:
        rolls: list[InitiativeRollResult] = []
        for combatant in combatants:
            character = self._characters.get_by_id(combatant.character_id)
            if character is None:
                raise CombatCharacterNotFoundError(
                    f"Personnage introuvable : {combatant.character_id!r}."
                )
            sheet = build_character_sheet(character, self._engine)
            rolls.append(
                roll_initiative(combatant.combatant_id, sheet.initiative, rng=rng)
            )
        return rolls

    def _require_state(self, combat_id: int) -> CombatState:
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        state = record.state
        self._sync_effect_registry_from_state(combat_id, state, force=False)
        return self._with_registry_effects(state)

    def _persist(self, state: CombatState) -> None:
        if state.combat_id is None:
            raise ValueError("combat_id requis pour persister.")
        combat_id = int(state.combat_id)
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        synced = replace(
            state,
            active_effects=self._registry_for(combat_id).all_effects(),
        )
        self._combats.save(
            CombatRecord(
                combat_id=combat_id,
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                sql_status=sql_status_from_combat(synced.status),
                state=synced,
            )
        )

    def _publish_initiative_events(
        self,
        record: CombatRecord,
        rolls: list[InitiativeRollResult],
        order: tuple[str, ...],
    ) -> None:
        state = record.state
        roll_payload = tuple(
            (r.combatant_id, r.d20, r.modifier, r.total) for r in rolls
        )
        self._bus.publish(
            InitiativeRolled(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(record.combat_id),
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                initiative_order=order,
                rolls=roll_payload,
            )
        )

    def _publish_turn_started(self, state: CombatState) -> None:
        combatant_id = state.initiative_order[state.turn_index]
        combatant = state.combatants[combatant_id]
        state.combatants[combatant_id] = combatant.with_action_budget(
            fresh_action_budget()
        )
        self._persist(state)

        self._bus.publish(
            TurnStarted(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or "",
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=combatant_id,
                round_number=state.round_number,
                turn_index=state.turn_index,
            )
        )

    def _current_turn_combatant_id(self, state: CombatState) -> str:
        return state.initiative_order[state.turn_index]

    def _consume_budget(
        self,
        combat_id: int,
        combatant_id: str,
        kind: ActionKind,
        *,
        require_own_turn: bool = True,
    ) -> None:
        state = self._require_state(combat_id)
        if require_own_turn and self._current_turn_combatant_id(state) != combatant_id:
            raise NotCombatantTurnError(
                f"Seul le combattant actif peut consommer {kind!r}."
            )
        combatant = self._require_combatant(state, combatant_id)
        budget = combatant.action_budget
        if budget is None:
            raise ActionBudgetExhaustedError(
                f"Budget non initialisé pour {combatant_id!r}."
            )
        try:
            new_budget = budget.consume(kind)
        except ActionBudgetExhaustedError:
            raise
        state.combatants[combatant_id] = combatant.with_action_budget(new_budget)
        self._persist(state)
        self._bus.publish(
            ActionConsumed(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=combatant_id,
                action_kind=kind,
                round_number=state.round_number,
                turn_index=state.turn_index,
            )
        )
