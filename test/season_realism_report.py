"""
SEZON GERÇEKÇİLİK RAPORU (yarış-yarış)
=======================================
HAM motor (gelişim YOK, antrenman YOK, oyuncu pit stratejisi YOK — AI varsayılanı)
ile tek sezon koşar ve her yarışı gerçekçilik/tutarlılık açısından inceler:

  * P1-P2 bitiş farkı vs takımların YARIŞ ÖNCESİ beklenen tempo farkı
  * "Yakın tempolu takımlar arasında açıklanamayan uçurum var mı?" denetimi
    (motorun kayıp dökümü ile SEBEP gösterilir: pit/hasar/mücadele/kirli hava)
  * Sezon geneli: takım başına beklenen vs gerçekleşen tempo + sapma dökümü

Gerçek F1 referansları (2022-2024 dönemi, yaklaşık):
  * P1-P2 farkı medyanı ~5-10s; %20-30 yarış <3s; >25s fark ~%10-15 (dominasyon)
  * Geç SC çıkan yarışlarda fark doğal olarak küçülür.

Çalıştırma: python test/season_realism_report.py [seed]   (varsayılan 2026)
"""
import os
import sys
import random
from statistics import mean, median

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.strategy import plan_strategies, apply_qualifying_tire_rule
from main import load_data

BREAKDOWN_KEYS = ["pit", "repair", "incident", "battle", "dirty_air"]


def team_expected_pace(engine, profiles, drivers, teams, track):
    """Takım başına temiz-hava beklenen tur süresi (iki pilotun ortalaması)."""
    pace = {}
    for t_id in teams:
        ds = [d for d in drivers.values() if d.team_id == t_id]
        pace[t_id] = mean(engine._base_lap_time(profiles[d.id]["base_power"], track) for d in ds)
    return pace


