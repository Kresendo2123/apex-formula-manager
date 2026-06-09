import random
from config.game_settings import GameSettings
from models.driver import Driver
from models.car import Car
from models.team import Team
from models.track import Track
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.simulator import Simulator
from engine.championship import Championship

from data.seed_data import SEED_DRIVERS, SEED_CARS, SEED_TEAMS, SEED_TRACKS


def load_data():
    """Seed verilerini Pydantic modellerine çevirir."""
    drivers = {d["id"]: Driver(**d) for d in SEED_DRIVERS}
    cars = {c["id"]: Car(**c) for c in SEED_CARS}
    teams = {t["id"]: Team(**t) for t in SEED_TEAMS}
    tracks = [Track(**t) for t in SEED_TRACKS]
    return drivers, cars, teams, tracks


def calculate_preseason_expectations(drivers, cars, teams, tracks, director):
    """
    Kağıt üstünde, şanssızlık (DNF) ve yağmur olmadan 24 yarışlık kusursuz bir
    sezon simüle edilerek 'Beklenen Şampiyona Puanları' hesaplanır.
    """
    expected_driver_points = {d_id: 0 for d_id in drivers}
    expected_team_points = {t_id: 0 for t_id in teams}

    # Gerçek F1 Puanlama Sistemi
    point_system = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
    #point_system = {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}

    # Tüm 24 pist için kusursuz (kazasız/yağmursuz) koşullarda yarışı simüle et
    for track in tracks:
        track_power_ranking = []

        for d_id, driver in drivers.items():
            car = cars[teams[driver.team_id].car_id]
            entry = director.calculate_effective_power(
                driver=driver,
                car=car,
                track=track,
                aero_level=3,
                strategy="normal",
                is_raining=False,
                grid_position=11  # Nötr pozisyon
            )
            # Pilot ID, Takım ID ve o pistteki Nihai Gücü
            track_power_ranking.append((d_id, driver.team_id, entry["raw_power"]))

        # O pist için en güçlü kombinasyonları sırala (Hard Sort)
        track_power_ranking.sort(key=lambda x: x[2], reverse=True)

        # İlk 10'a giren Pilot ve Takımlara puanlarını ver
        for pos, (d_id, t_id, power) in enumerate(track_power_ranking, start=1):
            if pos in point_system:
                expected_driver_points[d_id] += point_system[pos]
                expected_team_points[t_id] += point_system[pos]

    # Sıralı listeler (Tuple: (id, toplam_beklenen_puan))
    sorted_drivers = sorted(expected_driver_points.items(), key=lambda x: x[1], reverse=True)
    sorted_teams = sorted(expected_team_points.items(), key=lambda x: x[1], reverse=True)

    return sorted_drivers, sorted_teams


def print_preseason_predictions(expected_drivers, expected_teams, drivers, teams):
    """Sezon öncesi puan tahminlerini terminale basar."""
    print("\n" + "=" * 55)
    print(" SEZON ÖNCESİ TAHMİNLER (KUSURSUZ SEZON SİMÜLASYONU) ".center(55, "="))
    print("=" * 55)

    print("🏁 Tahmini Pilotlar Şampiyonası:")
    for pos, (d_id, points) in enumerate(expected_drivers, 1):
        # Gerçekçilik katmak için takım adının ilk 3 harfini ekliyoruz (Örn: VER (RBR))
        team_name = teams[drivers[d_id].team_id].name[:3].upper()
        print(f"{pos:2}. {drivers[d_id].name:15} ({team_name}) | Beklenen: {points:4} PTS")

    print("\n🏎️ Tahmini Markalar Şampiyonası:")
    for pos, (t_id, points) in enumerate(expected_teams, 1):
        print(f"{pos:2}. {teams[t_id].name:15} | Beklenen: {points:4} PTS")
    print("=" * 55 + "\n")


def print_standings(championship: Championship, drivers: dict, teams: dict):
    """Sezon sonu puan durumunu yazar."""
    print("\n" + "=" * 40)
    print(" PİLOTLAR ŞAMPİYONASI ".center(40, "="))
    print("=" * 40)
    sorted_drivers = sorted(championship.driver_standings.items(), key=lambda x: x[1], reverse=True)
    for pos, (d_id, points) in enumerate(sorted_drivers, 1):
        driver_name = drivers[d_id].name
        print(f"{pos:2}. {driver_name:15} | {points} PTS")

    print("\n" + "=" * 40)
    print(" MARKALAR ŞAMPİYONASI ".center(40, "="))
    print("=" * 40)
    sorted_teams = sorted(championship.team_standings.items(), key=lambda x: x[1], reverse=True)
    for pos, (t_id, points) in enumerate(sorted_teams, 1):
        team_name = teams[t_id].name
        print(f"{pos:2}. {team_name:15} | {points} PTS")
    print("=" * 40 + "\n")


