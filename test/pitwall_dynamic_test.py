"""
PİT DUVARI DİNAMİK STRATEJİ TESTİ
==================================
İki ölçüm:

A) ESKİ (statik plan + guard) vs YENİ (pit duvarı) — aynı seed'ler:
   - anlamsız geç "plan" piti (son 10 tur)
   - hava piti sonrası <6 turda ikinci (plansız-anlamsız) pit
   - SC/VSC ucuz pit kullanımı
   - pit/araç ve temel gerçekçilik korunuyor mu

B) RİSK ADALETİ — aynı seed'lerde McLaren'ın pit duvarı riski "düşük" vs
   "yüksek" zorlanır: EV (ort. puan) yakın kalmalı, VARYANS yüksek riskte
   artmalı ("kumar = bedava güç değil, adil bahis").

Çalıştırma: python test/pitwall_dynamic_test.py [sezon]   (varsayılan 6)
"""
import os
import sys
import random
from statistics import mean, pstdev

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
from engine.strategy import plan_strategies
from main import load_data

PTS = Championship.POINT_SYSTEM


def run_season(s, drivers, cars, teams, tracks, seed, force_risk=None, force_team="T_MCL"):
    director, engine, quali = RaceDirector(s), LapRaceEngine(s), Qualifying(s)
    champ = Championship()
    m = {"late_plan": 0, "double_after_weather": 0, "sc_pits": 0, "sc_races": 0,
         "pits": 0, "cars": 0, "dnf": 0, "races": 0}
    for no, track in enumerate(tracks, 1):
        random.seed(seed * 1000 + no)
        form = {d: random.gauss(0, s.RACE_FORM_SIGMA) for d in drivers}
        is_q_rain = random.random() < track.weather_volatility
        grid, q3 = quali.simulate_qualifying(drivers, cars, teams, track, is_q_rain, form=form)
        profiles = {d: director.build_profile(dr, cars[teams[dr.team_id].car_id],
                                              track, 3, "normal", False)
                    for d, dr in drivers.items()}
        nl = track.num_laps or s.DEFAULT_RACE_LAPS
        fc = engine.make_forecast(track, nl)
        strat = plan_strategies(grid, fc, nl, s, track=track)
        if force_risk:
            for d, dr in drivers.items():
                if dr.team_id == force_team and isinstance(strat.get(d), dict):
                    strat[d]["risk"] = force_risk
        res = engine.simulate_race(grid, profiles, track, form=form,
                                   strategies=strat, forecast=fc)
        champ.process_race_result(res["classification"])

        m["races"] += 1
        cls = res["classification"]
        m["pits"] += sum(c["pits"] for c in cls)
        m["cars"] += len(cls)
        m["dnf"] += sum(1 for c in cls if c["status"] == "DNF")
        ev = res["events"]
        had_caution = any(e["type"] in ("SC", "VSC") for e in ev)
        if had_caution:
            m["sc_races"] += 1
            m["sc_pits"] += sum(1 for e in ev if e["type"] == "PIT" and "altında" in e["msg"])
        pits_by = {}
        for e in ev:
            if e["type"] == "PIT":
                pits_by.setdefault(e["driver"], []).append((e["lap"], e["msg"]))
                if "plan" in e["msg"] and e["lap"] >= nl - 10:
                    m["late_plan"] += 1
        for laps in pits_by.values():
            for (l1, m1), (l2, m2) in zip(laps, laps[1:]):
                if l2 - l1 < 6 and "hava" in m1 and "hava" not in m2 and "altında" not in m2:
                    m["double_after_weather"] += 1
    team_pts = {}
    for d_id, p in champ.driver_standings.items():
        team_pts[drivers[d_id].team_id] = team_pts.get(drivers[d_id].team_id, 0) + p
    return m, team_pts


def section_a(n, drivers, cars, teams, tracks):
    print("\nA) ESKİ (statik) vs YENİ (pit duvarı) — aynı seed'ler")
    rows = {}
    for label, enabled in [("ESKİ", False), ("YENİ", True)]:
        s = GameSettings()
        s.PITWALL_ENABLED = enabled
        tot = {"late_plan": 0, "double_after_weather": 0, "sc_pits": 0, "sc_races": 0,
               "pits": 0, "cars": 0, "dnf": 0, "races": 0}
        for k in range(n):
            m, _ = run_season(s, *load_data(), seed=4400 + k)
            for key in tot:
                tot[key] += m[key]
        rows[label] = tot
    print(f"   {'Metrik':38s} {'ESKİ':>10s} {'YENİ':>10s}")
    e, y = rows["ESKİ"], rows["YENİ"]
    R = e["races"]
    print(f"   {'Geç anlamsız plan piti / yarış':38s} {e['late_plan']/R:>10.2f} {y['late_plan']/R:>10.2f}")
    print(f"   {'Hava piti sonrası çift pit / yarış':38s} {e['double_after_weather']/R:>10.2f} {y['double_after_weather']/R:>10.2f}")
    print(f"   {'SC/VSC ucuz pit / cautionlı yarış':38s} {e['sc_pits']/max(1,e['sc_races']):>10.2f} {y['sc_pits']/max(1,y['sc_races']):>10.2f}")
    print(f"   {'Pit / araç (ref 1.3-2.2)':38s} {e['pits']/e['cars']:>10.2f} {y['pits']/y['cars']:>10.2f}")
    print(f"   {'DNF / yarış (ref 2-3)':38s} {e['dnf']/R:>10.2f} {y['dnf']/R:>10.2f}")


def section_b(n, drivers, cars, teams, tracks):
    print("\nB) RİSK ADALETİ — McLaren pit duvarı riski zorlanır (aynı seed'ler)")
    out = {}
    for risk in ["düşük", "yüksek"]:
        s = GameSettings()
        pts = []
        for k in range(n):
            _, team_pts = run_season(s, *load_data(), seed=4400 + k, force_risk=risk)
            pts.append(team_pts.get("T_MCL", 0))
        out[risk] = pts
    for risk, pts in out.items():
        print(f"   risk={risk:7s}: ort {mean(pts):5.0f} puan/szn | sapma {pstdev(pts):5.1f} | {sorted(pts)}")
    print("   Beklenti: ortalamalar yakın (adil), sapma yüksek riskte daha büyük (kumar)")


def run(n=6):
    drivers, cars, teams, tracks = load_data()
    print(f"\n{'='*78}")
    print(f" PİT DUVARI DİNAMİK STRATEJİ TESTİ  ({n} sezon/senaryo)")
    print(f"{'='*78}")
    section_a(n, drivers, cars, teams, tracks)
    section_b(n, drivers, cars, teams, tracks)
    print()


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
