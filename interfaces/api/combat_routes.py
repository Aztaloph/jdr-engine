# interfaces/api/combat_routes.py
"""Routes HTTP combat v1 — cycle de vie et actions (contrat §5.2)."""
from __future__ import annotations

from typing import Callable

from pathlib import Path

from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field

from interfaces.api.combat_attack import (
    build_weapon_attack_request,
    build_weapon_damage_notation,
)
from interfaces.api.auth.guards import (
    assert_combatant_owned,
    assert_viewer_allowed,
    require_gm,
    require_session,
)
from interfaces.api.combat_scope import (
    assert_characters_available_for_combat,
    resolve_create_scope,
)
from interfaces.api.errors import ApiError
from interfaces.scenes.scene_store import SqliteSceneStore
from interfaces.scenes.spawn_placements import (
    build_spawn_placements,
    grid_dimensions_from_snapshot,
)
from interfaces.scenes.validate import SceneValidationError, parse_scene_document
from jdr_engine.application.combat_view import (
    resolve_combatant_ability_snapshots,
    resolve_viewer_context,
)
from jdr_engine.application.combat_journal import format_combat_log
from jdr_engine.application.combat_service import CombatService
from jdr_engine.application.dto.output_serializers import (
    WeaponAttackResult,
    combat_state_to_dict,
    viewer_combatant_id,
    weapon_attack_result_to_dict,
)
from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.domain.combat.action_budget import ActionBudgetExhaustedError
from jdr_engine.domain.combat.grid_position import GridPosition
from jdr_engine.game.combat_manager import (
    CellOccupiedError,
    CombatCharacterNotFoundError,
    CombatStatusError,
    CombatantNotFoundError,
    InsufficientCombatantsError,
    InvalidPositionError,
    NotCombatantTurnError,
    OutOfRangeError,
)
from jdr_engine.rules.combat.weapons import (
    UnknownWeaponError,
    resolve_weapon,
    weapon_attack_range_ft,
)
from jdr_engine.rules.spellcasting.cast import SpellCastError
from jdr_engine.persistence.combat_repository import (
    CombatNotFoundError,
    OpenCombatExistsError,
    SqliteCombatRepository,
)
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)


class CreateCombatRequest(BaseModel):
    character_ids: list[str] = Field(min_length=1)
    channel_id: str | None = None
    guild_id: str | None = None
    scene_id: str | None = None


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


class CombatHealRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    combatant_id: str = Field(min_length=1)
    hp_current: int | None = Field(default=None, ge=1)


class CombatSyncRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    combatant_id: str = Field(min_length=1)


class ActivateGridBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(default=20, ge=1, le=200)
    height: int = Field(default=20, ge=1, le=200)


class ActivatePositionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)


class ActivateCombatRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grid: ActivateGridBody | None = None
    placements: dict[str, ActivatePositionBody] | None = None


class MoveCombatantRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    combatant_id: str = Field(min_length=1)
    x: int = Field(ge=0)
    y: int = Field(ge=0)