def print_season_review(expected_drivers, expected_teams, championship, drivers, teams):
    """Beklentiler ile gerçekleşen sonuçları kıyaslayıp sürprizleri listeler."""
    actual_drivers = sorted(championship.driver_standings.items(), key=lambda x: x[1], reverse=True)
    actual_teams = sorted(championship.team_standings.items(), key=lambda x: x[1], reverse=True)

    # Sıralamaları {id: pozisyon} sözlüğüne çevir
    exp_d_pos = {d_id: pos for pos, (d_id, _) in enumerate(expected_drivers, 1)}
    exp_t_pos = {t_id: pos for pos, (t_id, _) in enumerate(expected_teams, 1)}
    act_d_pos = {d_id: pos for pos, (d_id, _) in enumerate(actual_drivers, 1)}
    act_t_pos = {t_id: pos for pos, (t_id, _) in enumerate(actual_teams, 1)}

    # Delta hesapla: Beklenen - Gerçekleşen (Pozitif: Yükseliş, Sürpriz)
    driver_deltas = []
    for d_id in drivers:
        act_pos = act_d_pos.get(d_id, len(drivers))  # Puan alamayanları sona at
        delta = exp_d_pos[d_id] - act_pos
        driver_deltas.append((d_id, delta, act_pos, exp_d_pos[d_id]))

    team_deltas = []
    for t_id in teams:
        act_pos = act_t_pos.get(t_id, len(teams))
        delta = exp_t_pos[t_id] - act_pos
        team_deltas.append((t_id, delta, act_pos, exp_t_pos[t_id]))

    driver_deltas.sort(key=lambda x: x[1], reverse=True)
    team_deltas.sort(key=lambda x: x[1], reverse=True)

    print("\n" + "=" * 55)
    print(" SEZON ÖZETİ: BEKLENTİLER vs GERÇEKLER ".center(55, "="))
    print("=" * 55)

    print("\n🔥 PİLOTLAR: EN BÜYÜK SÜRPRİZLER (OVERACHIEVERS)")
    for d_id, delta, act, exp in driver_deltas[:3]:
        print(f"🔼 {drivers[d_id].name:15} | Beklenen: {exp:2} -> Gerçekleşen: {act:2} (Fark: +{delta})")

    print("\n❄️ PİLOTLAR: HAYAL KIRIKLIKLARI (UNDERACHIEVERS)")
    # En kötüleri bulmak için listeyi tersten sondan 3 tane alıyoruz
    for d_id, delta, act, exp in driver_deltas[-3:]:
        print(f"🔽 {drivers[d_id].name:15} | Beklenen: {exp:2} -> Gerçekleşen: {act:2} (Fark: {delta})")

    print("\n🔥 TAKIMLAR: BEKLENTİYİ AŞANLAR")
    for t_id, delta, act, exp in team_deltas[:2]:
        print(f"🔼 {teams[t_id].name:15} | Beklenen: {exp:2} -> Gerçekleşen: {act:2} (Fark: +{delta})")

    print("\n❄️ TAKIMLAR: BEKLENTİNİN ALTINDA KALANLAR")
    for t_id, delta, act, exp in team_deltas[-2:]:
        print(f"🔽 {teams[t_id].name:15} | Beklenen: {exp:2} -> Gerçekleşen: {act:2} (Fark: {delta})")
    print("=" * 55 + "\n")


def run_season():
    # 1. Altyapıyı Başlat
    settings = GameSettings()
    drivers, cars, teams, tracks = load_data()

    director = RaceDirector(settings)
    simulator = Simulator()
    championship = Championship()

    # 2. Sezon Öncesi Analiz
    qualifying_engine = Qualifying(settings)
    expected_drivers, expected_teams = calculate_preseason_expectations(drivers, cars, teams, tracks, director)
    print_preseason_predictions(expected_drivers, expected_teams, drivers, teams)

    print("🏁 F1 Manager Simülatörü Başlıyor 🏁\n")

    # 3. 24 Yarışlık Sezon Döngüsü
    for race_no, track in enumerate(tracks, 1):
        print(f"\nYarış {race_no:02d}/24: {track.name:20}")

        # --- SIRALAMA TURLARI (QUALIFYING) ---
        is_quali_raining = random.random() < track.weather_volatility
        if is_quali_raining:
            print("  [💧 Islak Zemin Sıralama Turları]")

        grid, _ = qualifying_engine.simulate_qualifying(drivers, cars, teams, track, is_quali_raining)
        pole_sitter = drivers[grid[0]].name
        print(f"  ⏱️ Pole Pozisyonu: {pole_sitter}")

        # --- YARIŞ (RACE) ---
        is_race_raining = random.random() < track.weather_volatility
        if is_race_raining:
            print("  [🌧️ Yağmurlu Yarış Başlıyor]")
        else:
            print("  [☀️ Kuru Zemin Yarışı]")

        race_entries = []

        for d_id, driver in drivers.items():
            car = cars[teams[driver.team_id].car_id]

            # Pilotun grid pozisyonunu bul (index 0 olduğu için +1 ekliyoruz)
            grid_pos = grid.index(d_id) + 1

            entry = director.calculate_effective_power(
                driver=driver,
                car=car,
                track=track,
                aero_level=3,
                strategy="normal",
                is_raining=is_race_raining,
                grid_position=grid_pos  # YENİ PARAMETRE
            )
            race_entries.append(entry)

        race_result = simulator.simulate_race(race_entries)
        championship.process_race_result(race_result["classification"])

        print(f"  🏁 Yarış Bitti! (DNF: {race_result['dnf_count']} araç)")

    # 4. Sonuçlar ve Özet
    print_standings(championship, drivers, teams)
    print_season_review(expected_drivers, expected_teams, championship, drivers, teams)


if __name__ == "__main__":
    run_season()
