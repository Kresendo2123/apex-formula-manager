"""
ÇOK OYUNCULU SEZON OTURUMU — transport'tan bağımsız çekirdek (Faz 1).

2-11 insan oyuncu birer takımı yönetir; kalan takımlar YZ. Yarış içi etkileşim
YOKTUR: tüm kararlar yarış öncesi toplanır, simülasyon tek seferde koşulur ve
istemciler olay akışını replay gibi oynatır (bkz. docs/EVENT_SCHEMA.md).

Yarış başına faz akışı:

    aero ──> (quali otomatik) ──> strategy ──> (yarış otomatik) ──> upgrade ──> sonraki yarış
                                                                      └──> season_end (son yarışsa)

Sözleşme (sunucu katmanı bu API'yi sarar; WebSocket/JSON detayı burada YOK):
  - submit_aero / submit_strategy / submit_upgrades: oyuncu girdisi toplar.
  - all_submitted True olunca (veya zaman aşımında auto_fill_phase sonrası)
    advance() çağrılır; yayınlanacak (event_adı, payload) listesi döner.
  - Determinizm: aynı seed + aynı girdiler = birebir aynı sezon.
"""
import random
from typing import Any, Dict, List, Optional, Tuple

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.championship import Championship
from engine.strategy import plan_strategies, build_strategy_options, apply_choice
from data.seed_data import SEED_DRIVERS, SEED_TEAMS, SEED_CARS, SEED_TRACKS
from models.driver import Driver
from models.team import Team
from models.car import Car
from models.track import Track

STYLE_IDS = ["normal", "aggressive", "long_stint"]
WALL_RISKS = [None, "düşük", "orta", "yüksek"]   # None = kartın kendi riski
DRIVER_STAT_IDS = ["pace", "consistency", "attack_defense", "tire_management"]
CAR_STAT_IDS = ["acceleration", "top_speed", "grip", "reliability", "tire_consumption"]
FACILITY_IDS = ["wind_tunnel", "simulator", "factory"]

PHASE_AERO, PHASE_STRATEGY, PHASE_UPGRADE, PHASE_END = \
    "aero", "strategy", "upgrade", "season_end"


def team_catalog() -> List[Dict[str, Any]]:
    """Oyun-öncesi (lobi) takım seçimi için sabit takım listesi. Oturum
    gerektirmez; doğrudan tohum verisinden kurulur. İstemci bunu lobide
    gerçek bir takım seçici çizmek için kullanır."""
    drivers_by_team: Dict[str, List[str]] = {}
    for d in SEED_DRIVERS:
        drivers_by_team.setdefault(d["team_id"], []).append(d["name"])
    return [{"id": t["id"], "name": t["name"],
             "drivers": drivers_by_team.get(t["id"], [])}
            for t in SEED_TEAMS]


class SubmitError(ValueError):
    """Geçersiz oyuncu girdisi (yanlış faz, yanlış takım, bilinmeyen id...)."""


