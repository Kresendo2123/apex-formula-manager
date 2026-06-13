"""
APEX FORMULA MANAGER — Çok oyunculu sunucu (Faz 1).

FastAPI + WebSocket. Oda kur -> kodla katıl (2-11 oyuncu) -> takım seç -> hazır
-> sezon başlar. Karar fazlarında (aero/strateji/geliştirme) süre sayacı işler;
süre dolunca eksikler otomatik doldurulur ve oyun İLERLER (AFK oyunu kilitlemez).
Yarışın kendisi sunucuda tek seferde simüle edilir; istemciler race_result
içindeki olay akışını replay olarak oynatır. Yarış içi etkileşim yoktur.

Çalıştırma: uvicorn server.app:app --reload
Mesaj sözleşmesi: server/protocol.py — olay şeması: docs/EVENT_SCHEMA.md
"""
import time
import asyncio
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from engine.events import SCHEMA_VERSION
from engine.season_session import (SubmitError, PHASE_AERO, PHASE_STRATEGY,
                                   PHASE_UPGRADE, team_catalog)
from server import protocol as P
from server.rooms import Room, RoomManager, Player

app = FastAPI(title="Apex Formula Manager Server")
manager = RoomManager()

DECISION_PHASES = (PHASE_AERO, PHASE_STRATEGY, PHASE_UPGRADE)


@app.get("/health")
def health():
    return {"ok": True, "protocol_version": P.PROTOCOL_VERSION,
            "schema_version": SCHEMA_VERSION, "rooms": len(manager.rooms)}


# ----------------------------------------------------------------- yardımcılar

async def send(player: Player, msg: dict):
    if player.ws is None:
        return
    try:
        await player.ws.send_json(msg)
    except Exception:
        player.ws = None   # kopuk bağlantı; reconnect bekler


async def broadcast(room: Room, msg: dict):
    for p in list(room.players.values()):
        await send(p, msg)


async def broadcast_room_state(room: Room):
    await broadcast(room, {"ev": "room", **room.public()})


def _phase_msg(room: Room, payload: dict) -> dict:
    msg = {"ev": "phase", **payload}
    if payload.get("phase") in DECISION_PHASES:
        msg["deadline_ts"] = room.deadline_ts
    return msg


async def _dispatch_session_events(room: Room, events):
    """SeasonSession.advance()/start() çıktısını yayınlar; karar fazına
    girildiyse süre sayacını kurar."""
    for name, payload in events:
        if name == "phase":
            if payload.get("phase") in DECISION_PHASES:
                _arm_timer(room)
            else:
                _disarm_timer(room)
            await broadcast(room, _phase_msg(room, payload))
        else:
            await broadcast(room, {"ev": name, **payload})


def _disarm_timer(room: Room):
    room.deadline_ts = None
    t, room.timer_task = room.timer_task, None
    # Zaman aşımı akışında fire() kendi advance'i içinden bir sonraki fazın
    # sayacını kurar; o anda koşan görev kendisidir — kendini iptal etmemeli.
    if t is not None and t is not asyncio.current_task():
        t.cancel()


def _arm_timer(room: Room):
    _disarm_timer(room)
    room.deadline_ts = time.time() + room.turn_seconds
    ses = room.session
    marker = (ses.race_no, ses.phase)

    async def fire():
        try:
            await asyncio.sleep(room.turn_seconds)
        except asyncio.CancelledError:
            return
        async with room.lock:
            if room.session is None or (room.session.race_no,
                                        room.session.phase) != marker:
                return   # faz zaten ilerledi
            filled = room.session.auto_fill_phase()
            if filled:
                await broadcast(room, {"ev": "auto_filled", "teams": filled,
                                       "phase": marker[1]})
            await _dispatch_session_events(room, room.session.advance())

    room.timer_task = asyncio.create_task(fire())


async def _after_submit(room: Room, team_id: str):
    await broadcast(room, {"ev": "player_submitted", "team_id": team_id,
                           "phase": room.session.phase})
    if room.session.all_submitted:
        await _dispatch_session_events(room, room.session.advance())


