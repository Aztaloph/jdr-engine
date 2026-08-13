# interfaces/api/combat_ws.py
"""WebSocket combat v1 — hub EventBus et route (CONTRAT_WS.md)."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from interfaces.api.ws_serializers import (
    all_combat_event_types,
    domain_event_to_ws_message,
)
from jdr_engine.application.combat_service import CombatService
from jdr_engine.core.events.bus import EventBus
from jdr_engine.core.events.domain_event import DomainEvent
from jdr_engine.persistence.combat_repository import CombatNotFoundError

WS_COMBAT_NOT_FOUND = 4404


@dataclass
class _WsConnection:
    websocket: WebSocket
    queue: asyncio.Queue[dict | None] = field(default_factory=asyncio.Queue)
    loop: asyncio.AbstractEventLoop | None = None


class CombatWsHub:
    """Registre combat_id → connexions ; broadcast depuis l'EventBus (sync)."""

    def __init__(self) -> None:
        self._by_combat: dict[int, list[_WsConnection]] = defaultdict(list)

    def register(self, conn: _WsConnection, combat_id: int) -> None:
        self._by_combat[combat_id].append(conn)

    def unregister(self, conn: _WsConnection, combat_id: int) -> None:
        bucket = self._by_combat.get(combat_id)
        if not bucket:
            return
        try:
            bucket.remove(conn)
        except ValueError:
            return
        if not bucket:
            del self._by_combat[combat_id]

    async def run_sender(
        self,
        conn: _WsConnection,
        combat_id: int,
        *,
        viewer: str | None,
    ) -> None:
        await self._send(
            conn,
            {
                "type": "connected",
                "combat_id": combat_id,
                "timestamp": _iso_now(),
                "payload": {"viewer": viewer},
            },
        )
        try:
            while True:
                message = await conn.queue.get()
                if message is None:
                    break
                await self._send(conn, message)
                if message.get("type") == "combat_ended":
                    await self._close(conn, code=1000)
                    break
        finally:
            self.unregister(conn, combat_id)

    def stop_sender(self, conn: _WsConnection) -> None:
        self._enqueue(conn, None)

    def handle_domain_event(self, event: DomainEvent) -> None:
        message = domain_event_to_ws_message(event)
        if message is None:
            return
        combat_id = int(message["combat_id"])
        for conn in list(self._by_combat.get(combat_id, ())):
            self._enqueue(conn, message)

    def _enqueue(self, conn: _WsConnection, message: dict | None) -> None:
        loop = conn.loop
        if loop is None or not loop.is_running():
            return

        async def _put() -> None:
            await conn.queue.put(message)

        try:
            asyncio.run_coroutine_threadsafe(_put(), loop)
        except RuntimeError:
            return

    async def _send(self, conn: _WsConnection, message: dict) -> None:
        ws = conn.websocket
        if ws.client_state != WebSocketState.CONNECTED:
            return
        await ws.send_json(message)

    async def _close(self, conn: _WsConnection, *, code: int) -> None:
        ws = conn.websocket
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.close(code=code)


def attach_combat_ws_handlers(hub: CombatWsHub, event_bus: EventBus) -> None:
    """Abonne le hub à tous les événements combat du contrat WS."""
    handler = hub.handle_domain_event
    for event_type in all_combat_event_types():
        event_bus.subscribe(event_type, handler)


def register_combat_ws_routes(
    app: FastAPI,
    *,
    hub: CombatWsHub,
    combat_service: CombatService,
) -> None:
    """Enregistre ``WS /v1/combats/{combat_id}/ws``."""

    def _normalize_viewer(viewer: str | None) -> str | None:
        if viewer is None:
            return None
        trimmed = viewer.strip()
        return trimmed if trimmed else None

    @app.websocket("/v1/combats/{combat_id}/ws")
    async def combat_websocket(
        websocket: WebSocket,
        combat_id: int,
        viewer: str | None = None,
    ) -> None:
        await websocket.accept()
        try:
            combat_service.load_combat(combat_id)
        except CombatNotFoundError:
            await websocket.close(code=WS_COMBAT_NOT_FOUND)
            return

        normalized_viewer = _normalize_viewer(viewer)
        conn = _WsConnection(
            websocket=websocket,
            loop=asyncio.get_running_loop(),
        )
        hub.register(conn, combat_id)
        sender = asyncio.create_task(
            hub.run_sender(conn, combat_id, viewer=normalized_viewer)
        )
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            hub.stop_sender(conn)
            try:
                await asyncio.wait_for(sender, timeout=2.0)
            except TimeoutError:
                sender.cancel()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
