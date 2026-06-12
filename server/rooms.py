"""
Oda/lobi yönetimi (Faz 1). Transport detayı bilmez: oyunculara mesaj GÖNDERME
işi app.py'deki websocket katmanına aittir; burada yalnız durum + kurallar var.
"""
import time
import uuid
import asyncio
import secrets
import string
from typing import Any, Dict, List, Optional

from engine.season_session import SeasonSession
from server.protocol import DEFAULT_TURN_SECONDS, MAX_PLAYERS

_CODE_ALPHABET = string.ascii_uppercase.replace("O", "").replace("I", "")


class Player:
    def __init__(self, name: str):
        self.id = uuid.uuid4().hex[:12]
        self.rejoin_token = secrets.token_urlsafe(16)
        self.name = name[:24] or "Oyuncu"
        self.team_id: Optional[str] = None
        self.ready = False
        self.ws = None              # app.py bağlar/çözer

    @property
    def connected(self) -> bool:
        return self.ws is not None

    def public(self) -> Dict[str, Any]:
        return {"name": self.name, "team_id": self.team_id,
                "ready": self.ready, "connected": self.connected}


class Room:
    def __init__(self, code: str, opts: Dict[str, Any]):
        self.code = code
        self.created_at = time.time()
        self.players: Dict[str, Player] = {}          # player_id -> Player
        self.host_id: Optional[str] = None
        self.session: Optional[SeasonSession] = None
        self.turn_seconds = int(opts.get("turn_seconds", DEFAULT_TURN_SECONDS))
        self.num_races = opts.get("num_races")
        self.dynamic_ai = bool(opts.get("dynamic_ai", True))
        self.seed = opts.get("seed")
        self.deadline_ts: Optional[float] = None
        self.timer_task: Optional[asyncio.Task] = None
        self.lock = asyncio.Lock()    # faz ilerletme yarışlarına karşı

    # ------------------------------------------------------------- lobi

    @property
    def started(self) -> bool:
        return self.session is not None

    def add_player(self, name: str) -> Player:
        if self.started:
            raise LookupError("room_started")
        if len(self.players) >= MAX_PLAYERS:
            raise OverflowError("room_full")
        p = Player(name)
        self.players[p.id] = p
        if self.host_id is None:
            self.host_id = p.id
        return p

    def find_by_token(self, token: str) -> Optional[Player]:
        for p in self.players.values():
            if p.rejoin_token == token:
                return p
        return None

    def pick_team(self, player: Player, team_id: str):
        if self.started:
            raise LookupError("room_started")
        for other in self.players.values():
            if other is not player and other.team_id == team_id:
                raise ValueError("team_taken")
        player.team_id = team_id
        player.ready = False

    def can_start(self) -> bool:
        ps = list(self.players.values())
        return (len(ps) >= 1
                and all(p.team_id for p in ps)
                and all(p.ready for p in ps))

    def start_session(self) -> SeasonSession:
        human_teams = [p.team_id for p in self.players.values()]
        self.session = SeasonSession(
            human_teams, seed=self.seed, dynamic_ai=self.dynamic_ai,
            num_races=self.num_races)
        return self.session

    def team_of(self, player_id: str) -> Optional[str]:
        p = self.players.get(player_id)
        return p.team_id if p else None

    def public(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "host": self.players[self.host_id].name if self.host_id else None,
            "started": self.started,
            "turn_seconds": self.turn_seconds,
            "players": [p.public() for p in self.players.values()],
        }


class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def create(self, opts: Dict[str, Any]) -> Room:
        while True:
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
            if code not in self.rooms:
                break
        room = Room(code, opts or {})
        self.rooms[code] = room
        return room

    def get(self, code: str) -> Optional[Room]:
        return self.rooms.get((code or "").upper())

    def cleanup(self, max_idle_empty: float = 600.0):
        """Tamamen kopuk/boş odaları temizler (her bağlantı kapanışında çağrılır)."""
        now = time.time()
        dead = [c for c, r in self.rooms.items()
                if not any(p.connected for p in r.players.values())
                and now - r.created_at > max_idle_empty]
        for c in dead:
            r = self.rooms.pop(c)
            if r.timer_task:
                r.timer_task.cancel()