# ----------------------------------------------------------------- ws döngüsü

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    await ws.send_json({"ev": "hello", "protocol_version": P.PROTOCOL_VERSION,
                        "schema_version": SCHEMA_VERSION})
    room: Optional[Room] = None
    player: Optional[Player] = None

    async def err(code, msg):
        await ws.send_json({"ev": "error", "code": code, "msg": msg})

    try:
        while True:
            try:
                m = await ws.receive_json()
            except (ValueError, KeyError):
                await err(P.ERR_BAD_MESSAGE, "geçersiz JSON")
                continue
            op = m.get("op")

            # ---- oda gerektirmeyen sorgular
            if op == "list_teams":
                await ws.send_json({"ev": "team_catalog", "teams": team_catalog()})
                continue

            # ---- lobi işlemleri
            if op == "create_room":
                room = manager.create(m.get("opts") or {})
                player = room.add_player(m.get("name", ""))
                player.ws = ws
                await ws.send_json({"ev": "joined", "player_id": player.id,
                                    "rejoin_token": player.rejoin_token,
                                    "room": room.public()})
                await broadcast_room_state(room)

            elif op == "join_room":
                r = manager.get(m.get("code", ""))
                if r is None:
                    await err(P.ERR_ROOM_NOT_FOUND, "oda bulunamadı")
                    continue
                tok = m.get("rejoin_token")
                if tok:                       # yeniden bağlanma
                    p = r.find_by_token(tok)
                    if p is None:
                        await err(P.ERR_ROOM_NOT_FOUND, "geçersiz rejoin token")
                        continue
                    p.ws = ws
                    room, player = r, p
                else:
                    try:
                        player = r.add_player(m.get("name", ""))
                    except LookupError:
                        await err(P.ERR_ROOM_STARTED, "oyun başladı; rejoin_token gerekli")
                        continue
                    except OverflowError:
                        await err(P.ERR_ROOM_FULL, "oda dolu (11 oyuncu)")
                        continue
                    player.ws = ws
                    room = r
                await ws.send_json({"ev": "joined", "player_id": player.id,
                                    "rejoin_token": player.rejoin_token,
                                    "room": room.public()})
                await broadcast_room_state(room)
                if room.started:              # reconnect: durumu tazele
                    await send(player, {"ev": "static_data",
                                        **room.session.static_data()})
                    await send(player, _phase_msg(room, room.session.phase_payload()))

            elif room is None or player is None:
                await err(P.ERR_NOT_IN_ROOM, "önce bir odaya katıl")

            # ---- oda içi, oyun öncesi
            elif op == "pick_team":
                try:
                    room.pick_team(player, m.get("team_id"))
                except LookupError:
                    await err(P.ERR_ROOM_STARTED, "oyun zaten başladı")
                    continue
                except ValueError:
                    await err(P.ERR_TEAM_TAKEN, "takım başka oyuncuda")
                    continue
                await broadcast_room_state(room)

            elif op == "ready":
                player.ready = bool(m.get("ready", True))
                await broadcast_room_state(room)

            elif op == "start_game":
                if player.id != room.host_id:
                    await err(P.ERR_NOT_HOST, "yalnız oda sahibi başlatabilir")
                    continue
                if room.started:
                    await err(P.ERR_ROOM_STARTED, "oyun zaten başladı")
                    continue
                if not room.can_start():
                    await err(P.ERR_NOT_READY, "herkes takım seçip hazır olmalı")
                    continue
                async with room.lock:
                    ses = room.start_session()
                    await broadcast_room_state(room)
                    await broadcast(room, {"ev": "static_data", **ses.static_data()})
                    await _dispatch_session_events(room, ses.start())

            # ---- oyun içi girdiler
            elif op in ("submit_aero", "submit_strategy", "submit_upgrades"):
                if not room.started:
                    await err(P.ERR_BAD_MESSAGE, "oyun başlamadı")
                    continue
                team = player.team_id
                async with room.lock:
                    try:
                        if op == "submit_aero":
                            room.session.submit_aero(team, m.get("level", 3))
                        elif op == "submit_strategy":
                            room.session.submit_strategy(team, m.get("choices") or {})
                        else:
                            room.session.submit_upgrades(team, m.get("spends") or [],
                                                         m.get("facility"))
                    except SubmitError as e:
                        await err(P.ERR_SUBMIT, str(e))
                        continue
                    await send(player, {"ev": "submit_ok",
                                        "phase": room.session.phase})
                    await _after_submit(room, team)

            elif op == "sync":
                await ws.send_json({"ev": "room", **room.public()})
                if room.started:
                    await send(player, {"ev": "static_data",
                                        **room.session.static_data()})
                    await send(player, _phase_msg(room, room.session.phase_payload()))

            else:
                await err(P.ERR_BAD_MESSAGE, f"bilinmeyen op: {op}")

    except WebSocketDisconnect:
        pass
    finally:
        if player is not None:
            player.ws = None
            if room is not None:
                await broadcast_room_state(room)
        manager.cleanup()
