import random
from typing import Dict, List, Any
import copy

from config.game_settings import GameSettings
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.qualifying import Qualifying
from engine.championship import Championship
from engine.strategy import plan_strategies, apply_qualifying_tire_rule
from engine.perks import get_all_perk_names

from data.seed_data import SEED_DRIVERS, SEED_TEAMS, SEED_CARS, SEED_TRACKS
from models.driver import Driver
from models.team import Team
from models.car import Car
from models.track import Track

# Dairesel referans (circular import) yaratmaması için calculate_initial_power_rankings'i buraya taşıdık
def calculate_initial_power_rankings(drivers: Dict[str, Driver], cars: Dict[str, Car], teams: Dict[str, Team], tracks: List[Track]):
    """
    Sezon başlamadan önce, mevcut araç ve pilot statlarına göre,
    ortalama bir pistteki teorik tur süresi gücünü hesaplayıp
    pilotları ve takımları sıralar.
    """
    settings = GameSettings()
    director = RaceDirector(settings)
    
    class DummyTrack:
        req_top_speed = sum(t.req_top_speed for t in tracks) / len(tracks)
        req_acceleration = sum(t.req_acceleration for t in tracks) / len(tracks)
        req_grip = sum(t.req_grip for t in tracks) / len(tracks)
        req_driver_skill = sum(t.req_driver_skill for t in tracks) / len(tracks)
        weather_volatility = 0.0

    dummy_track = DummyTrack()
    
    driver_powers = []
    team_powers = {t_id: 0 for t_id in teams}
    
    for d_id, drv in drivers.items():
        car = cars[teams[drv.team_id].car_id]
        profile = director.build_profile(drv, car, dummy_track, aero_level=3, strategy="normal", is_raining=False)
        power = profile["base_power"]
        
        driver_powers.append({
            "driver_id": d_id,
            "name": drv.name,
            "team": teams[drv.team_id].name,
            "base_power": power
        })
        team_powers[drv.team_id] += power

    driver_powers.sort(key=lambda x: x["base_power"], reverse=True)
    expected_driver_standings = {dp["driver_id"]: idx + 1 for idx, dp in enumerate(driver_powers)}
    
    team_powers_list = [{"team_id": k, "name": teams[k].name, "total_power": v} for k, v in team_powers.items()]
    team_powers_list.sort(key=lambda x: x["total_power"], reverse=True)
    expected_team_standings = {tp["team_id"]: idx + 1 for idx, tp in enumerate(team_powers_list)}
    
    return expected_driver_standings, expected_team_standings