def register_combat_routes(
    app: FastAPI,
    *,
    combat_service: CombatService,
    character_repository: SqliteCharacterRepository,
    combat_repository: SqliteCombatRepository,
    engine,
    db_path: Path,
    locale: str = "fr",
    initiative_rng: Callable[[], int] | None = None,
    attack_rng=None,
) -> None:
    """Enregistre ``/v1/combats/…`` sur l'application."""
    app.state.combat_initiative_rng = initiative_rng
    app.state.combat_attack_rng = attack_rng
    scene_store = SqliteSceneStore(db_path)

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

    def _scene_fields(combat_id: int) -> dict:
        binding = combat_repository.get_scene_binding(combat_id)
        if binding is None:
            return {}
        return {
            "scene_id": binding.scene_id,
            "scene_snapshot": binding.snapshot,
        }

    def _combat_payload(
        state: CombatState,
        *,
        viewer: str | None = None,
    ) -> dict:
        payload = _serialize_combat_state(state, viewer=viewer)
        if state.combat_id is not None:
            payload.update(_scene_fields(int(state.combat_id)))
        return payload

    def _combat_response(combat_id: int, viewer: str | None = None) -> dict:
        state = combat_service.load_combat(combat_id)
        return _combat_payload(state, viewer=viewer)

    def _resolve_viewer(
        request: Request,
        state: CombatState,
        viewer: str | None,
    ) -> str | None:
        session = require_session(request)
        if session is None:
            return _validated_viewer(state, viewer)
        return assert_viewer_allowed(
            session,
            viewer,
            state=state,
            character_repository=character_repository,
        )

    @app.post("/v1/combats")
    def create_combat(body: CreateCombatRequest, request: Request) -> dict:
        session = require_session(request)
        require_gm(session)
        _assert_characters_exist(body.character_ids)
        assert_characters_available_for_combat(
            combat_repository,
            body.character_ids,
        )
        guild_id, channel_id = resolve_create_scope(
            guild_id=body.guild_id,
            channel_id=body.channel_id,
        )
        scene_snapshot: dict | None = None
        resolved_scene_id: str | None = None
        if body.scene_id is not None:
            record = scene_store.get(body.scene_id)
            if record is None:
                raise ApiError(
                    404,
                    "SCENE_NOT_FOUND",
                    "Scène introuvable.",
                    details={"scene_id": body.scene_id},
                )
            try:
                scene_snapshot = parse_scene_document(record.document)
            except SceneValidationError as exc:
                raise ApiError(
                    422,
                    "SCENE_INVALID",
                    "Document scène invalide.",
                    details={
                        "issues": [
                            {
                                "code": issue.code,
                                "message": issue.message,
                                "ref": issue.ref,
                            }
                            for issue in exc.report.issues
                            if issue.level == "error"
                        ]
                    },
                ) from exc
            resolved_scene_id = record.id
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
        if scene_snapshot is not None and resolved_scene_id is not None:
            assert state.combat_id is not None
            combat_repository.set_scene_binding(
                int(state.combat_id),
                scene_id=resolved_scene_id,
                snapshot=scene_snapshot,
                character_ids=body.character_ids,
            )
        return _combat_payload(state, viewer=None)

    @app.get("/v1/combats/open")
    def list_open_combats(request: Request) -> dict:
        require_session(request)
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
    def get_combat(combat_id: int, request: Request, viewer: str | None = None) -> dict:
        require_session(request)
        try:
            state = combat_service.load_combat(combat_id)
            resolved_viewer = _resolve_viewer(request, state, viewer)
            return _combat_payload(state, viewer=resolved_viewer)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc

    @app.get("/v1/combats/{combat_id}/events")
    def get_combat_events(combat_id: int, request: Request) -> dict:
        require_session(request)
        try:
            state = combat_service.load_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc
        entries = combat_service.get_event_log(combat_id)
        return {
            "combat_id": combat_id,
            "events": format_combat_log(entries, state),
        }

    @app.post("/v1/combats/{combat_id}/activate")
    def activate_combat(
        combat_id: int,
        request: Request,
        body: ActivateCombatRequestBody | None = None,
    ) -> dict:
        session = require_session(request)
        require_gm(session)
        rng = getattr(request.app.state, "combat_initiative_rng", None)
        binding = combat_repository.get_scene_binding(combat_id)
        grid_width = 20
        grid_height = 20
        placements: dict[str, GridPosition] | None = None
        if binding is not None:
            grid_width, grid_height = grid_dimensions_from_snapshot(binding.snapshot)
            state = combat_service.load_combat(combat_id)
            placements = build_spawn_placements(
                binding.snapshot,
                list(binding.character_ids),
                state.combatants,
            )
        elif body is not None:
            if body.grid is not None:
                grid_width = body.grid.width
                grid_height = body.grid.height
            if body.placements is not None:
                placements = {
                    combatant_id: GridPosition(x=pos.x, y=pos.y)
                    for combatant_id, pos in body.placements.items()
                }
        try:
            state = combat_service.activate_combat(
                combat_id,
                grid_width=grid_width,
                grid_height=grid_height,
                placements=placements,
                rng=rng,
            )
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
        except (InvalidPositionError, CellOccupiedError) as exc:
            raise ApiError(
                409,
                exc.code,
                str(exc),
            ) from exc
        except ValueError as exc:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                str(exc),
            ) from exc
        return _combat_payload(state, viewer=None)

    @app.post("/v1/combats/{combat_id}/attack")
    def attack(
        combat_id: int,
        body: AttackRequestBody,
        request: Request,
        viewer: str | None = None,
    ) -> dict:
        session = require_session(request)
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

        normalized_viewer = _resolve_viewer(request, state, viewer)
        assert_combatant_owned(
            session,
            state,
            body.attacker_id,
            character_repository,
        )

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
                max_range_ft=weapon_attack_range_ft(weapon_profile),
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
        except OutOfRangeError as exc:
            raise ApiError(
                409,
                exc.code,
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
        session = require_session(request)
        try:
            state = combat_service.load_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc

        normalized_viewer = _resolve_viewer(request, state, viewer)
        assert_combatant_owned(
            session,
            state,
            body.caster_id,
            character_repository,
        )

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
        except OutOfRangeError as exc:
            raise ApiError(
                409,
                exc.code,
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

    @app.post("/v1/combats/{combat_id}/heal")
    def heal_combatant(
        combat_id: int,
        body: CombatHealRequestBody,
        request: Request,
        viewer: str | None = None,
    ) -> dict:
        session = require_session(request)
        require_gm(session)
        try:
            state = combat_service.load_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc

        normalized_viewer = _resolve_viewer(request, state, viewer)

        if body.combatant_id not in state.combatants:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                "Combattant introuvable.",
                details={"combatant_id": body.combatant_id},
            )

        try:
            state = combat_service.heal_combatant(
                combat_id,
                body.combatant_id,
                hp_current=body.hp_current,
            )
        except CombatantNotFoundError as exc:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                str(exc),
            ) from exc

        return _serialize_combat_state(state, viewer=normalized_viewer)

    @app.post("/v1/combats/{combat_id}/sync-combatant")
    def sync_combatant_from_sheet(
        combat_id: int,
        body: CombatSyncRequestBody,
        request: Request,
        viewer: str | None = None,
    ) -> dict:
        """Réaligne PV/CA du combattant sur la fiche (après repos long, etc.)."""
        session = require_session(request)
        try:
            state = combat_service.load_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc

        normalized_viewer = _resolve_viewer(request, state, viewer)
        assert_combatant_owned(
            session,
            state,
            body.combatant_id,
            character_repository,
        )

        if body.combatant_id not in state.combatants:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                "Combattant introuvable.",
                details={"combatant_id": body.combatant_id},
            )

        try:
            state = combat_service.refresh_combatant_from_sheet(
                combat_id,
                body.combatant_id,
            )
        except CombatantNotFoundError as exc:
            raise ApiError(
                404,
                "COMBATANT_NOT_FOUND",
                str(exc),
            ) from exc

        return _serialize_combat_state(state, viewer=normalized_viewer)

    @app.post("/v1/combats/{combat_id}/move")
    def move_combatant(
        combat_id: int,
        body: MoveCombatantRequestBody,
        request: Request,
        viewer: str | None = None,
    ) -> dict:
        session = require_session(request)
        try:
            state = combat_service.load_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc

        normalized_viewer = _resolve_viewer(request, state, viewer)
        assert_combatant_owned(
            session,
            state,
            body.combatant_id,
            character_repository,
        )

        try:
            state = combat_service.move_combatant(
                combat_id,
                body.combatant_id,
                body.x,
                body.y,
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
        except InvalidPositionError as exc:
            raise ApiError(
                409,
                exc.code,
                str(exc),
            ) from exc
        except CellOccupiedError as exc:
            raise ApiError(
                409,
                exc.code,
                str(exc),
            ) from exc
        except CombatStatusError as exc:
            raise ApiError(
                409,
                "COMBAT_STATUS_INVALID",
                str(exc),
            ) from exc
        return _serialize_combat_state(state, viewer=normalized_viewer)

    @app.post("/v1/combats/{combat_id}/advance-turn")
    def advance_turn(
        combat_id: int,
        request: Request,
        viewer: str | None = None,
    ) -> dict:
        session = require_session(request)
        require_gm(session)
        try:
            state = combat_service.load_combat(combat_id)
        except CombatNotFoundError as exc:
            raise ApiError(
                404,
                "COMBAT_NOT_FOUND",
                "Combat introuvable.",
                details={"combat_id": combat_id},
            ) from exc
        resolved_viewer = _resolve_viewer(request, state, viewer)
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
        return _serialize_combat_state(state, viewer=resolved_viewer)

    @app.post("/v1/combats/{combat_id}/close")
    def close_combat(combat_id: int, request: Request) -> dict:
        session = require_session(request)
        require_gm(session)
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