class SeasonSession:
    def __init__(self, human_teams: List[str], seed: Optional[int] = None,
                 settings: Optional[GameSettings] = None, dynamic_ai: bool = True,
                 num_races: Optional[int] = None):
        self.s = settings or GameSettings()
        self.seed = seed if seed is not None else random.getrandbits(48)
        self.rng = random.Random(self.seed)
        self.dynamic_ai = dynamic_ai

        self.teams = {t["id"]: Team(**t) for t in SEED_TEAMS}
        self.cars = {c["id"]: Car(**c) for c in SEED_CARS}
        self.drivers = {d["id"]: Driver(**d) for d in SEED_DRIVERS}
        self.tracks = [Track(**t) for t in SEED_TRACKS]
        self.rng.shuffle(self.tracks)
        if num_races:
            self.tracks = self.tracks[:num_races]

        unknown = [t for t in human_teams if t not in self.teams]
        if unknown:
            raise SubmitError(f"bilinmeyen takım(lar): {unknown}")
        if not 1 <= len(set(human_teams)) == len(human_teams) <= len(self.teams):
            raise SubmitError("insan takımları 1-11 arası ve benzersiz olmalı")
        self.human_teams = list(human_teams)
        self.ai_teams = [t for t in sorted(self.teams) if t not in human_teams]

        self.director = RaceDirector(self.s, rng=self.rng)
        self.engine = LapRaceEngine(self.s, rng=self.rng)
        self.quali = Qualifying(self.s, rng=self.rng)
        self.champ = Championship()

        # faz durumu
        self.race_no = 0          # 1-based; 0 = sezon başlamadı
        self.phase: Optional[str] = None
        self.pending: set = set()           # bu fazda girdisi beklenen insan takımları
        self._aero: Dict[str, int] = {}     # team_id -> seviye (insanlar)
        self._strategy: Dict[str, Dict[str, Dict[str, Any]]] = {}  # team -> driver -> seçim
        self._upgrades: Dict[str, Dict[str, Any]] = {}             # team -> harcama paketi

        # yarış bağlamı (her _setup_race'te yenilenir)
        self.track = None
        self.num_laps = 0
        self.fc = None
        self.conditions = None
        self.options: List[Dict[str, Any]] = []
        self.grid: List[str] = []
        self.form: Dict[str, float] = {}
        self.aero_lv: Dict[str, int] = {}
        self.last_result: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------- statik veri

    def team_drivers(self, t_id: str) -> List[str]:
        t = self.teams[t_id]
        return [t.lead_driver_id, t.second_driver_id]

    def static_data(self) -> Dict[str, Any]:
        """İstemcinin id->isim eşlemesi için bir kez aldığı sabit veri."""
        return {
            "teams": {t_id: {"name": t.name,
                             "drivers": self.team_drivers(t_id)}
                      for t_id, t in self.teams.items()},
            "drivers": {d_id: d.name for d_id, d in self.drivers.items()},
            "calendar": [t.name for t in self.tracks],
            "styles": STYLE_IDS,
            "wall_risks": ["kart", "düşük", "orta", "yüksek"],
            "driver_stats": DRIVER_STAT_IDS,
            "car_stats": CAR_STAT_IDS,
            "facilities": FACILITY_IDS,
            "upgrades_per_race": self.s.UPGRADES_PER_RACE,
        }

    # ------------------------------------------------------------- faz yükleri

    def start(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Sezonu başlatır; ilk yayın listesi döner."""
        if self.race_no != 0:
            raise SubmitError("sezon zaten başladı")
        return self._setup_race()

    def _track_character(self) -> str:
        ideal = RaceDirector.ideal_aero(self.track, self.s)
        if ideal <= 2.2:
            return "düzlük"
        if ideal >= 3.8:
            return "viraj"
        return "dengeli"

    def phase_payload(self) -> Dict[str, Any]:
        """Mevcut fazın istemciye gidecek bağlamı (resync için de kullanılır)."""
        base = {"race_no": self.race_no, "total_races": len(self.tracks),
                "phase": self.phase, "pending_teams": sorted(self.pending)}
        if self.phase == PHASE_AERO:
            base.update({
                "track": {"name": self.track.name, "num_laps": self.num_laps,
                          "character": self._track_character()},
                "forecast": self.fc,
                "conditions": {
                    "wear_mult": round(self.conditions["wear_day_mult"], 3),
                    "hint": ("sıcak" if self.conditions["wear_day_mult"] > 1.05
                             else "serin" if self.conditions["wear_day_mult"] < 0.95
                             else "normal"),
                },
            })
        elif self.phase == PHASE_STRATEGY:
            base.update({
                "grid": list(self.grid),
                "options": self.options,
                "styles": STYLE_IDS,
            })
        elif self.phase == PHASE_UPGRADE:
            base.update({"teams": {
                t_id: self._team_sheet(t_id) for t_id in self.human_teams}})
        elif self.phase == PHASE_END:
            base.update({"final_standings": self._standings_payload()})
        return base

    def _team_sheet(self, t_id: str) -> Dict[str, Any]:
        t = self.teams[t_id]
        car = self.cars[t.car_id]
        sheet = {
            "car": {st: getattr(car, st) for st in CAR_STAT_IDS},
            "drivers": {d: {st: getattr(self.drivers[d], st) for st in DRIVER_STAT_IDS}
                        for d in self.team_drivers(t_id)},
            "facilities": dict(t.facilities),
            "active_facility_upgrade": t.active_facility_upgrade,
        }
        return sheet

    def _standings_payload(self) -> Dict[str, Any]:
        return {
            "drivers": sorted(self.champ.driver_standings.items(),
                              key=lambda kv: -kv[1]),
            "teams": sorted(self.champ.team_standings.items(),
                            key=lambda kv: -kv[1]),
        }

    # ------------------------------------------------------------- girdi toplama

    def _check(self, phase: str, team_id: str):
        if self.phase != phase:
            raise SubmitError(f"şu an {self.phase} fazındayız, {phase} girdisi alınmaz")
        if team_id not in self.human_teams:
            raise SubmitError(f"{team_id} insan takımı değil")

    @property
    def all_submitted(self) -> bool:
        return not self.pending

    def submit_aero(self, team_id: str, level: int):
        self._check(PHASE_AERO, team_id)
        if not 1 <= int(level) <= 5:
            raise SubmitError("aero 1-5 arası olmalı")
        self._aero[team_id] = int(level)
        self.pending.discard(team_id)

    def submit_strategy(self, team_id: str, choices: Dict[str, Dict[str, Any]]):
        """choices: {driver_id: {"card_id": str, "style": str, "wall": str|None}}"""
        self._check(PHASE_STRATEGY, team_id)
        valid_cards = {o["id"] for o in self.options}
        my_drivers = set(self.team_drivers(team_id))
        clean = {}
        for d_id, ch in choices.items():
            if d_id not in my_drivers:
                raise SubmitError(f"{d_id} bu takımın pilotu değil")
            card = ch.get("card_id")
            if card is not None and card not in valid_cards:
                raise SubmitError(f"bilinmeyen kart: {card}")
            style = ch.get("style", "normal")
            if style not in STYLE_IDS:
                raise SubmitError(f"bilinmeyen stil: {style}")
            wall = ch.get("wall")
            if wall not in WALL_RISKS:
                raise SubmitError(f"bilinmeyen pit duvarı talimatı: {wall}")
            clean[d_id] = {"card_id": card, "style": style, "wall": wall}
        for d_id in my_drivers - set(clean):
            clean[d_id] = {"card_id": None, "style": "normal", "wall": None}
        self._strategy[team_id] = clean
        self.pending.discard(team_id)

    def submit_upgrades(self, team_id: str, spends: List[Dict[str, Any]],
                        facility: Optional[str] = None):
        """spends: [{"kind":"driver","driver_id":..,"stat":..} | {"kind":"car","stat":..}]"""
        self._check(PHASE_UPGRADE, team_id)
        if len(spends) > self.s.UPGRADES_PER_RACE:
            raise SubmitError(f"en fazla {self.s.UPGRADES_PER_RACE} geliştirme hakkı var")
        my_drivers = set(self.team_drivers(team_id))
        for sp in spends:
            if sp.get("kind") == "driver":
                if sp.get("driver_id") not in my_drivers:
                    raise SubmitError(f"{sp.get('driver_id')} bu takımın pilotu değil")
                if sp.get("stat") not in DRIVER_STAT_IDS:
                    raise SubmitError(f"bilinmeyen sürücü statı: {sp.get('stat')}")
            elif sp.get("kind") == "car":
                if sp.get("stat") not in CAR_STAT_IDS:
                    raise SubmitError(f"bilinmeyen araç statı: {sp.get('stat')}")
            else:
                raise SubmitError("spend.kind 'driver' ya da 'car' olmalı")
        if facility is not None and facility not in FACILITY_IDS:
            raise SubmitError(f"bilinmeyen tesis: {facility}")
        self._upgrades[team_id] = {"spends": list(spends), "facility": facility}
        self.pending.discard(team_id)

    # ------------------------------------------------------------- YZ / otomatik

    def _ai_pick_aero(self) -> int:
        if not self.dynamic_ai:
            return 3
        ideal = int(round(RaceDirector.ideal_aero(self.track, self.s)))
        r = self.rng.random()
        off = 0 if r < 0.60 else self.rng.choice([-1, 1]) if r < 0.90 \
            else self.rng.choice([-2, 2])
        return max(1, min(5, ideal + off))

    def _ai_pick_style(self) -> str:
        if not self.dynamic_ai:
            return "normal"
        return self.rng.choices(STYLE_IDS, weights=[60, 20, 20])[0]

    def _ai_pick_card(self) -> Optional[Dict[str, Any]]:
        if not self.dynamic_ai or self.rng.random() < 0.45:
            return None
        return self.rng.choice(self.options)

    def _ai_spend_upgrades(self, t_id: str):
        """YZ (veya zaman aşımına uğrayan insan) takımının gelişim turu."""
        if not self.dynamic_ai and t_id not in self.human_teams:
            return
        team = self.teams[t_id]
        car = self.cars[team.car_id]
        d1, d2 = (self.drivers[d] for d in self.team_drivers(t_id))
        if team.active_facility_upgrade is None:
            avail = [f for f in FACILITY_IDS if team.facilities.get(f, 3) < 3]
            if avail:
                team.start_facility_upgrade(self.rng.choice(avail),
                                            self.s.FACILITY_UPGRADE_TIME)
        for _ in range(self.s.UPGRADES_PER_RACE):
            if self.rng.random() < 0.6:
                stats = sorted(CAR_STAT_IDS, key=lambda x: getattr(car, x))
                stat = stats[0] if self.rng.random() < 0.5 else self.rng.choice(CAR_STAT_IDS)
                mult = team.get_facility_multiplier(
                    "wind_tunnel" if stat in ("grip", "acceleration") else "factory")
                car.add_xp_to_stat(stat, int(self.s.CAR_XP_PER_UPGRADE * mult))
            else:
                drv = d1 if self.rng.random() < 0.65 else d2
                stat = self.rng.choice(DRIVER_STAT_IDS)
                mult = team.get_facility_multiplier("simulator")
                drv.add_xp_to_stat(stat, int(self.s.DRIVER_XP_PER_UPGRADE * mult))

    def auto_fill_phase(self) -> List[str]:
        """Zaman aşımı: eksik insan girdilerini makul varsayılanla doldurur.
        Doldurulan takımların listesini döner (yayın/etiket için)."""
        filled = sorted(self.pending)
        for t_id in filled:
            if self.phase == PHASE_AERO:
                self.submit_aero(t_id, 3)
            elif self.phase == PHASE_STRATEGY:
                self.submit_strategy(t_id, {})   # varsayılan plan + normal stil
            elif self.phase == PHASE_UPGRADE:
                # AFK oyuncu geride kalmasın: YZ mantığıyla harcanır
                self.submit_upgrades(t_id, [], None)
                self._upgrades[t_id]["afk_ai"] = True
        return filled

    # ------------------------------------------------------------- akış

    def _setup_race(self) -> List[Tuple[str, Dict[str, Any]]]:
        self.race_no += 1
        self.track = self.tracks[self.race_no - 1]
        self.num_laps = self.track.num_laps or self.s.DEFAULT_RACE_LAPS
        self.fc = self.engine.make_forecast(self.track, self.num_laps)
        self.conditions = self.engine.roll_race_conditions()
        self._aero, self._strategy, self._upgrades = {}, {}, {}
        self.phase = PHASE_AERO
        self.pending = set(self.human_teams)
        return [("phase", self.phase_payload())]

    def advance(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Faz girdileri tamamlandığında çağrılır (gerekirse önce auto_fill_phase).
        Otomatik adımları koşar, sonraki faza geçer, yayın listesi döner."""
        if not self.all_submitted:
            raise SubmitError(f"eksik girdiler var: {sorted(self.pending)}")
        if self.phase == PHASE_AERO:
            return self._run_quali()
        if self.phase == PHASE_STRATEGY:
            return self._run_race()
        if self.phase == PHASE_UPGRADE:
            return self._finish_upgrades()
        raise SubmitError("sezon bitti")

    def _run_quali(self) -> List[Tuple[str, Dict[str, Any]]]:
        self.aero_lv = {}
        for d_id, dr in self.drivers.items():
            if dr.team_id in self.human_teams:
                self.aero_lv[d_id] = self._aero[dr.team_id]
            else:
                self.aero_lv[d_id] = self._ai_pick_aero()
        self.form = {d: self.rng.gauss(0, self.s.RACE_FORM_SIGMA) for d in self.drivers}
        is_q_rain = self.rng.random() < self.track.weather_volatility
        self.grid, _ = self.quali.simulate_qualifying(
            self.drivers, self.cars, self.teams, self.track, is_q_rain,
            form=self.form, aero_levels=self.aero_lv)
        self.options = build_strategy_options(self.fc, self.num_laps, self.s,
                                              track=self.track)
        self.phase = PHASE_STRATEGY
        self.pending = set(self.human_teams)
        return [("quali_result", {"race_no": self.race_no, "is_rain": is_q_rain,
                                  "grid": list(self.grid)}),
                ("phase", self.phase_payload())]

    def _run_race(self) -> List[Tuple[str, Dict[str, Any]]]:
        strat = plan_strategies(self.grid, self.fc, self.num_laps, self.s,
                                rng=self.rng, track=self.track)
        cards_by_id = {o["id"]: o for o in self.options}
        styles = {}
        for d_id, dr in self.drivers.items():
            if dr.team_id in self.human_teams:
                ch = self._strategy[dr.team_id][d_id]
                if ch["card_id"] is not None:
                    apply_choice(strat, d_id, cards_by_id[ch["card_id"]])
                if ch["wall"] is not None:
                    strat[d_id]["risk"] = ch["wall"]
                styles[d_id] = ch["style"]
            else:
                card = self._ai_pick_card()
                if card is not None:
                    apply_choice(strat, d_id, card)
                styles[d_id] = self._ai_pick_style()

        profiles = {d: self.director.build_profile(
            dr, self.cars[self.teams[dr.team_id].car_id], self.track,
            self.aero_lv[d], styles[d], False)
            for d, dr in self.drivers.items()}
        race_seed = self.rng.getrandbits(48)
        res = self.engine.simulate_race(
            self.grid, profiles, self.track, form=self.form, strategies=strat,
            forecast=self.fc, conditions=self.conditions, seed=race_seed)
        self.last_result = res
        self.champ.process_race_result(res["classification"])

        out = [("race_result", {
            "race_no": self.race_no, "track": self.track.name,
            "grid": list(self.grid), "result": res,
        }), ("standings", self._standings_payload())]

        if self.race_no >= len(self.tracks):
            self.phase = PHASE_END
            self.pending = set()
        else:
            self.phase = PHASE_UPGRADE
            self.pending = set(self.human_teams)
        out.append(("phase", self.phase_payload()))
        return out

    def _finish_upgrades(self) -> List[Tuple[str, Dict[str, Any]]]:
        # İnsan harcamaları (deterministik sıra: takım id sıralı)
        for t_id in sorted(self._upgrades):
            pkg = self._upgrades[t_id]
            if pkg.get("afk_ai"):
                self._ai_spend_upgrades(t_id)
                continue
            team = self.teams[t_id]
            for sp in pkg["spends"]:
                if sp["kind"] == "driver":
                    mult = team.get_facility_multiplier("simulator")
                    self.drivers[sp["driver_id"]].add_xp_to_stat(
                        sp["stat"], int(self.s.DRIVER_XP_PER_UPGRADE * mult))
                else:
                    mult = team.get_facility_multiplier(
                        "wind_tunnel" if sp["stat"] in ("grip", "acceleration")
                        else "factory")
                    self.cars[team.car_id].add_xp_to_stat(
                        sp["stat"], int(self.s.CAR_XP_PER_UPGRADE * mult))
            if pkg["facility"] and team.active_facility_upgrade is None \
                    and team.facilities.get(pkg["facility"], 3) < 3:
                team.start_facility_upgrade(pkg["facility"],
                                            self.s.FACILITY_UPGRADE_TIME)
        # YZ takımları
        for t_id in self.ai_teams:
            self._ai_spend_upgrades(t_id)
        # Tesis inşaatları ilerler (tüm takımlar)
        for team in self.teams.values():
            team.process_facility_upgrade()
        return self._setup_race()
