import os
import random
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.game_settings import GameSettings
from engine.championship import Championship
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.strategy import apply_qualifying_tire_rule, plan_strategies
from main import load_data
from test.season_balance_analysis import extract_race_metrics


def _grid_bucket(grid_pos):
    if grid_pos <= 3:
        return "P1-P3"
    if grid_pos <= 10:
        return "P4-P10"
    if grid_pos <= 16:
        return "P11-P16"
    return "P17-P22"


def run_multi_season_analysis(num_seasons=100, seed_start=1000,
                              filename="f1_100_season_balance_report.xlsx"):
    settings = GameSettings()
    all_race_rows = []
    all_top3_rows = []
    champion_rows = []

    print(f"🏁 {num_seasons} sezon / {num_seasons * 24} yarış simüle ediliyor...")

    for season_idx in range(1, num_seasons + 1):
        seed = seed_start + season_idx - 1
        random.seed(seed)

        drivers, cars, teams, tracks = load_data()
        director = RaceDirector(settings)
        engine = LapRaceEngine(settings)
        quali = Qualifying(settings)
        champ = Championship()

        for race_no, track in enumerate(tracks, start=1):
            form = {d_id: random.gauss(0, settings.RACE_FORM_SIGMA) for d_id in drivers}
            is_quali_raining = random.random() < track.weather_volatility
            grid, q3_tire_choices = quali.simulate_qualifying(
                drivers, cars, teams, track, is_quali_raining, form=form
            )

            profiles = {
                d_id: director.build_profile(
                    driver,
                    cars[teams[driver.team_id].car_id],
                    track,
                    aero_level=3,
                    strategy="normal",
                    is_raining=False,
                )
                for d_id, driver in drivers.items()
            }

            num_laps = track.num_laps or settings.DEFAULT_RACE_LAPS
            forecast = engine.make_forecast(track, num_laps)
            strategies = plan_strategies(grid, forecast, num_laps, settings)
            apply_qualifying_tire_rule(strategies, q3_tire_choices, forecast)

            result = engine.simulate_race(
                grid,
                profiles,
                track,
                form=form,
                strategies=strategies,
                forecast=forecast,
            )
            champ.process_race_result(result["classification"])

            race_row, top3_rows = extract_race_metrics(
                race_no, track, grid, result, engine, drivers, teams, settings
            )
            race_row["Sezon"] = season_idx
            race_row["Seed"] = seed
            race_row["Kazanan Grid"] = next(
                grid.index(e["driver_id"]) + 1
                for e in result["classification"]
                if e["position"] == 1
            )
            race_row["Kazanan Grid Grubu"] = _grid_bucket(race_row["Kazanan Grid"])
            all_race_rows.append(race_row)

            for row in top3_rows:
                row["Sezon"] = season_idx
                row["Seed"] = seed
                row["Grid Grubu"] = _grid_bucket(row["Grid"])
                all_top3_rows.append(row)

        if champ.driver_standings:
            champion_id, champion_points = max(champ.driver_standings.items(), key=lambda x: x[1])
            champion_rows.append({
                "Sezon": season_idx,
                "Seed": seed,
                "Şampiyon": drivers[champion_id].name,
                "Takım": teams[drivers[champion_id].team_id].name,
                "Puan": champion_points,
            })

        if season_idx % 10 == 0:
            print(f"  ✓ {season_idx}/{num_seasons} sezon tamamlandı")

    race_df = pd.DataFrame(all_race_rows)
    top3_df = pd.DataFrame(all_top3_rows)
    champions_df = pd.DataFrame(champion_rows)

    overall_rows = [
        {"Metrik": "Sezon", "Değer": num_seasons},
        {"Metrik": "Yarış", "Değer": len(race_df)},
        {"Metrik": "Ortalama P1-P2", "Değer": round(race_df["P1-P2"].mean(), 3)},
        {"Metrik": "Median P1-P2", "Değer": round(race_df["P1-P2"].median(), 3)},
        {"Metrik": "P1-P2 >= 20s Yarış", "Değer": int((race_df["P1-P2"] >= 20).sum())},
        {"Metrik": "P1-P2 >= 30s Yarış", "Değer": int((race_df["P1-P2"] >= 30).sum())},
        {"Metrik": "P1-P2 >= 40s Yarış", "Değer": int((race_df["P1-P2"] >= 40).sum())},
        {"Metrik": "Ortalama P1-P3", "Değer": round(race_df["P1-P3"].mean(), 3)},
        {"Metrik": "Ortalama Ardışık Fark", "Değer": round(race_df["Ortalama Ardışık Fark"].mean(), 3)},
        {"Metrik": "Ortalama İlk 10 Fark", "Değer": round(race_df["İlk 10 Ortalama Fark"].mean(), 3)},
        {"Metrik": "Ortalama Geçiş", "Değer": round(race_df["Gerçek Geçiş"].mean(), 3)},
        {"Metrik": "Beklenenden Fazla Geçiş Oranı", "Değer": round((race_df["Geçiş Uyumu"] == "Beklenenden fazla").mean(), 3)},
        {"Metrik": "Şüpheli Yarış Oranı", "Değer": round((race_df["Denge Durumu"] == "Şüpheli").mean(), 3)},
        {"Metrik": "Yağmurlu Yarış Oranı", "Değer": round((race_df["Gerçek Yağış"] == "Evet").mean(), 3)},
        {"Metrik": "Ortalama DNF", "Değer": round(race_df["DNF"].mean(), 3)},
        {"Metrik": "Ortalama SC+VSC", "Değer": round(race_df["SC+VSC"].mean(), 3)},
        {"Metrik": "P17-P22 Podyum Toplam", "Değer": int(race_df["P17-P22 Podyum"].sum())},
    ]
    overall_df = pd.DataFrame(overall_rows)

    track_df = race_df.groupby(["Yarış No", "Pist"], as_index=False).agg(
        Yarış=("Pist", "count"),
        Ortalama_P1_P2=("P1-P2", "mean"),
        Median_P1_P2=("P1-P2", "median"),
        P1_P2_20s_Üstü=("P1-P2", lambda s: int((s >= 20).sum())),
        P1_P2_30s_Üstü=("P1-P2", lambda s: int((s >= 30).sum())),
        Ortalama_P1_P3=("P1-P3", "mean"),
        Ortalama_Ardışık_Fark=("Ortalama Ardışık Fark", "mean"),
        Ortalama_İlk10_Fark=("İlk 10 Ortalama Fark", "mean"),
        Ortalama_Geçiş=("Gerçek Geçiş", "mean"),
        Beklenen_Fazla_Geçiş=("Geçiş Uyumu", lambda s: int((s == "Beklenenden fazla").sum())),
        Ortalama_DNF=("DNF", "mean"),
        Ortalama_SCVSC=("SC+VSC", "mean"),
        Yağmurlu_Yarış=("Gerçek Yağış", lambda s: int((s == "Evet").sum())),
        Şüpheli=("Denge Durumu", lambda s: int((s == "Şüpheli").sum())),
        P17_P22_Podyum=("P17-P22 Podyum", "sum"),
        Ortalama_En_Büyük_Kazanç=("En Büyük Kazanç", "mean"),
    )

    condition_df = race_df.groupby("Gerçek Yağış", as_index=False).agg(
        Yarış=("Pist", "count"),
        Ortalama_P1_P2=("P1-P2", "mean"),
        Ortalama_P1_P3=("P1-P3", "mean"),
        Ortalama_Ardışık_Fark=("Ortalama Ardışık Fark", "mean"),
        Ortalama_Geçiş=("Gerçek Geçiş", "mean"),
        Ortalama_DNF=("DNF", "mean"),
        Ortalama_SCVSC=("SC+VSC", "mean"),
        Ortalama_Yağmur_Piti=("Yağmur Pitleri", "mean"),
    )

    overtake_df = race_df.groupby(["Beklenen Geçiş Seviyesi", "Geçiş Uyumu"], as_index=False).agg(
        Yarış=("Pist", "count"),
        Ortalama_Geçiş=("Gerçek Geçiş", "mean"),
        Ortalama_P1_P2=("P1-P2", "mean"),
    )

    winner_grid_df = race_df.groupby("Kazanan Grid Grubu", as_index=False).agg(
        Galibiyet=("Pist", "count"),
        Ortalama_P1_P2=("P1-P2", "mean"),
    )

    podium_grid_df = top3_df.groupby(["Sıra", "Grid Grubu"], as_index=False).agg(
        Adet=("Pilot", "count"),
        Ortalama_Grid=("Grid", "mean"),
        Ortalama_Tempo=("Ortalama Yarış Temposu", "mean"),
    )

    champion_df = champions_df.groupby(["Şampiyon", "Takım"], as_index=False).agg(
        Şampiyonluk=("Sezon", "count"),
        Ortalama_Puan=("Puan", "mean"),
    ).sort_values("Şampiyonluk", ascending=False)

    output_path = os.path.abspath(filename)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        overall_df.to_excel(writer, sheet_name="Genel Özet", index=False)
        track_df.to_excel(writer, sheet_name="Pist Ortalamaları", index=False)
        condition_df.to_excel(writer, sheet_name="Yağmur Kuru", index=False)
        overtake_df.to_excel(writer, sheet_name="Geçiş Uyumu", index=False)
        winner_grid_df.to_excel(writer, sheet_name="Kazanan Grid", index=False)
        podium_grid_df.to_excel(writer, sheet_name="Podyum Grid", index=False)
        champion_df.to_excel(writer, sheet_name="Şampiyonlar", index=False)
        race_df.to_excel(writer, sheet_name="Tüm Yarışlar", index=False)

        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes = "A2"
            for column_cells in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in column_cells)
                ws.column_dimensions[column_cells[0].column_letter].width = min(max_len + 2, 42)

    print(f"✅ 100 sezon raporu yazıldı: {output_path}")
    print(f"Ortalama P1-P2: {race_df['P1-P2'].mean():.2f}s")
    print(f"P1-P2 >= 30s: {(race_df['P1-P2'] >= 30).sum()} yarış")
    print(f"Beklenenden fazla geçiş oranı: {(race_df['Geçiş Uyumu'] == 'Beklenenden fazla').mean():.1%}")
    return output_path


if __name__ == "__main__":
    run_multi_season_analysis()
