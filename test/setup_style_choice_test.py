"""
ARAÇ AYARI (AERO) + SÜRÜŞ STİLİ SEÇİM DENGESİ TESTİ
====================================================
Kullanıcının yarış öncesi 3 girdisinden ikisini ölçer:
  * Araç ayarı  = aero seviyesi 1-5 (top_speed <-> grip takası, +-%10)
  * Sürüş stili = aggressive / normal / long_stint (pace <-> aşınma <-> risk)
(Pit stratejisi ayrı test edildi: strategy_scenario_test.py)

Yöntem:
  - DENEK takımın iki pilotu seçilen politikayı uygular, diğer 20 araç
    varsayılanda (aero 3, normal) kalır.
  - Aynı seed'ler tüm politikalarda kullanılır; her yarış öncesi reseed
    edildiği için grid, hava ve form TÜM politikalarda birebir aynıdır.
    Yani fark SADECE seçimden gelir (eşleştirilmiş deney).
  - "aero İYİ" = her pist için matematiksel en iyi seviye,
    "aero KÖTÜ" = en kötü seviye (bilinçsiz oyuncu simülasyonu).

Denekler: McLaren (şampiyonluk takipçisi) ve Williams (orta sıra).

NOT: Sıralama (qualifying) bu seçimleri KULLANMIYOR — etki sadece yarışta.

Çalıştırma: python test/setup_style_choice_test.py [sezon_sayısı]   (varsayılan 5)
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

SUBJECTS = [("T_MCL", "McLaren (şampiyonluk takipçisi)"),
            ("T_WIL", "Williams (orta sıra)")]

# (aero_modu, stil): aero_modu None=3 sabit, "ideal"/"extreme"/"worst"=pist bazlı seçim
POLICIES = [
    ("varsayılan (aero3 + normal)",     None,      "normal"),
    ("aero İDEAL (stil normal)",        "ideal",   "normal"),
    ("aero hep UÇ (1/5, stil normal)",  "extreme", "normal"),
    ("aero KÖTÜ (stil normal)",         "worst",   "normal"),
    ("stil AGRESİF (aero 3)",           None,      "aggressive"),
    ("stil LONG_STINT (aero 3)",        None,      "long_stint"),
    ("KOMBO: aero ideal + agresif",     "ideal",   "aggressive"),
    ("KOMBO: aero ideal + long_stint",  "ideal",   "long_stint"),
]


def pick_aero(s, track, mode):
    """Pist idealine göre aero seçimi (1-5)."""
    if mode is None:
        return 3
    ideal = RaceDirector.ideal_aero(track, s)
    if mode == "ideal":      # bilgili oyuncu: ideale yuvarla
        return int(round(ideal))
    if mode == "extreme":    # eski meta: ideal yönündeki uca savrul
        return 1 if ideal < 3 else 5
    # worst: idealden en uzak kademe (bilinçsiz oyuncu)
    return max((1, 2, 3, 4, 5), key=lambda lvl: abs(lvl - ideal))


def run_season(s, drivers, cars, teams, tracks, subject, aero_mode, style, season_seed):
    director = RaceDirector(s)
    engine = LapRaceEngine(s)
    quali = Qualifying(s)
    champ = Championship()

    wins = podiums = dnfs = 0
    aero_picks = []

    for no, track in enumerate(tracks, 1):
        # Reseed: grid/hava/form tüm politikalarda birebir aynı olsun
        random.seed(season_seed * 1000 + no)
        form = {d: random.gauss(0, s.RACE_FORM_SIGMA) for d in drivers}
        is_q_rain = random.random() < track.weather_volatility
        grid, q3 = quali.simulate_qualifying(drivers, cars, teams, track, is_q_rain, form=form)

        profiles = {}
        for d, dr in drivers.items():
            car = cars[teams[dr.team_id].car_id]
            if dr.team_id == subject:
                aero = pick_aero(s, track, aero_mode)
                profiles[d] = director.build_profile(dr, car, track, aero, style, False)
                aero_picks.append(aero)
            else:
                profiles[d] = director.build_profile(dr, car, track, 3, "normal", False)

        num_laps = track.num_laps or s.DEFAULT_RACE_LAPS
        fc = engine.make_forecast(track, num_laps)
        strat = plan_strategies(grid, fc, num_laps, s)
        apply_qualifying_tire_rule(strat, q3, fc)
        res = engine.simulate_race(grid, profiles, track, form=form, strategies=strat, forecast=fc)
        champ.process_race_result(res["classification"])

        for row in res["classification"]:
            if drivers[row["driver_id"]].team_id != subject:
                continue
            if row["status"] == "FIN":
                if row["position"] == 1: wins += 1
                if row["position"] <= 3: podiums += 1
            else:
                dnfs += 1

    # takımlar şampiyonası
    team_pts = {}
    for d_id, pts in champ.driver_standings.items():
        team_pts[drivers[d_id].team_id] = team_pts.get(drivers[d_id].team_id, 0) + pts
    ranking = sorted(team_pts.items(), key=lambda x: -x[1])
    rank = next(i for i, (t, _) in enumerate(ranking, 1) if t == subject)

    return {"pts": team_pts.get(subject, 0), "rank": rank,
            "wins": wins, "podiums": podiums, "dnfs": dnfs, "aero_picks": aero_picks}


def run(n_seasons=5):
    s = GameSettings()
    drivers, cars, teams, tracks = load_data()

    print(f"\n{'='*100}")
    print(f" ARAÇ AYARI + SÜRÜŞ STİLİ SEÇİM TESTİ — {n_seasons} eşleştirilmiş sezon / politika")
    print(f" (Denek takımın 2 pilotu politikayı uygular, kalan 20 araç hep aero3+normal)")
    print(f"{'='*100}")

    for subject, label in SUBJECTS:
        print(f"\n--- DENEK: {label} ---")
        print(f"{'Politika':38s} {'Puan/szn':>9s} {'Δbaz':>6s} {'Sıra':>5s} {'Gal/szn':>8s} {'Pod/szn':>8s} {'DNF/szn':>8s}")
        print("-" * 90)
        base_pts = None
        for pol_label, aero_mode, style in POLICIES:
            results = [run_season(s, drivers, cars, teams, tracks, subject,
                                  aero_mode, style, 7000 + k) for k in range(n_seasons)]
            pts = mean(r["pts"] for r in results)
            if base_pts is None:
                base_pts = pts
            print(f"{pol_label:38s} {pts:9.0f} {pts-base_pts:+6.0f} "
                  f"{mean(r['rank'] for r in results):5.1f} "
                  f"{sum(r['wins'] for r in results)/n_seasons:8.1f} "
                  f"{sum(r['podiums'] for r in results)/n_seasons:8.1f} "
                  f"{sum(r['dnfs'] for r in results)/n_seasons:8.1f}")

    # Pist başına ideal aero kademesi dağılımı (bilgi amaçlı)
    dist = {}
    for t in tracks:
        lvl = pick_aero(s, t, "ideal")
        dist[lvl] = dist.get(lvl, 0) + 1
    print(f"\nBİLGİ: Pist başına İDEAL aero kademesi dağılımı: "
          + ", ".join(f"seviye {k}: {v} pist" for k, v in sorted(dist.items())))
    print("BİLGİ: Sıralama turları aero/stil seçimini KULLANMIYOR (grid hep aynı kalıyor).\n")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run(n)
