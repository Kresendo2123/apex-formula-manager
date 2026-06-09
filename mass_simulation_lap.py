import random
import pandas as pd

from config.game_settings import GameSettings
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.championship import Championship
from engine.qualifying import Qualifying
from engine.strategy import plan_strategies, apply_qualifying_tire_rule

# Mevcut load_data fonksiyonunu main'den çekiyoruz
from main import load_data


def run_mass_simulation(num_seasons=1000):
    print(f"🛠️ [{num_seasons} Sezonluk LAP-MOTORU Simülasyonu Başlıyor... Lütfen Bekleyin]")

    settings = GameSettings()
    drivers, cars, teams, tracks = load_data()

    # 1. İstatistik sözlükleri
    driver_stats = {
        d_id: {"name": d.name, "team": teams[d.team_id].name, "champs": 0, "pts": 0,
               "pos_sum": 0, "wins": 0, "podiums": 0, "poles": 0, "dnfs": 0}
        for d_id, d in drivers.items()
    }
    team_stats = {
        t_id: {"name": t.name, "champs": 0, "pts": 0, "pos_sum": 0}
        for t_id, t in teams.items()
    }

    # 2. N sezon simüle et
    for season in range(1, num_seasons + 1):
        if season % 50 == 0:
            print(f"⏳ İşleniyor: Sezon {season}/{num_seasons} tamamlandı...")

        director = RaceDirector(settings)
        engine = LapRaceEngine(settings)
        championship = Championship()
        qualifying_engine = Qualifying(settings)

        for track in tracks:
            # Hafta sonu formu: pilot başına bir kez çekilir, sıralama + yarışta aynı kullanılır
            form = {d_id: random.gauss(0, settings.RACE_FORM_SIGMA) for d_id in drivers}

            # --- Sıralama ---
            is_quali_raining = random.random() < track.weather_volatility
            grid, q3_tire_choices = qualifying_engine.simulate_qualifying(
                drivers, cars, teams, track, is_quali_raining, form=form
            )
            driver_stats[grid[0]]["poles"] += 1

            # --- Yarış (tur tabanlı) ---
            # Yağmur artık YARIŞ MOTORUNDA (dinamik hava) ele alınıyor; çift saymamak için
            # profil kuru hesaplanır.
            profiles = {}
            for d_id, driver in drivers.items():
                car = cars[teams[driver.team_id].car_id]
                profiles[d_id] = director.build_profile(
                    driver, car, track, aero_level=3, strategy="normal", is_raining=False
                )

            # Hava tahmini + ona göre strateji (çoğu konvansiyonel, azı riskli)
            num_laps = track.num_laps or settings.DEFAULT_RACE_LAPS
            forecast = engine.make_forecast(track, num_laps)
            strategies = plan_strategies(grid, forecast, num_laps, settings)
            apply_qualifying_tire_rule(strategies, q3_tire_choices, forecast)
            race_result = engine.simulate_race(grid, profiles, track, form=form,
                                               strategies=strategies, forecast=forecast)
            championship.process_race_result(race_result["classification"])

            for res in race_result["classification"]:
                d_id = res["driver_id"]
                if res.get("status") == "DNF":
                    driver_stats[d_id]["dnfs"] += 1
                else:
                    if res["position"] == 1:
                        driver_stats[d_id]["wins"] += 1
                    if res["position"] <= 3:
                        driver_stats[d_id]["podiums"] += 1

        # 3. Sezon sonu şampiyona kayıtları
        sorted_drivers = sorted(championship.driver_standings.items(), key=lambda x: x[1], reverse=True)
        for pos, (d_id, pts) in enumerate(sorted_drivers, 1):
            driver_stats[d_id]["pts"] += pts
            driver_stats[d_id]["pos_sum"] += pos
            if pos == 1:
                driver_stats[d_id]["champs"] += 1

        sorted_teams = sorted(championship.team_standings.items(), key=lambda x: x[1], reverse=True)
        for pos, (t_id, pts) in enumerate(sorted_teams, 1):
            team_stats[t_id]["pts"] += pts
            team_stats[t_id]["pos_sum"] += pos
            if pos == 1:
                team_stats[t_id]["champs"] += 1

    # 4. DataFrame
    driver_rows = []
    for d_id, stats in driver_stats.items():
        driver_rows.append({
            "Pilot": stats["name"],
            "Takım": stats["team"],
            "Şampiyonluk": stats["champs"],
            "Ortalama Puan": round(stats["pts"] / num_seasons, 1),
            "Ort. Klasman Sırası": round(stats["pos_sum"] / num_seasons, 1),
            "Galibiyet Sayısı": stats["wins"],
            "Podyum Sayısı": stats["podiums"],
            "Pole Pozisyonu": stats["poles"],
            "Toplam DNF": stats["dnfs"]
        })

    team_rows = []
    for t_id, stats in team_stats.items():
        team_rows.append({
            "Takım": stats["name"],
            "Markalar Şampiyonluğu": stats["champs"],
            "Ortalama Puan": round(stats["pts"] / num_seasons, 1),
            "Ort. Klasman Sırası": round(stats["pos_sum"] / num_seasons, 1)
        })

    df_drivers = pd.DataFrame(driver_rows).sort_values(by="Ortalama Puan", ascending=False)
    df_teams = pd.DataFrame(team_rows).sort_values(by="Ortalama Puan", ascending=False)

    filename = f"f1_{num_seasons}_season_LAP_report.xlsx"
    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        df_drivers.to_excel(writer, sheet_name="Pilot İstatistikleri", index=False)
        df_teams.to_excel(writer, sheet_name="Takım İstatistikleri", index=False)

    print(f"\n✅ [BAŞARILI] {num_seasons} sezon ({num_seasons * 24} yarış) tur tur simüle edildi.")
    print(f"📊 Sonuçlar '{filename}' dosyasına kaydedildi.")


if __name__ == "__main__":
    run_mass_simulation(1000)
