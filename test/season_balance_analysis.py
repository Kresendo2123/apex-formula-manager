import os
import random
import sys
from statistics import mean

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.game_settings import GameSettings
from engine.championship import Championship
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.strategy import apply_qualifying_tire_rule, plan_strategies
from main import load_data


def format_gap(seconds):
    if seconds is None:
        return ""
    return f"{seconds:.3f}s"


def expected_overtake_window(engine, track, num_laps):
    difficulty = engine._track_overtaking_difficulty(track)
    center = max(4.0, num_laps * max(0.08, 0.85 - difficulty) * 0.75)
    low = max(0, round(center * 0.65))
    high = round(center * 1.35)
    if difficulty >= 0.72:
        label = "Düşük"
    elif difficulty >= 0.55:
        label = "Orta-Düşük"
    elif difficulty >= 0.38:
        label = "Orta"
    else:
        label = "Yüksek"
    return difficulty, low, high, label


def judge_overtakes(actual, expected_low, expected_high):
    if actual < expected_low:
        return "Beklenenden az"
    if actual > expected_high:
        return "Beklenenden fazla"
    return "Beklenen aralıkta"


def classify_balance(row):
    issues = []
    if row["P17-P22 Podyum"] > 0:
        issues.append("arka sıra podyum")
    if row["En Büyük Kazanç"] >= 12:
        issues.append("çok büyük sıra kazancı")
    if row["Ortalama Ardışık Fark"] < 0.75:
        issues.append("saha fazla sıkışık")
    if row["Ortalama Ardışık Fark"] > 8.0:
        issues.append("saha fazla kopuk")
    if row["Geçiş Uyumu"] == "Beklenenden fazla":
        issues.append("geçiş fazla")
    if row["Geçiş Uyumu"] == "Beklenenden az":
        issues.append("geçiş az")
    if row["DNF"] >= 4:
        issues.append("DNF fazla")
    if row["SC+VSC"] >= 3:
        issues.append("neutralization fazla")
    if row["Yağmur Pitleri"] >= 45:
        issues.append("hava strateji kaosu")

    if not issues:
        return "Dengeli", ""
    if len(issues) <= 2:
        return "İzle", ", ".join(issues)
    return "Şüpheli", ", ".join(issues)


def extract_race_metrics(race_no, track, grid, result, engine, drivers, teams, settings):
    classification = result["classification"]
    events = result["events"]
    num_laps = track.num_laps or settings.DEFAULT_RACE_LAPS
    grid_pos = {d_id: pos for pos, d_id in enumerate(grid, start=1)}

    finishers = [e for e in classification if e["status"] == "FIN" and e["total_time"] is not None]
    top3 = finishers[:3]
    winner_time = top3[0]["total_time"] if top3 else None

    top3_rows = []
    for entry in top3:
        d_id = entry["driver_id"]
        gap_to_winner = None if entry["position"] == 1 else entry["total_time"] - winner_time
        top3_rows.append({
            "Yarış No": race_no,
            "Pist": track.name,
            "Sıra": entry["position"],
            "Pilot": drivers[d_id].name,
            "Takım": teams[entry["team_id"]].name,
            "Grid": grid_pos[d_id],
            "Kazanılan Sıra": grid_pos[d_id] - entry["position"],
            "Toplam Süre": entry["total_time"],
            "Lider Farkı": gap_to_winner,
            "Lider Farkı Format": format_gap(gap_to_winner),
            "Ortalama Yarış Temposu": entry["total_time"] / max(1, entry["laps_completed"]),
            "Pit": entry["pits"],
            "Son Lastik": entry["final_compound"],
        })

    adjacent_gaps = []
    for prev, cur in zip(finishers, finishers[1:]):
        if prev["laps_completed"] == cur["laps_completed"]:
            adjacent_gaps.append(cur["total_time"] - prev["total_time"])

    point_gaps = []
    for prev, cur in zip(finishers[:10], finishers[1:10]):
        if prev["laps_completed"] == cur["laps_completed"]:
            point_gaps.append(cur["total_time"] - prev["total_time"])

    overtakes = sum(1 for ev in events if ev["type"] == "OVERTAKE")
    dnf = sum(1 for ev in events if ev["type"] == "DNF")
    sc = sum(1 for ev in events if ev["type"] == "SC")
    vsc = sum(1 for ev in events if ev["type"] == "VSC")
    red = sum(1 for ev in events if ev["type"] == "RED_FLAG")
    weather_changes = sum(1 for ev in events if ev["type"] == "WEATHER")
    rain_pits = sum(1 for ev in events if ev["type"] == "PIT")

    difficulty, expected_low, expected_high, expected_label = expected_overtake_window(engine, track, num_laps)
    overtake_judgement = judge_overtakes(overtakes, expected_low, expected_high)

    gains = [grid_pos[e["driver_id"]] - e["position"] for e in classification]
    top3_from_back = sum(1 for e in top3 if grid_pos[e["driver_id"]] >= 17)
    top10_from_back = sum(1 for e in finishers[:10] if grid_pos[e["driver_id"]] >= 17)

    row = {
        "Yarış No": race_no,
        "Pist": track.name,
        "Tur": num_laps,
        "Geçiş Zorluğu": round(difficulty, 3),
        "Beklenen Geçiş Seviyesi": expected_label,
        "Beklenen Geçiş Min": expected_low,
        "Beklenen Geçiş Max": expected_high,
        "Gerçek Geçiş": overtakes,
        "Geçiş Uyumu": overtake_judgement,
        "Ortalama Ardışık Fark": round(mean(adjacent_gaps), 3) if adjacent_gaps else None,
        "İlk 10 Ortalama Fark": round(mean(point_gaps), 3) if point_gaps else None,
        "P1-P2": round(top3[1]["total_time"] - top3[0]["total_time"], 3) if len(top3) > 1 else None,
        "P2-P3": round(top3[2]["total_time"] - top3[1]["total_time"], 3) if len(top3) > 2 else None,
        "P1-P3": round(top3[2]["total_time"] - top3[0]["total_time"], 3) if len(top3) > 2 else None,
        "P1 Tempo": round(top3_rows[0]["Ortalama Yarış Temposu"], 3) if len(top3_rows) > 0 else None,
        "P2 Tempo": round(top3_rows[1]["Ortalama Yarış Temposu"], 3) if len(top3_rows) > 1 else None,
        "P3 Tempo": round(top3_rows[2]["Ortalama Yarış Temposu"], 3) if len(top3_rows) > 2 else None,
        "En Büyük Kazanç": max(gains) if gains else 0,
        "En Büyük Kayıp": min(gains) if gains else 0,
        "P17-P22 Podyum": top3_from_back,
        "P17-P22 İlk 10": top10_from_back,
        "DNF": dnf,
        "SC": sc,
        "VSC": vsc,
        "Kırmızı Bayrak": red,
        "SC+VSC": sc + vsc + red,
        "Hava Değişimi": weather_changes,
        "Yağmur Pitleri": rain_pits,
        "Gerçek Yağış": "Evet" if result["rained"] else "Hayır",
        "Maks Islaklık": result["weather_peak"],
    }
    status, notes = classify_balance(row)
    row["Denge Durumu"] = status
    row["Notlar"] = notes
    return row, top3_rows


