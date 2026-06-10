"""
VARYANS / SÜRPRİZ DENETİMİ
==========================
"Her şey sabitse kazananlar hep aynı olur" sorusunu ölçer: motor ne kadar
sürpriz, drama ve kaos üretiyor? Gerçek F1 referanslarıyla kıyaslar.
Gelişim KAPALI (sabit statlar) — yani bu, varyansın TABANIDIR; oyunda sezon içi
gelişim + oyuncu kararları bunun üstüne ek çeşitlilik koyar.

Çalıştırma: python test/variance_audit.py [sezon_sayısı]   (varsayılan 30)
"""
import os
import sys
import random
from collections import Counter, defaultdict

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

TOP3 = {"T_MER", "T_FER", "T_MCL"}          # seed gücüne göre üst küme
BOTTOM4 = {"T_WIL", "T_VCB", "T_AUD", "T_CAD"}  # seed gücüne göre alt küme


def run(n_seasons=30):
    s = GameSettings()
    drivers, cars, teams, tracks = load_data()
    director = RaceDirector(s)
    engine = LapRaceEngine(s)
    quali = Qualifying(s)

    races = 0
    winners_per_season = []
    win_teams_per_season = []
    surprise_wins = 0                 # top3 dışı takım galibiyeti
    surprise_wins_chaotic = 0         # bunların kaçı yağmur/SC yarışında
    surprise_podiums = 0              # top3 dışı podyum (yarış başına sayılır)
    bottom4_points_per_season = []
    wins_from_p5plus = 0
    winner_grid_sum = 0
    pos_change_sum = 0
    pos_change_n = 0
    driver_titles = Counter()
    team_titles = Counter()
    biggest_charge = 0                # tek yarışta en çok pozisyon kazanma
    podium_from_p10plus = 0           # P10+ startla podyum (büyük sürpriz)

    # puanlama (Championship ile aynı varsayım: standart F1)
    PTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}

    for season in range(n_seasons):
        champ = Championship()
        season_winners = set()
        season_win_teams = set()
        bottom4_pts = 0

        for track in tracks:
            form = {d: random.gauss(0, s.RACE_FORM_SIGMA) for d in drivers}
            is_q_rain = random.random() < track.weather_volatility
            grid, q3 = quali.simulate_qualifying(drivers, cars, teams, track, is_q_rain, form=form)
            grid_pos = {d_id: i + 1 for i, d_id in enumerate(grid)}
            profiles = {d: director.build_profile(dr, cars[teams[dr.team_id].car_id], track, 3, "normal", False)
                        for d, dr in drivers.items()}
            num_laps = track.num_laps or s.DEFAULT_RACE_LAPS
            fc = engine.make_forecast(track, num_laps)
            strat = plan_strategies(grid, fc, num_laps, s, track=track)
            apply_qualifying_tire_rule(strat, q3, fc)
            res = engine.simulate_race(grid, profiles, track, form=form, strategies=strat, forecast=fc)
            champ.process_race_result(res["classification"])
            races += 1

            cls = res["classification"]
            ev_types = {e["type"] for e in res["events"]}
            chaotic = res["rained"] or ("SC" in ev_types) or ("RED_FLAG" in ev_types)

            winner = next(c for c in cls if c["position"] == 1)
            season_winners.add(winner["driver_id"])
            season_win_teams.add(winner["team_id"])
            wg = grid_pos[winner["driver_id"]]
            winner_grid_sum += wg
            if wg >= 5:
                wins_from_p5plus += 1
            if winner["team_id"] not in TOP3:
                surprise_wins += 1
                if chaotic:
                    surprise_wins_chaotic += 1

            for c in cls:
                if c["status"] == "FIN":
                    delta = grid_pos[c["driver_id"]] - c["position"]
                    pos_change_sum += abs(delta)
                    pos_change_n += 1
                    if delta > biggest_charge:
                        biggest_charge = delta
                if c["position"] <= 3:
                    if c["team_id"] not in TOP3:
                        surprise_podiums += 1
                    if grid_pos[c["driver_id"]] >= 10:
                        podium_from_p10plus += 1
                if c["status"] == "FIN" and c["team_id"] in BOTTOM4:
                    bottom4_pts += PTS.get(c["position"], 0)

        winners_per_season.append(len(season_winners))
        win_teams_per_season.append(len(season_win_teams))
        bottom4_points_per_season.append(bottom4_pts)

        dstd = champ.driver_standings
        tstd = champ.team_standings
        if dstd:
            driver_titles[max(dstd, key=dstd.get)] += 1
        if tstd:
            team_titles[max(tstd, key=tstd.get)] += 1

    R = races
    N = n_seasons
    print(f"\n{'='*78}")
    print(f" VARYANS / SÜRPRİZ DENETİMİ  ({N} sezon = {R} yarış, gelişim KAPALI) ")
    print(f"{'='*78}\n")

    print("1) SEZON İÇİ ÇEŞİTLİLİK")
    print(f"   {'Metrik':40s} {'Motor':>8s}   {'Gerçek F1 ~':>12s}")
    print(f"   {'-'*64}")
    print(f"   {'Farklı kazanan pilot / sezon':40s} {sum(winners_per_season)/N:>8.1f}   {'3 – 7':>12s}")
    print(f"   {'Farklı kazanan takım / sezon':40s} {sum(win_teams_per_season)/N:>8.1f}   {'2 – 4':>12s}")
    print(f"   {'Top-3 dışı takım galibiyeti / sezon':40s} {surprise_wins/N:>8.1f}   {'0 – 2':>12s}")
    if surprise_wins:
        print(f"   {'  - bunların yağmur/SC yarışında payı':40s} {surprise_wins_chaotic/surprise_wins*100:>7.0f}%   {'çoğunluk':>12s}")
    print(f"   {'Top-3 dışı podyum / sezon':40s} {surprise_podiums/N:>8.1f}   {'2 – 8':>12s}")
    print(f"   {'Alt-4 takım toplam puanı / sezon':40s} {sum(bottom4_points_per_season)/N:>8.0f}   {'10 – 60':>12s}")

    print(f"\n2) YARIŞ İÇİ KARIŞMA (grid -> bitiş)")
    print(f"   {'Kazananın ort. grid pozisyonu':40s} {winner_grid_sum/R:>8.1f}   {'~1.5 – 2.5':>12s}")
    print(f"   {'P5+ gridden kazanılan yarış %':40s} {wins_from_p5plus/R*100:>7.1f}%   {'~8 – 18%':>12s}")
    print(f"   {'Ort. |grid - bitiş| (bitirenler)':40s} {pos_change_sum/max(1,pos_change_n):>8.1f}   {'~2.5 – 4':>12s}")
    print(f"   {'P10+ startla podyum (toplam)':40s} {podium_from_p10plus:>8d}   {'nadir ama olur':>12s}")
    print(f"   {'En büyük tek-yarış remontadası':40s} {biggest_charge:>8d}   {'10 – 15 poz.':>12s}")

    print(f"\n3) SEZONLAR ARASI ÇEŞİTLİLİK (şampiyonluk)")
    print(f"   Pilot şampiyonları: ", end="")
    for d_id, n in driver_titles.most_common():
        print(f"{drivers[d_id].name} {n}/{N}", end="  ")
    print(f"\n   Takım şampiyonları: ", end="")
    for t_id, n in team_titles.most_common():
        print(f"{teams[t_id].name} {n}/{N}", end="  ")
    print("\n")
    print("   Gerçek F1 notu: tek takımın dominasyon dönemi gerçek F1'de de olur")
    print("   (2014-2020 Mercedes). Oyunda sezon içi gelişim + oyuncu kararları bu")
    print("   tabana ek varyans koyar; buradaki rakamlar 'her şey sabitken' tabandır.\n")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    run(n)
