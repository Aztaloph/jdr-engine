# interfaces/api/combat_routes.py
"""Routes HTTP combat v1 — cycle de vie et actions (contrat §5.2)."""
from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field

from interfaces.api.combat_attack import (
    build_weapon_attack_request,
    build_weapon_damage_notation,
)
from interfaces.api.combat_scope import (
    assert_characters_available_for_combat,
    resolve_create_scope,
)
from interfaces.api.errors import ApiError
from jdr_engine.application.combat_view import (
    resolve_combatant_ability_snapshots,
    resolve_viewer_context,
)
from jdr_engine.application.combat_service import CombatService
from jdr_engine.application.dto.output_serializers import (
    WeaponAttackResult,
    combat_state_to_dict,
    viewer_combatant_id,
    weapon_attack_result_to_dict,
)
from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.domain.combat.action_budget import ActionBudgetExhaustedError
from jdr_engine.game.combat_manager import (
    CombatCharacterNotFoundError,
    CombatStatusError,
    CombatantNotFoundError,
    InsufficientCombatantsError,
    NotCombatantTurnError,
)
from jdr_engine.persistence.combat_repository import (
    CombatNotFoundError,
    OpenCombatExistsError,
    SqliteCombatRepository,
)
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules.combat.weapons import UnknownWeaponError, resolve_weapon
from jdr_engine.rules.spellcasting.cast import SpellCastError


class CreateCombatRequest(BaseModel):
    character_ids: list[str] = Field(min_length=1)
    channel_id: str | None = None
    guild_id: str | None = None


class AttackRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attacker_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    weapon_id: str = Field(min_length=1)


class CombatCastRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caster_id: str = Field(min_length=1)
    spell_id: str = Field(min_length=1)
    target_ids: list[str] = Field(default_factory=list)
    slot_level: int | None = Field(default=None, ge=1, le=9)


