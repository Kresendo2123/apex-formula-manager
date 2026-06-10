"""
"RUSSELL SON SIRADAN" TESTİ
============================
En iyi araç+sürücü kombosu (Russell/Mercedes) HER yarışa P22'den (son sıra)
başlatılır. Sorular:
  * Yarışları kaçıncı bitiriyor? Önlerde rekabet edebiliyor mu?
  * Startta (kalkışta) ve yarış içinde kaç sıra kazanıyor?
  * Şampiyonada nereye düşüyor?

Sıralama normal koşulur, sonra Russell gridin sonuna alınır (ceza gibi).
Diğer her şey ham motor: gelişim yok, oyuncu stratejisi yok (AI varsayılanı).

Çalıştırma: python test/russell_from_back_test.py [ekstra_sezon]  (varsayılan 7)
"""
import os
import sys
import random
from statistics import mean

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.championship import Championship
from engine.strategy import plan_strategies, apply_qualifying_tire_rule
from main import load_data

TARGET = "D_RUS"


def pos_in(snapshot, d_id):
    return snapshot.index(d_id) + 1 if d_id in snapshot else None


def run_season(s, drivers, cars, teams, tracks, detailed=False):
    director = RaceDirector(s)
    engine = LapRaceEngine(s)
    quali = Qualifying(s)
    champ = Championship()

    rows = []
    finishes, start_gains, race_gains, points_races = [], [], [], 0
    wins = podiums = top5 = dnfs = 0

    for no, track in enumerate(tracks, 1):
        form = {d: random.gauss(0, s.RACE_FORM_SIGMA) for d in drivers}
        is_q_rain = random.random() < track.weather_volatility
        grid, q3 = quali.simulate_qualifying(drivers, cars, teams, track, is_q_rain, form=form)
        natural_q = grid.index(TARGET) + 1
        # Russell'ı gridin SONUNA al (ceza senaryosu)
        grid.remove(TARGET)
        grid.append(TARGET)

        profiles = {d: director.build_profile(dr, cars[teams[dr.team_id].car_id], track, 3, "normal", False)
                    for d, dr in drivers.items()}
        num_laps = track.num_laps or s.DEFAULT_RACE_LAPS
        fc = engine.make_forecast(track, num_laps)
        strat = plan_strategies(grid, fc, num_laps, s, track=track)
        apply_qualifying_tire_rule(strat, q3, fc)
        res = engine.simulate_race(grid, profiles, track, form=form, strategies=strat, forecast=fc)
        champ.process_race_result(res["classification"])

        lp = res["lap_positions"]
        grid_pos = len(grid)  # 22
        start_pos = pos_in(lp[0], TARGET)
        lap1_pos = pos_in(lp[1], TARGET) if len(lp) > 1 else None
        lap5_pos = pos_in(lp[5], TARGET) if len(lp) > 5 else None
        mid_pos = pos_in(lp[len(lp) // 2], TARGET)
        row = next(c for c in res["classification"] if c["driver_id"] == TARGET)
        fin = row["position"] if row["status"] == "FIN" else None
        status = "FIN" if fin else f"DNF({row.get('dnf_detail') or row.get('dnf_cause')})"

        sg = grid_pos - start_pos if start_pos else 0
        start_gains.append(sg)
        if fin:
            finishes.append(fin)
            race_gains.append((start_pos or grid_pos) - fin)
            if fin == 1: wins += 1
            if fin <= 3: podiums += 1
            if fin <= 5: top5 += 1
        else:
            dnfs += 1

        if detailed:
            ev_types = {e["type"] for e in res["events"]}
            kosul = ("yağmur " if res["rained"] else "") + ("SC" if ("SC" in ev_types or "RED_FLAG" in ev_types) else "")
            P = lambda v: f"P{v:<2d}" if v else "out"
            rows.append(f"{no:2d} {track.name[:20]:20s} | doğal Q:P{natural_q:<2d} -> start P22 | "
                        f"kalkış {P(start_pos)} | L1 {P(lap1_pos)} | L5 {P(lap5_pos)} | "
                        f"orta {P(mid_pos)} | bitiş {('P'+str(fin)) if fin else status:>12s} | {kosul}")

    # şampiyona sırası
    std = sorted(champ.driver_standings.items(), key=lambda x: -x[1])
    champ_rank = next(i for i, (d, _) in enumerate(std, 1) if d == TARGET)
    rus_pts = champ.driver_standings.get(TARGET, 0)
    leader = std[0]

    return {
        "rows": rows, "finishes": finishes, "start_gains": start_gains,
        "race_gains": race_gains, "wins": wins, "podiums": podiums, "top5": top5,
        "dnfs": dnfs, "champ_rank": champ_rank, "pts": rus_pts,
        "leader": (leader[0], leader[1]),
    }


def run(extra_seasons=7, car_boost=0, ot_mult=1.0):
    s = GameSettings()
    drivers, cars, teams, tracks = load_data()

    if car_boost:
        # Deney: Mercedes aracının tüm statlarına +boost (seed dosyasına dokunmadan)
        car = cars["C_MER"]
        for stat in ["acceleration", "top_speed", "grip", "reliability", "tire_consumption"]:
            setattr(car, stat, getattr(car, stat) + car_boost)
    if ot_mult != 1.0:
        # Deney: pace-farkı-bazlı sollama duyarlılığı çarpanı (kalıcı ayar değil)
        s.OVERTAKE_PACE_DELTA_SCALE *= ot_mult

    tag = ""
    if car_boost: tag += f" | MERCEDES ARAÇ +{car_boost}"
    if ot_mult != 1.0: tag += f" | OT_PACE_SCALE x{ot_mult:g}"
    print(f"\n{'='*108}")
    print(f" RUSSELL P22'DEN BAŞLIYOR — detaylı sezon (seed=2026){tag}")
    print(f"{'='*108}")
    random.seed(2026)
    det = run_season(s, drivers, cars, teams, tracks, detailed=True)
    for r in det["rows"]:
        print("   " + r)
    print(f"\n   SEZON ÖZETİ: galibiyet {det['wins']} | podyum {det['podiums']} | top5 {det['top5']} | "
          f"DNF {det['dnfs']} | ort. bitiş P{mean(det['finishes']):.1f}")
    print(f"   Kalkışta ort. {mean(det['start_gains']):+.1f} sıra | yarış içinde ort. {mean(det['race_gains']):+.1f} sıra daha")
    print(f"   Şampiyona: P{det['champ_rank']} ({det['pts']} puan) | Şampiyon: "
          f"{drivers[det['leader'][0]].name} ({det['leader'][1]} puan)")

    if extra_seasons > 0:
        agg = {"fin": [], "sg": [], "rg": [], "wins": 0, "pod": 0, "dnf": 0, "rank": [], "pts": []}
        for k in range(extra_seasons):
            random.seed(3000 + k)
            r = run_season(s, drivers, cars, teams, tracks)
            agg["fin"] += r["finishes"]; agg["sg"] += r["start_gains"]; agg["rg"] += r["race_gains"]
            agg["wins"] += r["wins"]; agg["pod"] += r["podiums"]; agg["dnf"] += r["dnfs"]
            agg["rank"].append(r["champ_rank"]); agg["pts"].append(r["pts"])
        n = extra_seasons
        print(f"\n{'='*108}")
        print(f" {n} EK SEZON İSTATİSTİĞİ (her yarış P22'den) ")
        print(f"{'='*108}")
        print(f"   Ort. bitiş: P{mean(agg['fin']):.1f} | galibiyet/szn: {agg['wins']/n:.1f} | "
              f"podyum/szn: {agg['pod']/n:.1f} | DNF/szn: {agg['dnf']/n:.1f}")
        print(f"   Kalkış kazancı ort: {mean(agg['sg']):+.1f} sıra | yarış içi ek kazanç ort: {mean(agg['rg']):+.1f} sıra")
        print(f"   Şampiyona sırası dağılımı: {sorted(agg['rank'])} | ort. puan: {mean(agg['pts']):.0f}")
        from collections import Counter
        fin_dist = Counter()
        for f in agg["fin"]:
            if f <= 3: fin_dist["P1-3"] += 1
            elif f <= 6: fin_dist["P4-6"] += 1
            elif f <= 10: fin_dist["P7-10"] += 1
            else: fin_dist["P11+"] += 1
        tot = len(agg["fin"])
        print("   Bitiş dağılımı: " + " | ".join(f"{k}: %{v/tot*100:.0f}" for k, v in
              sorted(fin_dist.items())))
    print()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    boost = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    ot_mult = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    run(n, boost, ot_mult)
