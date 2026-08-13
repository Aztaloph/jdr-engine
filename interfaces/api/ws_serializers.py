# interfaces/api/ws_serializers.py
"""Sérialisation EventBus → messages WebSocket combat (CONTRAT_WS.md §3–4)."""
from __future__ import annotations

from jdr_engine.core.events.combat_events import (
    ActionConsumed,
    AttackRollResolved,
    CombatantJoined,
    CombatEnded,
    CombatStarted,
    ConditionApplied,
    ConditionRemoved,
    ConcentrationBroken,
    DamageDealt,
    InitiativeRolled,
    PositionChanged,
    RoundStarted,
    SavingThrowResolved,
    SpellCast,
    TurnEnded,
    TurnStarted,
)
from jdr_engine.core.events.domain_event import DomainEvent

_WS_TYPED_EVENTS = (PositionChanged, TurnStarted, CombatEnded)

_COMBAT_INVALIDATION_EVENT_TYPES: frozenset[type[DomainEvent]] = frozenset(
    {
        CombatStarted,
        CombatantJoined,
        InitiativeRolled,
        TurnEnded,
        RoundStarted,
        AttackRollResolved,
        DamageDealt,
        SpellCast,
        SavingThrowResolved,
        ConditionApplied,
        ConditionRemoved,
        ConcentrationBroken,
        ActionConsumed,
    }
)


def _combat_id_int(event: DomainEvent) -> int | None:
    raw = getattr(event, "combat_id", None)
    if raw is None:
        return None
    return int(raw)


def domain_event_to_ws_message(event: DomainEvent) -> dict | None:
    """
    Convertit un événement domaine en message WS, ou ``None`` si hors périmètre.

    Événements combat non typés → ``combat_state_invalidated``.
    """
    combat_id = _combat_id_int(event)
    if combat_id is None:
        return None

    timestamp = event.timestamp.isoformat()
    event_cls = type(event)

    if event_cls is PositionChanged:
        assert isinstance(event, PositionChanged)
        return {
            "type": "position_changed",
            "combat_id": combat_id,
            "timestamp": timestamp,
            "payload": {
                "combatant_id": event.combatant_id,
                "from": {"x": event.from_x, "y": event.from_y},
                "to": {"x": event.to_x, "y": event.to_y},
                "cost_ft": event.cost_ft,
                "movement_remaining_ft": event.movement_remaining_ft,
                "round_number": event.round_number,
                "turn_index": event.turn_index,
            },
        }

    if event_cls is TurnStarted:
        assert isinstance(event, TurnStarted)
        return {
            "type": "turn_started",
            "combat_id": combat_id,
            "timestamp": timestamp,
            "payload": {
                "combatant_id": event.combatant_id,
                "round_number": event.round_number,
                "turn_index": event.turn_index,
            },
        }

    if event_cls is CombatEnded:
        assert isinstance(event, CombatEnded)
        return {
            "type": "combat_ended",
            "combat_id": combat_id,
            "timestamp": timestamp,
            "payload": {"reason": event.reason},
        }

    if event_cls in _COMBAT_INVALIDATION_EVENT_TYPES:
        return {
            "type": "combat_state_invalidated",
            "combat_id": combat_id,
            "timestamp": timestamp,
            "payload": {"source_event": event_cls.__name__},
        }

    return None


def all_combat_event_types() -> tuple[type[DomainEvent], ...]:
    """Types EventBus à abonner pour le hub WS."""
    return _WS_TYPED_EVENTS + tuple(_COMBAT_INVALIDATION_EVENT_TYPES)
