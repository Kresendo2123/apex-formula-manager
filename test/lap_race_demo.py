import random

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from main import load_data


def run(track_index: int = 15, seed: int = None):
    if seed is not None:
        random.seed(seed)

    settings = GameSettings()
    drivers, cars, teams, tracks = load_data()
    director = RaceDirector(settings)
    quali = Qualifying(settings)
    engine = LapRaceEngine(settings)

    track = tracks[track_index]
    is_raining = False

    # 1) Sıralama turları -> grid
    grid, _ = quali.simulate_qualifying(drivers, cars, teams, track, is_raining)

    # 2) Her araç için deterministik profil
    profiles = {}
    for d_id, driver in drivers.items():
        car = cars[teams[driver.team_id].car_id]
        profiles[d_id] = director.build_profile(
            driver, car, track, aero_level=3, strategy="normal", is_raining=is_raining
        )

    # 3) Stratejiler: çoğu pilot varsayılan tek-stop; iki pilota kontrast strateji ver
    num_laps = track.num_laps or settings.DEFAULT_RACE_LAPS
    third = max(1, round(num_laps / 3))
    strategies = {
        # İddialı iki-stop: soft -> soft -> medium
        grid[0]: [{"compound": "soft", "laps": third},
                  {"compound": "soft", "laps": third},
                  {"compound": "medium", "laps": num_laps - 2 * third}],
        # Riskli sıfır-pit denemesi (zorunlu kurala uymaz, aşınma cezasını göster)
        grid[1]: [{"compound": "hard", "laps": num_laps}],
    }

    # 4) Tur tabanlı yarış
    result = engine.simulate_race(grid, profiles, track, strategies=strategies)

    grid_pos = {d_id: i + 1 for i, d_id in enumerate(grid)}
    ot_diff = engine._track_overtaking_difficulty(track)

    print("=" * 72)
    print(f" {track.name}  |  Sollama: {ot_diff:.2f}  |  {num_laps} tur ".center(72, "="))
    print("=" * 72)
    print(f"{'Fin':>3}  {'Pilot':<12}{'Takım':<14}{'Grid':>5}{'Δ':>4}  {'Pit':>3} {'Son':<7} Durum")
    print("-" * 72)
    for entry in result["classification"]:
        d_id = entry["driver_id"]
        name = drivers[d_id].name
        team = teams[entry["team_id"]].name
        gp = grid_pos[d_id]
        delta = gp - entry["position"]
        arrow = f"+{delta}" if delta > 0 else (str(delta) if delta < 0 else "·")
        status = "DNF" if entry["status"] == "DNF" else f"{entry['total_time']}s"
        print(f"{entry['position']:>3}. {name:<12}{team:<14}{gp:>5}{arrow:>4}  "
              f"{entry['pits']:>3} {entry['final_compound']:<7} {status}")
    print("-" * 72)
    print(f"DNF sayısı: {result['dnf_count']}")
    print("Not: P-grid[0] iki-stop (soft/soft/med), P-grid[1] sıfır-pit (hard) denemesi.")


if __name__ == "__main__":
    run(track_index=15, seed=42)