def register_combat_routes(
    app: FastAPI,
    *,
    combat_service: CombatService,
    character_repository: SqliteCharacterRepository,
    combat_repository: SqliteCombatRepository,
    engine,
    locale: str = "fr",
    initiative_rng: Callable[[], int] | None = None,
    attack_rng=None,
) -> None:
    """Enregistre ``/v1/combats/…`` sur l'application."""
    app.state.combat_initiative_rng = initiative_rng
    app.state.combat_attack_rng = attack_rng

    def _assert_characters_exist(character_ids: list[str]) -> None:
        for character_id in character_ids:
            if character_repository.get_by_id(character_id) is None:
                raise ApiError(
                    404,
                    "CHARACTER_NOT_FOUND",
                    "Personnage introuvable.",
                    details={"character_id": character_id},
                )

    def _normalize_viewer(viewer: str | None) -> str | None:
        if viewer is None:
            return None
        trimmed = viewer.strip()
        return trimmed if trimmed else None

    def _validated_viewer(state: CombatState, viewer: str | None) -> str | None:
        normalized = _normalize_viewer(viewer)
        if normalized is not None and viewer_combatant_id(state, normalized) is None:
            details: dict[str, object] = {"character_id": normalized}
            if state.combat_id is not None:
                details["combat_id"] = int(state.combat_id)
            raise ApiError(
                404,
                "VIEWER_NOT_IN_COMBAT",
                "Le personnage ne participe pas à cette rencontre.",
                details=details,
            )
        return normalized

    def _serialize_combat_state(
        state: CombatState,
        viewer: str | None = None,
    ) -> dict:
        normalized = _validated_viewer(state, viewer)
        viewer_context = None
        if normalized is not None:
            viewer_context = resolve_viewer_context(
                state,
                normalized,
                character_repository,
                engine,
                locale=locale,
            )
        ability_snapshots = resolve_combatant_ability_snapshots(
            state,
            character_repository,
            engine,
            viewer=normalized,
            locale=locale,
        )
        return combat_state_to_dict(
            state,
            viewer=normalized,
            viewer_context=viewer_context,
            combatant_ability_snapshots=ability_snapshots,
        )

    def _combat_response(combat_id: int, viewer: str | None = None) -> dict:
        state = combat_service.load_combat(combat_id)
        return _serialize_combat_state(state, viewer=viewer)

    @app.post("/v1/combats")
    def create_combat(body: CreateCombatRequest) -> dict:
        _assert_characters_exist(body.character_ids)
        assert_characters_available_for_combat(
            combat_repository,
            body.character_ids,
        )
        guild_id, channel_id = resolve_create_scope(
            guild_id=body.guild_id,
            channel_id=body.channel_id,
        )
        try:
            state = combat_service.create_combat(
                guild_id,
                channel_id,
                body.character_ids,
            )
        except CombatCharacterNotFoundError as exc:
            raise ApiError(
                404,
                "CHARACTER_NOT_FOUND",
                str(exc),
            ) from exc
        except OpenCombatExistsError as exc:
            raise ApiError(
                409,
                "OPEN_COMBAT_EXISTS",
                str(exc),
            ) from exc
        return _serialize_combat_state(state, viewer=None)

    @app.get("/v1/combats/open")
    def list_open_combats() -> dict:
        """Index des combats ouverts (banc de test — libère les personnages via close)."""
        entries: list[dict] = []
        for record in combat_repository.list_open():
            state = record.state
            entries.append(
                {
                    "combat_id": record.combat_id,
                    "status": state.status,
                    "participants": [
                        {
                            "character_id": combatant.character_id,
                            "display_name": combatant.display_name,
                        }
                        for combatant in state.combatants.values()
                    ],
                }
            )
        return {"combats": entries}

    @app.get("/v1/combats/{combat_id}")
    def get_combat(combat_id: int, viewer: str | None = None) -> dict:
        try:
            return _combat_response(combat_id, viewer=viewer)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc

    @app.post("/v1/combats/{combat_id}/activate")
    def activate_combat(combat_id: int, request: Request) -> dict:
        rng = getattr(request.app.state, "combat_initiative_rng", None)
        try:
            state = combat_service.activate_combat(combat_id, rng=rng)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc
        except InsufficientCombatantsError as exc:
            raise ApiError(
                409,
                "INSUFFICIENT_COMBATANTS",
                str(exc),
            ) from exc
        except CombatStatusError as exc:
            raise ApiError(
                409,
                "COMBAT_STATUS_INVALID",
                str(exc),
            ) from exc
        return _serialize_combat_state(state, viewer=None)

    @app.post("/v1/combats/{combat_id}/attack")
    def attack(
        combat_id: int,
        body: AttackRequestBody,
        request: Request,
        viewer: str | None = None,
    ) -> dict:
        try:
            weapon_profile = resolve_weapon(body.weapon_id)
        except UnknownWeaponError as exc:
            raise ApiError(
                422,
                exc.code,
                str(exc),
                details={"weapon_id": exc.weapon_id},
            ) from exc

        try:
            state = combat_service.load_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc

        normalized_viewer = _validated_viewer(state, viewer)

        if body.attacker_id not in state.combatants:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                "Combattant introuvable.",
                details={"combatant_id": body.attacker_id},
            )
        if body.target_id not in state.combatants:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                "Combattant introuvable.",
                details={"combatant_id": body.target_id},
            )

        attacker_combatant = state.combatants[body.attacker_id]
        character = character_repository.get_by_id(attacker_combatant.character_id)
        if character is None:
            raise ApiError(
                404,
                "CHARACTER_NOT_FOUND",
                "Personnage introuvable.",
                details={"character_id": attacker_combatant.character_id},
            )

        roll_request = build_weapon_attack_request(
            character,
            engine,
            weapon_profile,
            locale=locale,
        )
        rng = getattr(request.app.state, "combat_attack_rng", None)
        try:
            resolution = combat_service.resolve_attack_roll(
                combat_id,
                body.attacker_id,
                body.target_id,
                roll_request,
                rng=rng,
            )
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc
        except CombatantNotFoundError as exc:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                str(exc),
            ) from exc
        except ActionBudgetExhaustedError as exc:
            raise ApiError(
                409,
                "ACTION_BUDGET_EXHAUSTED",
                str(exc),
            ) from exc
        except NotCombatantTurnError as exc:
            raise ApiError(
                409,
                "NOT_COMBATANT_TURN",
                str(exc),
            ) from exc
        except CombatStatusError as exc:
            raise ApiError(
                409,
                "COMBAT_STATUS_INVALID",
                str(exc),
            ) from exc
        except CombatCharacterNotFoundError as exc:
            raise ApiError(
                404,
                "CHARACTER_NOT_FOUND",
                str(exc),
            ) from exc

        damage_resolution = None
        if resolution.outcome.hit:
            damage_notation = build_weapon_damage_notation(
                character,
                engine,
                weapon_profile,
                locale=locale,
            )
            state, damage_resolution = combat_service.apply_damage(
                combat_id,
                body.target_id,
                damage_notation,
                critical=resolution.outcome.critical,
                source_id=body.attacker_id,
                rng=rng,
            )
        else:
            state = combat_service.load_combat(combat_id)

        target = state.combatants[body.target_id]
        return weapon_attack_result_to_dict(
            WeaponAttackResult(
                attack=resolution,
                damage=damage_resolution,
                target_combatant_id=body.target_id,
                target_hp_current=target.hp_current,
                target_hp_max=target.hp_max,
            ),
            state=state,
            viewer=normalized_viewer,
        )

    @app.post("/v1/combats/{combat_id}/cast")
    def cast_spell_in_combat(
        combat_id: int,
        body: CombatCastRequestBody,
        request: Request,
        viewer: str | None = None,
    ) -> dict:
        try:
            state = combat_service.load_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc

        normalized_viewer = _validated_viewer(state, viewer)

        if body.caster_id not in state.combatants:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                "Combattant introuvable.",
                details={"combatant_id": body.caster_id},
            )
        for target_id in body.target_ids:
            if target_id not in state.combatants:
                raise ApiError(
                    404,
                    "COMBATANT_NOT_FOUND",
                    "Combattant introuvable.",
                    details={"combatant_id": target_id},
                )

        rng = getattr(request.app.state, "combat_attack_rng", None)
        try:
            state = combat_service.cast_spell(
                combat_id,
                body.caster_id,
                body.spell_id,
                body.target_ids,
                slot_level=body.slot_level,
                locale=locale,
                rng=rng,
            )
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc
        except CombatantNotFoundError as exc:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                str(exc),
            ) from exc
        except ActionBudgetExhaustedError as exc:
            raise ApiError(
                409,
                "ACTION_BUDGET_EXHAUSTED",
                str(exc),
            ) from exc
        except NotCombatantTurnError as exc:
            raise ApiError(
                409,
                "NOT_COMBATANT_TURN",
                str(exc),
            ) from exc
        except CombatStatusError as exc:
            raise ApiError(
                409,
                "COMBAT_STATUS_INVALID",
                str(exc),
            ) from exc
        except CombatCharacterNotFoundError as exc:
            raise ApiError(
                404,
                "CHARACTER_NOT_FOUND",
                str(exc),
            ) from exc
        except SpellCastError as exc:
            raise ApiError(
                422,
                "SPELL_CAST_REJECTED",
                str(exc),
                details={"spell_id": body.spell_id},
            ) from exc
        except ValueError as exc:
            raise ApiError(
                422,
                "SPELL_CAST_REJECTED",
                str(exc),
                details={"spell_id": body.spell_id},
            ) from exc

        return _serialize_combat_state(state, viewer=normalized_viewer)

    @app.post("/v1/combats/{combat_id}/advance-turn")
    def advance_turn(
        combat_id: int,
        viewer: str | None = None,
    ) -> dict:
        try:
            state = combat_service.advance_turn(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc
        except CombatStatusError as exc:
            raise ApiError(
                409,
                "COMBAT_STATUS_INVALID",
                str(exc),
            ) from exc
        return _serialize_combat_state(state, viewer=viewer)

    @app.post("/v1/combats/{combat_id}/close")
    def close_combat(combat_id: int) -> dict:
        try:
            state = combat_service.close_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc
        return _serialize_combat_state(state, viewer=None)
