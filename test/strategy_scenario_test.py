"""
STRATEJİ SEÇİMİ SENARYO TESTİ
==============================
Yarış-öncesi strateji menüsünün (engine/strategy.py: build_strategy_options)
etkisini, adilliğini ve dengesini ölçer. İki senaryo kıyaslanır:

  BASELINE : Herkes AI varsayılanı (plan_strategies) — "strateji seçimi yok" dünyası.
  CHOICES  : Gerçekçi şampiyona anlatısı — takımlar konumlarına göre seçer:
      * Mercedes (lider, puanı yeterli)      -> Güvenli 1-stop
      * Ferrari & McLaren (şampiyona kovalar)-> Agresif 2-stop; yağmur riski varsa SLICK KUMARI
      * Orta saha (RBR, AST, ALP, HAS)       -> Ters strateji; yağmur riski varsa TEDBİRLİ ISLAK
        (kaos onların tek şansı — erken inter çağrısı sürpriz podyum getirebilir)
      * Alt takımlar (WIL, VCB, AUD, CAD)    -> Piyango: her yarış rastgele uç seçenek

Ölçülenler: takım başına puan/galibiyet/podyum değişimi (EV etkisi), sezon puanı
standart sapması (varyans etkisi), kumarların yağmurlu/kuru yarışlardaki getirisi
(risk/ödül adilliği), pit sayısı değişimi.

Adillik kriteri: seçimler EV'yi (ortalama getiriyi) az, VARYANSI çok değiştirmeli.
"Agresif her zaman kazanır" çıkarsa meta çözülür (kötü); "riskli = bazen büyük
kazanç bazen büyük kayıp" çıkarsa adil kumardır (iyi).

Çalıştırma: python test/strategy_scenario_test.py [sezon_sayısı]  (varsayılan 16)
"""
import os
import sys
import random
from collections import defaultdict
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
from engine.strategy import plan_strategies, apply_qualifying_tire_rule, build_strategy_options, apply_choice
from main import load_data

CHASERS = {"T_FER", "T_MCL"}
MIDFIELD = {"T_RBR", "T_AST", "T_ALP", "T_HAS"}
BOTTOM = {"T_WIL", "T_VCB", "T_AUD", "T_CAD"}
PTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}


def pick(options, opt_id, fallback_id):
    by_id = {o["id"]: o for o in options}
    return by_id.get(opt_id) or by_id[fallback_id]


def choose_for_team(team_id, options, rain_risky, hot_day):
    """Senaryodaki takım profiline göre strateji kartı seçer.
    Koşul-bilinçli: agresif 2-stop yalnız SICAK günde (yüksek aşınma) mantıklıdır —
    gerçek F1'de de takımlar pist sıcaklığına göre stop sayısına karar verir."""
    if team_id == "T_MER":
        return pick(options, "safe_1stop", "safe_1stop")
    if team_id in CHASERS:
        if rain_risky:
            return pick(options, "slick_gamble", "aggressive_2stop")
        if hot_day:
            return pick(options, "aggressive_2stop", "aggressive_2stop")
        return pick(options, "offset", "offset")  # normal günde SC piyangosu kovala
    if team_id in MIDFIELD:
        return pick(options, "weather_eager" if rain_risky else "offset", "offset")
    # alt takımlar: piyango — uç seçeneklerden rastgele
    lottery_ids = ["offset"]
    if hot_day:
        lottery_ids.append("aggressive_2stop")
    if rain_risky:
        lottery_ids += ["slick_gamble", "weather_eager"]
    return pick(options, random.choice(lottery_ids), "offset")


def run_scenario(use_choices, n_seasons, drivers, cars, teams, tracks, s):
    director = RaceDirector(s)
    engine = LapRaceEngine(s)
    quali = Qualifying(s)

    team_season_pts = defaultdict(list)
    team_wins = defaultdict(int)
    team_podiums = defaultdict(int)
    pits_total = car_races = 0
    races = 0
    # risk/ödül takibi: takım grubu -> (yağmurlu, kuru) yarışlardaki ort. bitiş + puan
    group_finish = {"chaser": {"rain": [], "dry": []}, "mid": {"rain": [], "dry": []}}
    surprise_podiums_rain = 0   # top-3 dışı takımların yağmurlu yarış podyumları

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
            # Koşullar yarış ÖNCESİ üretilir (oyunda oyuncuya gösterilecek rapor)
            conditions = engine.roll_race_conditions()
            strat = plan_strategies(grid, fc, num_laps, s)
            apply_qualifying_tire_rule(strat, q3, fc)

            if use_choices:
                options = build_strategy_options(fc, num_laps, s)
                rain_risky = fc.get("rain_prob", 0.0) >= 0.25
                hot_day = conditions["wear_day_mult"] > 1.05
                for d_id, drv in drivers.items():
                    option = choose_for_team(drv.team_id, options, rain_risky, hot_day)
                    apply_choice(strat, d_id, option)

            res = engine.simulate_race(grid, profiles, track, form=form, strategies=strat,
                                       forecast=fc, conditions=conditions)
            champ.process_race_result(res["classification"])
            races += 1

            cls = res["classification"]
            rained = res["rained"]
            wkey = "rain" if rained else "dry"
            for c in cls:
                t_id = c["team_id"]
                if c["position"] == 1:
                    team_wins[t_id] += 1
                if c["position"] <= 3:
                    team_podiums[t_id] += 1
                    if rained and t_id not in {"T_MER", "T_FER", "T_MCL"}:
                        surprise_podiums_rain += 1
                pits_total += c["pits"]
                car_races += 1
                if c["status"] == "FIN":
                    if t_id in CHASERS:
                        group_finish["chaser"][wkey].append(c["position"])
                    elif t_id in MIDFIELD:
                        group_finish["mid"][wkey].append(c["position"])

        for t_id in teams:
            team_season_pts[t_id].append(champ.team_standings.get(t_id, 0))

    return {
        "pts": team_season_pts, "wins": team_wins, "podiums": team_podiums,
        "races": races, "pits_per_car": pits_total / max(1, car_races),
        "group_finish": group_finish, "surprise_podiums_rain": surprise_podiums_rain,
        "n_seasons": n_seasons,
    }