def simulate_season(seed=44, filename="f1_season_balance_analysis.xlsx"):
    random.seed(seed)
    settings = GameSettings()
    drivers, cars, teams, tracks = load_data()
    director = RaceDirector(settings)
    engine = LapRaceEngine(settings)
    quali = Qualifying(settings)
    champ = Championship()

    race_rows = []
    top3_rows = []
    event_rows = []

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

        race_row, race_top3_rows = extract_race_metrics(
            race_no, track, grid, result, engine, drivers, teams, settings
        )
        race_rows.append(race_row)
        top3_rows.extend(race_top3_rows)

        for ev in result["events"]:
            event_rows.append({
                "Yarış No": race_no,
                "Pist": track.name,
                "Tur": "-" if ev["lap"] == 0 else ev["lap"],
                "Tip": ev["type"],
                "Açıklama": ev["msg"],
            })

    race_df = pd.DataFrame(race_rows)
    top3_df = pd.DataFrame(top3_rows)
    event_df = pd.DataFrame(event_rows)

    summary_rows = [
        {"Metrik": "Seed", "Değer": seed},
        {"Metrik": "Yarış Sayısı", "Değer": len(race_df)},
        {"Metrik": "Ortalama Geçiş", "Değer": round(race_df["Gerçek Geçiş"].mean(), 2)},
        {"Metrik": "Beklenenden Fazla Geçiş Yarışı", "Değer": int((race_df["Geçiş Uyumu"] == "Beklenenden fazla").sum())},
        {"Metrik": "Beklenenden Az Geçiş Yarışı", "Değer": int((race_df["Geçiş Uyumu"] == "Beklenenden az").sum())},
        {"Metrik": "Şüpheli Yarış", "Değer": int((race_df["Denge Durumu"] == "Şüpheli").sum())},
        {"Metrik": "İzlenecek Yarış", "Değer": int((race_df["Denge Durumu"] == "İzle").sum())},
        {"Metrik": "Ortalama Ardışık Fark", "Değer": round(race_df["Ortalama Ardışık Fark"].mean(), 3)},
        {"Metrik": "Ortalama En Büyük Kazanç", "Değer": round(race_df["En Büyük Kazanç"].mean(), 2)},
        {"Metrik": "P17-P22 Podyum Toplam", "Değer": int(race_df["P17-P22 Podyum"].sum())},
        {"Metrik": "DNF Ortalama", "Değer": round(race_df["DNF"].mean(), 2)},
        {"Metrik": "SC+VSC Ortalama", "Değer": round(race_df["SC+VSC"].mean(), 2)},
    ]
    summary_df = pd.DataFrame(summary_rows)

    grouped_df = race_df.groupby("Beklenen Geçiş Seviyesi", as_index=False).agg(
        Yarış=("Pist", "count"),
        Ortalama_Geçiş=("Gerçek Geçiş", "mean"),
        Ortalama_Beklenen_Min=("Beklenen Geçiş Min", "mean"),
        Ortalama_Beklenen_Max=("Beklenen Geçiş Max", "mean"),
        Ortalama_Ardışık_Fark=("Ortalama Ardışık Fark", "mean"),
        Şüpheli=("Denge Durumu", lambda s: int((s == "Şüpheli").sum())),
    )

    output_path = os.path.abspath(filename)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Özet", index=False)
        race_df.to_excel(writer, sheet_name="Yarış Dengesi", index=False)
        top3_df.to_excel(writer, sheet_name="İlk 3 Tempo", index=False)
        grouped_df.to_excel(writer, sheet_name="Pist Tipi Özeti", index=False)
        event_df.to_excel(writer, sheet_name="Olay Logu", index=False)

        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes = "A2"
            for column_cells in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in column_cells)
                ws.column_dimensions[column_cells[0].column_letter].width = min(max_len + 2, 42)

    print(f"✅ Denge analiz raporu yazıldı: {output_path}")
    print(f"Şüpheli yarış: {(race_df['Denge Durumu'] == 'Şüpheli').sum()} / {len(race_df)}")
    print(f"Beklenenden fazla geçiş: {(race_df['Geçiş Uyumu'] == 'Beklenenden fazla').sum()} yarış")
    return output_path


if __name__ == "__main__":
    simulate_season()
