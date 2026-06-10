"""
GERÇEKÇİLİK DENETİMİ
====================
Motorun çıktısını GERÇEK F1 referans aralıklarıyla kıyaslar. Sezon-içi gelişim
KAPALI (sabit seed statları) — böylece araç/pilot/pist/koşul katsayılarının
ham gerçekçiliği izole ölçülür.

Çalıştırma: python test/realism_audit.py [sezon_sayısı]   (varsayılan 40)
"""
import os
import sys
import random
from collections import defaultdict

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


def run(n_seasons=40):
    s = GameSettings()
    drivers, cars, teams, tracks = load_data()
    director = RaceDirector(s)
    engine = LapRaceEngine(s)
    quali = Qualifying(s)

    # toplananlar
    races = 0
    dnf_total = dnf_mech = dnf_crash = 0
    sc_races = vsc_races = red_races = rain_races = 0
    overtakes_total = 0          # NOT: motor yalnız ilk-10 sollamasını logluyor
    pits_total = car_laps_field = 0
    team_wins = defaultdict(int)
    team_points_season = defaultdict(list)   # sezon başına toplam puan
    team_title = defaultdict(int)
    finish_classified = 0
    overtakes_by_track = defaultdict(list)

    for season in range(n_seasons):
        champ = Championship()
        for track in tracks:
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
            champ.process_race_result(res["classification"])
            races += 1

            cls = res["classification"]
            ev = res["events"]
            ev_types = [e["type"] for e in ev]

            winner = next(c for c in cls if c["position"] == 1)
            team_wins[winner["team_id"]] += 1

            dnfs = [c for c in cls if c["status"] == "DNF"]
            dnf_total += len(dnfs)
            for c in dnfs:
                if c.get("dnf_cause") == "mech":
                    dnf_mech += 1
                elif c.get("dnf_cause") == "crash":
                    dnf_crash += 1
            finish_classified += sum(1 for c in cls if c["status"] == "FIN")

            if "SC" in ev_types or "RED_FLAG" in ev_types:
                sc_races += 1
            if "VSC" in ev_types:
                vsc_races += 1
            if "RED_FLAG" in ev_types:
                red_races += 1
            if res["rained"]:
                rain_races += 1
            ot = sum(1 for t in ev_types if t == "OVERTAKE")
            overtakes_total += ot
            overtakes_by_track[track.name].append(ot)
            pits_total += sum(c["pits"] for c in cls)
            car_laps_field += len(cls)

        # sezon sonu: takım şampiyonu + puanlar
        ts = champ.team_standings
        for t_id, pts in ts.items():
            team_points_season[t_id].append(pts)
        if ts:
            champ_team = max(ts, key=ts.get)
            team_title[champ_team] += 1

    R = races
    print(f"\n{'='*78}")
    print(f" GERÇEKÇİLİK DENETİMİ  ({n_seasons} sezon = {R} yarış, gelişim KAPALI) ")
    print(f"{'='*78}\n")

    print("1) YARIŞ KOŞULLARI  (motor çıktısı  vs  gerçek F1 referansı)")
    print(f"   {'Metrik':32s} {'Motor':>10s}   {'Gerçek F1 ~':>14s}")
    print(f"   {'-'*60}")
    print(f"   {'DNF / yarış':32s} {dnf_total/R:>10.2f}   {'2.0 – 3.0':>14s}")
    print(f"   {'  - mekanik DNF / yarış':32s} {dnf_mech/R:>10.2f}   {'0.7 – 1.3':>14s}")
    print(f"   {'  - kaza DNF / yarış':32s} {dnf_crash/R:>10.2f}   {'0.8 – 1.6':>14s}")
    print(f"   {'SC (veya kırmızı) olan yarış %':32s} {sc_races/R*100:>9.1f}%   {'~35 – 50%':>14s}")
    print(f"   {'VSC olan yarış %':32s} {vsc_races/R*100:>9.1f}%   {'~30 – 45%':>14s}")
    print(f"   {'Kırmızı bayrak yarış %':32s} {red_races/R*100:>9.1f}%   {'~5 – 8%':>14s}")
    print(f"   {'Yağmurlu yarış %':32s} {rain_races/R*100:>9.1f}%   {'~12 – 20%':>14s}")
    print(f"   {'Pit / araç / yarış':32s} {pits_total/car_laps_field:>10.2f}   {'1.3 – 2.2':>14s}")
    print(f"   {'Sollama / yarış (sadece ilk-10!)':32s} {overtakes_total/R:>10.1f}   {'~15 – 40 (top10)':>14s}")

    print(f"\n2) REKABET DENGESİ  (araç + pilot güçleri)")
    print(f"   {'Takım':14s} {'Galibiyet%':>10s} {'Ort.Sezon P':>12s} {'Şampiyon%':>10s}")
    print(f"   {'-'*50}")
    order = sorted(team_points_season, key=lambda t: -sum(team_points_season[t]))
    for t_id in order:
        name = teams[t_id].name
        wins_pct = team_wins[t_id] / R * 100
        avg_pts = sum(team_points_season[t_id]) / n_seasons
        title_pct = team_title[t_id] / n_seasons * 100
        print(f"   {name[:14]:14s} {wins_pct:>9.1f}% {avg_pts:>12.0f} {title_pct:>9.1f}%")

    # özet rekabet metrikleri
    best = order[0]
    worst = order[-1]
    print(f"\n   En iyi takım galibiyet payı: {team_wins[best]/R*100:.1f}%  (gerçek F1: dominant ~%50-80, dengeli ~%30-45)")
    print(f"   En iyi takım şampiyonluk oranı: {team_title[best]/n_seasons*100:.0f}%")
    top_pts = sum(team_points_season[best])/n_seasons
    bot_pts = sum(team_points_season[worst])/n_seasons
    print(f"   Puan uçurumu (en iyi/en kötü ort. sezon): {top_pts:.0f} / {bot_pts:.0f}  (oran {top_pts/max(1,bot_pts):.1f}x)")

    print(f"\n3) SOLLAMA — PİST HASSASİYETİ (ilk-10 sollama ort., birkaç pist)")
    sample = ["Monaco", "Hungary (Hungaroring)", "Italy (Monza)", "Belgium (Spa)",
              "Bahrain (Sakhir)", "Singapore"]
    for nm in sample:
        if nm in overtakes_by_track:
            vals = overtakes_by_track[nm]
            print(f"   {nm[:24]:24s} {sum(vals)/len(vals):>6.1f}")
    print()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    run(n)