def run(n_seasons=16):
    s = GameSettings()
    drivers, cars, teams, tracks = load_data()

    random.seed(2026)
    base = run_scenario(False, n_seasons, drivers, cars, teams, tracks, s)
    random.seed(2026)
    chs = run_scenario(True, n_seasons, drivers, cars, teams, tracks, s)

    N, R = n_seasons, base["races"]
    print(f"\n{'='*86}")
    print(f" STRATEJİ SEÇİMİ SENARYO TESTİ  ({N} sezon x 2 senaryo = {R*2} yarış) ")
    print(f"{'='*86}\n")

    print("1) TAKIM BAZINDA ETKİ  (BASELINE = AI varsayılanı, CHOICES = senaryo seçimleri)")
    print(f"   {'Takım':13s} {'Profil':16s} {'Puan B':>7s} {'Puan C':>7s} {'ΔPuan':>7s} "
          f"{'Gal/szn B':>9s} {'Gal/szn C':>9s} {'σ(puan) B':>9s} {'σ(puan) C':>9s}")
    print(f"   {'-'*83}")
    profile_name = {}
    for t_id in teams:
        if t_id == "T_MER": profile_name[t_id] = "güvenli"
        elif t_id in CHASERS: profile_name[t_id] = "agresif+kumar"
        elif t_id in MIDFIELD: profile_name[t_id] = "fırsatçı"
        else: profile_name[t_id] = "piyango"
    order = sorted(teams, key=lambda t: -mean(base["pts"][t]))
    for t_id in order:
        bp, cp = mean(base["pts"][t_id]), mean(chs["pts"][t_id])
        bs, cs = pstdev(base["pts"][t_id]), pstdev(chs["pts"][t_id])
        bw, cw = base["wins"][t_id] / N, chs["wins"][t_id] / N
        print(f"   {teams[t_id].name[:13]:13s} {profile_name[t_id]:16s} {bp:>7.0f} {cp:>7.0f} {cp-bp:>+7.0f} "
              f"{bw:>9.1f} {cw:>9.1f} {bs:>9.0f} {cs:>9.0f}")

    print(f"\n2) RİSK/ÖDÜL — KUMARLAR NE ZAMAN ÖDÜYOR?  (ort. bitiş pozisyonu, düşük=iyi)")
    for grp, label in [("chaser", "Şamp. kovalayan (FER/MCL, yağmurda slick kumarı)"),
                       ("mid", "Orta saha (yağmurda tedbirli ıslak)")]:
        for scen, data in [("BASELINE", base), ("CHOICES", chs)]:
            gf = data["group_finish"][grp]
            r_avg = mean(gf["rain"]) if gf["rain"] else float("nan")
            d_avg = mean(gf["dry"]) if gf["dry"] else float("nan")
            print(f"   {label[:48]:48s} {scen:9s} yağmurlu: {r_avg:5.2f} | kuru: {d_avg:5.2f}")
    print(f"\n   Top-3 dışı YAĞMUR podyumu: BASELINE {base['surprise_podiums_rain']} | "
          f"CHOICES {chs['surprise_podiums_rain']}  (kaos = fırsatçının sahnesi mi?)")

    print(f"\n3) PIT DAVRANIŞI: ort. pit/araç  BASELINE {base['pits_per_car']:.2f} -> "
          f"CHOICES {chs['pits_per_car']:.2f}  (gerçek F1 ~1.3-2.2; çeşitlilik arttı mı?)")

    print(f"\n4) ADİLLİK ÖZETİ")
    ev_shift = [abs(mean(chs['pts'][t]) - mean(base['pts'][t])) for t in teams]
    var_up = sum(1 for t in teams if pstdev(chs['pts'][t]) > pstdev(base['pts'][t]))
    print(f"   Ort. |EV kayması|: {mean(ev_shift):.0f} puan/sezon (küçük olmalı — seçim kumar, bedava güç değil)")
    print(f"   Varyansı artan takım sayısı: {var_up}/11 (riskli profillerde artmalı)")
    print()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    run(n)