def run(seed=2026):
    random.seed(seed)
    s = GameSettings()
    drivers, cars, teams, tracks = load_data()
    director = RaceDirector(s)
    engine = LapRaceEngine(s)
    quali = Qualifying(s)

    race_rows = []
    gaps = []
    suspicious = []
    expected_match = pole_win = 0
    # takım sezon toplamları
    tstats = {t: {"exp": [], "act": [], "comp": {k: [] for k in BREAKDOWN_KEYS}, "aero": []}
              for t in teams}

    print(f"\n{'='*100}")
    print(f" SEZON GERÇEKÇİLİK RAPORU — HAM MOTOR (seed={seed}, gelişim/oyuncu stratejisi YOK) ")
    print(f"{'='*100}\n")

    for no, track in enumerate(tracks, 1):
        form = {d: random.gauss(0, s.RACE_FORM_SIGMA) for d in drivers}
        is_q_rain = random.random() < track.weather_volatility
        grid, q3 = quali.simulate_qualifying(drivers, cars, teams, track, is_q_rain, form=form)
        profiles = {d: director.build_profile(dr, cars[teams[dr.team_id].car_id], track, 3, "normal", False)
                    for d, dr in drivers.items()}
        num_laps = track.num_laps or s.DEFAULT_RACE_LAPS
        fc = engine.make_forecast(track, num_laps)
        strat = plan_strategies(grid, fc, num_laps, s)
        apply_qualifying_tire_rule(strat, q3, fc)
        res = engine.simulate_race(grid, profiles, track, form=form, strategies=strat, forecast=fc)

        cls = res["classification"]
        ev_types = [e["type"] for e in res["events"]]
        sc_n = ev_types.count("SC") + ev_types.count("RED_FLAG")
        vsc_n = ev_types.count("VSC")
        rained = res["rained"]

        exp_pace = team_expected_pace(engine, profiles, drivers, teams, track)
        fastest_team = min(exp_pace, key=exp_pace.get)

        fin = [c for c in cls if c["status"] == "FIN"]
        p1, p2 = fin[0], fin[1]
        winner_perlap = p1["total_time"] / p1["laps_completed"]
        gap = (p2["total_time"] / p2["laps_completed"]) * p1["laps_completed"] - p1["total_time"] \
            if p2["laps_completed"] != p1["laps_completed"] else p2["total_time"] - p1["total_time"]
        gaps.append(gap)
        if p1["team_id"] == fastest_team:
            expected_match += 1
        if p1["driver_id"] == grid[0]:
            pole_win += 1

        # P1-P2 takımlarının beklenen tempo farkı (s/tur). Pozitif = kazanan takım beklenen hızlı.
        exp_delta = exp_pace[p2["team_id"]] - exp_pace[p1["team_id"]]
        pred_gap = exp_delta * num_laps

        # Not / tutarlılık değerlendirmesi
        note = ""
        if gap < 3:
            note = "kıl payı final"
        if gap > 25 and not rained and sc_n == 0:
            if exp_delta >= 0.12:
                note = "büyük fark (tempo farkı — normal)"
            else:
                # yakın tempoda büyük fark -> sebep ara (P2'nin kayıp dökümü vs P1)
                b1, b2 = p1["loss_breakdown"], p2["loss_breakdown"]
                deltas = {k: b2[k] - b1[k] for k in BREAKDOWN_KEYS}
                main_k = max(deltas, key=deltas.get)
                note = f"SUPHELI: yakın tempo ({exp_delta:+.3f}s/t) ama {gap:.0f}s fark — en büyük etken: {main_k} (+{deltas[main_k]:.0f}s)"
                suspicious.append((no, track.name, gap, exp_delta, deltas))
        if sc_n > 0 and gap < 6 and not note:
            note = "SC sonrası yakın bitiş"

        # takım sezon istatistikleri (yalnız FIN pilotlar, tur-normalize)
        for c in fin:
            t_id = c["team_id"]
            act_perlap = c["total_time"] / c["laps_completed"] - winner_perlap
            expd = exp_pace[t_id] - exp_pace[p1["team_id"]]
            tstats[t_id]["exp"].append(expd)
            tstats[t_id]["act"].append(act_perlap)
            wb = p1["loss_breakdown"]
            for k in BREAKDOWN_KEYS:
                tstats[t_id]["comp"][k].append((c["loss_breakdown"][k] - wb[k]) / c["laps_completed"])
            tstats[t_id]["aero"].append((c["loss_breakdown"]["aero_gain"] - wb["aero_gain"]) / c["laps_completed"])

        weather = "yağmur" if rained else "kuru"
        race_rows.append(
            f"{no:2d} {track.name[:21]:21s} {weather:6s} SC:{sc_n} VSC:{vsc_n} DNF:{res['dnf_count']:2d} | "
            f"{drivers[p1['driver_id']].name[:9]:9s}({teams[p1['team_id']].name[:3]}) > "
            f"{drivers[p2['driver_id']].name[:9]:9s}({teams[p2['team_id']].name[:3]}) "
            f"fark {gap:5.1f}s | beklΔ {exp_delta:+.3f}s/t (~{pred_gap:+.0f}s) | {note}"
        )

    print("1) YARIŞ YARIŞ SONUÇLAR  (fark = P1-P2; beklΔ = takımların yarış öncesi tempo farkı)")
    for row in race_rows:
        print("   " + row)

    n = len(gaps)
    print(f"\n2) P1-P2 FARK DAĞILIMI vs GERÇEK F1")
    print(f"   medyan {median(gaps):.1f}s | ort {mean(gaps):.1f}s | min {min(gaps):.1f}s | max {max(gaps):.1f}s")
    b1 = sum(1 for g in gaps if g < 3); b2 = sum(1 for g in gaps if 3 <= g < 10)
    b3 = sum(1 for g in gaps if 10 <= g < 25); b4 = sum(1 for g in gaps if g >= 25)
    print(f"   <3s: {b1} ({b1/n*100:.0f}%) | 3-10s: {b2} ({b2/n*100:.0f}%) | "
          f"10-25s: {b3} ({b3/n*100:.0f}%) | >25s: {b4} ({b4/n*100:.0f}%)")
    print(f"   Gerçek F1 ~: <3s %20-30 | medyan 5-10s | >25s %10-15")
    print(f"   Beklenen-en-hızlı takımın kazandığı yarış: {expected_match}/{n} | Pole->galibiyet: {pole_win}/{n}")

    print(f"\n3) TAKIM TEMPO ANALİZİ (sezon ort., s/tur, kazanana göre; FIN pilotlar)")
    print(f"   {'Takım':13s} {'BeklΔ':>7s} {'GerçekΔ':>8s} {'Sapma':>7s} | "
          f"{'pit':>6s} {'hasar':>6s} {'olay':>6s} {'mücad':>6s} {'k.hava':>6s} {'aeroG':>6s} {'diğer*':>7s}")
    print(f"   {'-'*95}")
    order = sorted(teams, key=lambda t: mean(tstats[t]["exp"]) if tstats[t]["exp"] else 9)
    for t_id in order:
        st = tstats[t_id]
        if not st["exp"]:
            continue
        e, a = mean(st["exp"]), mean(st["act"])
        comps = {k: mean(st["comp"][k]) for k in BREAKDOWN_KEYS}
        aero = mean(st["aero"])
        dev = a - e
        other = dev - sum(comps.values()) + aero  # aero kazanç olduğundan geri eklenir
        print(f"   {teams[t_id].name[:13]:13s} {e:>+7.3f} {a:>+8.3f} {dev:>+7.3f} | "
              f"{comps['pit']:>+6.3f} {comps['repair']:>+6.3f} {comps['incident']:>+6.3f} "
              f"{comps['battle']:>+6.3f} {comps['dirty_air']:>+6.3f} {-aero:>+6.3f} {other:>+7.3f}")
    print("   *diğer = lastik aşınma farkı + SC sıkışması (yavaş takım lehine, negatif) + start avantajı + şans")

    if suspicious:
        print(f"\n4) ŞÜPHELİ YARIŞLAR ({len(suspicious)} adet — yakın tempo, açıklanamayan uçurum)")
        for no, name, gap, expd, deltas in suspicious:
            ds = ", ".join(f"{k}:{v:+.0f}s" for k, v in deltas.items() if abs(v) >= 1)
            print(f"   Yarış {no} {name}: fark {gap:.0f}s, beklenen {expd:+.3f}s/t | P2'nin ek kayıpları: {ds}")
    else:
        print(f"\n4) ŞÜPHELİ YARIŞ YOK — yakın tempolu takımlar arasında açıklanamayan uçurum bulunamadı.")
    print()


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    run(seed)