class GameUniverse:
    """
    Oyunun tüm evrenini (Veritabanı, Sezon durumu, Şampiyona ve Motorları)
    tek bir Obje içinde barındırır.
    """
    def __init__(self, settings: GameSettings):
        self.settings = settings
        self.drivers: Dict[str, Driver] = {}
        self.teams: Dict[str, Team] = {}
        self.cars: Dict[str, Car] = {}
        self.tracks: List[Track] = []
        
        # Engine referansları
        self.director = RaceDirector(self.settings)
        self.engine = LapRaceEngine(self.settings)
        self.quali = Qualifying(self.settings)
        self.champ = Championship()
        
        # Sezon ilerlemesi
        self.current_race_idx = 0
        self.season_finished = False
        
        # Takım yapay zekası stratejileri
        self.team_strategies = {}
        self.available_perks = get_all_perk_names()
        
        self.exp_drv = {}
        self.exp_team = {}
        
        # Son simülasyon logları
        self.latest_upgrades = []
        self.latest_race_result = []
        
        # Sürücülerin Qualifying seansında kullandıkları son lastikleri saklar (Yarış başlangıcı için)
        self.driver_qualy_tire_choices = {}

    def load_seed_data(self):
        """Verileri dictlerden Pydantic objelerine çevirir ve Universe içine yükler."""
        self.teams = {t["id"]: Team(**t) for t in SEED_TEAMS}
        self.cars = {c["id"]: Car(**c) for c in SEED_CARS}
        self.drivers = {d["id"]: Driver(**d) for d in SEED_DRIVERS}
        self.tracks = [Track(**trk) for trk in SEED_TRACKS]

    def setup_season(self):
        """Sezon başlamadan önce güç sıralamalarını ve yapay zeka stratejilerini ayarlar."""
        self.load_seed_data()
        
        # Beklenen Şampiyona Sıralamalarını Hesapla
        self.exp_drv, self.exp_team = calculate_initial_power_rankings(
            self.drivers, self.cars, self.teams, self.tracks
        )
        
        # Takım Stratejileri oluştur
        self.team_strategies = {}
        for t_id in self.teams:
            strategy_type = random.choice(["driver_focused", "car_focused", "balanced"])
            if strategy_type == "driver_focused":
                w = {"driver1": 0.40, "driver2": 0.40, "car": 0.20}
            elif strategy_type == "car_focused":
                w = {"driver1": 0.15, "driver2": 0.15, "car": 0.70}
            else:
                w = {"driver1": 0.25, "driver2": 0.25, "car": 0.50}
            self.team_strategies[t_id] = w

    def get_team_drivers(self, team_id: str) -> List[Driver]:
        """Bir takıma ait tüm sürücüleri getirir."""
        return [d for d in self.drivers.values() if d.team_id == team_id]

    def get_team_car(self, team_id: str) -> Car:
        """Bir takımın kullandığı aracı getirir."""
        t = self.teams[team_id]
        return self.cars[t.car_id]
        
    def format_time(self, total_seconds: float) -> str:
        """Saniyeyi saat:dakika:saniye.salise formatına çevirir."""
        if total_seconds is None:
            return ""
        
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int(round((total_seconds - int(total_seconds)) * 1000))
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        else:
            return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def simulate_next_race(self):
        if self.current_race_idx >= len(self.tracks):
            self.season_finished = True
            return
            
        track = self.tracks[self.current_race_idx]
        self.current_race_idx += 1
        
        self.latest_upgrades = []
        self.latest_race_result = []
        
        # --- 1. HAFTA İÇİ GELİŞTİRMELERİ (UPGRADES & AR-GE) ---
        driver_stats = ["pace", "consistency", "attack_defense", "tire_management"]
        car_stats = ["acceleration", "top_speed", "grip", "reliability", "tire_consumption"]
        
        for t_id, team in self.teams.items():
            if team.active_facility_upgrade:
                team.process_facility_upgrade()
                if not team.active_facility_upgrade:
                    self.latest_upgrades.append({"Takım": team.name, "Kategori": "Ar-Ge", "Hedef": "Tesis", "Detay": "İnşaat Tamamlandı! Tesis Seviye Atladı."})
            else:
                facs = ["wind_tunnel", "simulator", "factory"]
                random.shuffle(facs)
                for f in facs:
                    if team.facilities.get(f, 1) < 3:
                        team.start_facility_upgrade(f, self.settings.FACILITY_UPGRADE_TIME)
                        self.latest_upgrades.append({"Takım": team.name, "Kategori": "Ar-Ge", "Hedef": "Tesis", "Detay": f"Yeni {f.upper()} inşaatı başladı ({self.settings.FACILITY_UPGRADE_TIME} Yarış sürecek).."})
                        break
                        
            team_drivers = self.get_team_drivers(t_id)
            car = self.get_team_car(t_id)
            weights = self.team_strategies[t_id]
            
            for _ in range(self.settings.UPGRADES_PER_RACE): 
                rand_val = random.random()
                if rand_val < weights["driver1"] and len(team_drivers) > 0:
                    choice = "driver1"
                elif rand_val < (weights["driver1"] + weights["driver2"]) and len(team_drivers) > 1:
                    choice = "driver2"
                else:
                    choice = "car"
                    
                if choice in ["driver1", "driver2"]:
                    drv = team_drivers[0] if choice == "driver1" else team_drivers[1]
                    
                    if random.random() < self.settings.PERK_LEARN_CHANCE and len(drv.perks) < self.settings.MAX_PERKS_PER_DRIVER:
                        potential = [p for p in self.available_perks if p not in drv.perks]
                        if potential:
                            new_perk = random.choice(potential)
                            drv.add_perk(new_perk)
                            self.latest_upgrades.append({"Takım": team.name, "Kategori": "Özel Yetenek", "Hedef": drv.name, "Detay": f"YENİ PERK ÖĞRENİLDİ: {new_perk}!"})
                            continue
                            
                    stat = random.choice(driver_stats)
                    mult = team.get_facility_multiplier("simulator")
                    
                    exp_bonus = 1.0
                    from engine.perks import get_perk_instance
                    for p_id in drv.perks:
                        perk_obj = get_perk_instance(p_id)
                        exp_bonus = perk_obj.apply_xp_modifier(exp_bonus)
                        
                    added_xp = int(self.settings.DRIVER_XP_PER_UPGRADE * mult * exp_bonus)
                    old_val = getattr(drv, stat)
                    drv.add_xp_to_stat(stat, added_xp)
                    new_val = getattr(drv, stat)
                    
                    msg = f"{stat.upper()} barına +{added_xp} XP eklendi."
                    if new_val > old_val:
                        msg += f" 🔥 (SEVİYE ATLADI: {old_val} -> {new_val})"
                    self.latest_upgrades.append({"Takım": team.name, "Kategori": "Sürücü Antrenmanı", "Hedef": drv.name, "Detay": msg})
                else:
                    stat = random.choice(car_stats)
                    if stat in ["grip", "acceleration"]:
                        mult = team.get_facility_multiplier("wind_tunnel")
                    else:
                        mult = team.get_facility_multiplier("factory")
                    added_xp = int(self.settings.CAR_XP_PER_UPGRADE * mult)
                    
                    old_val = getattr(car, stat)
                    car.add_xp_to_stat(stat, added_xp)
                    new_val = getattr(car, stat)
                    
                    msg = f"{stat.upper()} geliştirmesine +{added_xp} XP yatırıldı."
                    if new_val > old_val:
                        msg += f" 🏎️ (SEVİYE ATLADI: {old_val} -> {new_val})"
                    self.latest_upgrades.append({"Takım": team.name, "Kategori": "Araç Güncellemesi", "Hedef": "Araç", "Detay": msg})

        # --- 2. SIRALAMA TURLARI (QUALIFYING) ---
        # Artık Q1, Q2, Q3 ve Dinamik Lastik Kuralı devrede
        form = {d_id: random.gauss(0, self.settings.RACE_FORM_SIGMA) for d_id in self.drivers}
        # Qualy için ayrı bir yağmur zarı
        is_qualy_raining = random.random() < (track.weather_volatility * 2.0)
        
        grid, self.driver_qualy_tire_choices = self.quali.simulate_qualifying(
            self.drivers, self.cars, self.teams, track, is_qualy_raining, form=form
        )

        # --- 3. YARIŞ SİMÜLASYONU ---
        profiles = {
            d_id: self.director.build_profile(drv, self.get_team_car(drv.team_id), track, 3, "normal", is_raining=False) 
            for d_id, drv in self.drivers.items()
        }
        
        num_laps = track.num_laps or self.settings.DEFAULT_RACE_LAPS
        forecast = self.engine.make_forecast(track, num_laps)
        
        # Stratejileri planla
        # Q3'e kalanların (self.driver_qualy_tire_choices içinde olanların) başlangıç lastiklerini zorla
        strategies = plan_strategies(grid, forecast, num_laps, self.settings, track=track)
        
        apply_qualifying_tire_rule(strategies, self.driver_qualy_tire_choices, forecast)

        result = self.engine.simulate_race(grid, profiles, track, form=form, strategies=strategies, forecast=forecast)
        self.champ.process_race_result(result["classification"])

        # Ham çıktılar (denge denetimi / server API / replay için)
        self.latest_raw = result
        self.latest_grid = list(grid)
        
        # Sonuçları Formatla
        grid_pos = {d_id: i + 1 for i, d_id in enumerate(grid)}
        winner_time = None
        winner_laps = 0
        for e in result["classification"]:
            if e["position"] == 1 and e["status"] == "FIN":
                winner_time = e["total_time"]
                winner_laps = e["laps_completed"]
                break
                
        for i, e in enumerate(result["classification"]):
            d_id = e["driver_id"]
            delta = grid_pos[d_id] - e["position"]
            
            if e["status"] == "DNF":
                durum = f"❌ DNF ({e.get('dnf_cause', 'Unknown')})"
            else:
                if e["position"] == 1:
                    durum = self.format_time(e["total_time"])
                else:
                    lap_diff = winner_laps - e["laps_completed"]
                    if lap_diff > 0:
                        durum = f"+{lap_diff} LAP"
                    else:
                        prev_time = result["classification"][i-1]["total_time"]
                        time_diff = e["total_time"] - prev_time
                        sec = int(time_diff)
                        ms = int(round((time_diff - sec) * 1000))
                        durum = f"+{sec}.{ms:03d}"
                
            self.latest_race_result.append({
                "Sıra": e["position"],
                "Pilot": self.drivers[d_id].name,
                "Takım": self.teams[e["team_id"]].name,
                "Grid": grid_pos[d_id],
                "Değişim": f"🟢 +{delta}" if delta>0 else (f"🔴 {delta}" if delta<0 else "➖ 0"),
                "Pit Stop": e["pits"],
                "Durum (Fark)": durum
            })
