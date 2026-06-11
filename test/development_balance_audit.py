"""
GELİŞİMLİ SEZON DENGE DENETİMİ
===============================
Diğer tüm testler gelişim KAPALI ölçer; bu denetim GERÇEK OYUN KOŞULUNU ölçer:
GameUniverse akışıyla (5 hak/yarış XP ekonomisi + kesintisiz tesis inşaatı)
tam sezonlar koşulur ve denge metrikleri SEZON FAZLARINA göre raporlanır.

Sorular:
  1. Statlar 100-130 bandına şişerken gerçekçilik metrikleri bozuluyor mu?
     (DNF, SC, pit, sollama, pole->galibiyet — faz faz)
  2. Stat enflasyonu ne hızda? (araç/sürücü overall, 100+ ve 130 tavanı sayısı)
  3. Saha yayılımı nasıl evriliyor? (lider-P2 / lider-P5 temiz pace farkı)
  4. Rekabet: alt takımlar ucuz statlarla kapatıyor mu, üst takım kaçıyor mu?
     (faz bazlı galibiyet payı, şampiyon dağılımı)
  5. Gelişim getiriyor mu? (sezon stat kazanımı vs beklentiye göre sıra değişimi)

Çalıştırma: python test/development_balance_audit.py [sezon_sayısı]  (varsayılan 6)
"""
import os
import sys
import random
from collections import defaultdict
from statistics import mean

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.game_settings import GameSettings
from models.game_universe import GameUniverse

CAR_STATS = ["acceleration", "top_speed", "grip", "reliability", "tire_consumption"]
DRV_STATS = ["pace", "consistency", "attack_defense", "tire_management"]
PHASES = [(1, 8, "Erken (1-8)"), (9, 16, "Orta (9-16)"), (17, 24, "Geç (17-24)")]


def phase_of(race_no):
    for lo, hi, _ in PHASES:
        if lo <= race_no <= hi:
            return (lo, hi)
    return (17, 24)


def field_pace_spread(u):
    """Temiz-hava pace yayılımı (sn/tur, ortalama pist): lider-P2 ve lider-P5."""
    s = u.settings
    tracks = u.tracks

    class AvgTrack:
        req_top_speed = mean(t.req_top_speed for t in tracks)
        req_acceleration = mean(t.req_acceleration for t in tracks)
        req_grip = mean(t.req_grip for t in tracks)
        req_driver_skill = mean(t.req_driver_skill for t in tracks)
        weather_volatility = 0.0

    powers = []
    for d_id, drv in u.drivers.items():
        car = u.get_team_car(drv.team_id)
        p = u.director.build_profile(drv, car, AvgTrack(), 3, "normal", False)
        powers.append(p["base_power"])
    powers.sort(reverse=True)
    base = s.BASE_LAP_TIME

    def lap(bp):
        return base * (1 - (bp - s.PACE_REFERENCE) * s.PACE_SENSITIVITY)

    return lap(powers[1]) - lap(powers[0]), lap(powers[4]) - lap(powers[0])


def overall(u):
    car_avg = mean(getattr(u.get_team_car(t), st) for t in u.teams for st in CAR_STATS)
    drv_avg = mean(getattr(d, st) for d in u.drivers.values() for st in DRV_STATS)
    over100 = sum(1 for t in u.teams for st in CAR_STATS if getattr(u.get_team_car(t), st) > 100) \
            + sum(1 for d in u.drivers.values() for st in DRV_STATS if getattr(d, st) > 100)
    capped = sum(1 for t in u.teams for st in CAR_STATS if getattr(u.get_team_car(t), st) >= 130) \
           + sum(1 for d in u.drivers.values() for st in DRV_STATS if getattr(d, st) >= 130)
    return car_avg, drv_avg, over100, capped


def run(n_seasons=6):
    agg = {ph[:2]: defaultdict(list) for ph in PHASES}
    spreads = {"start": [], "mid": [], "end": []}
    stats_t = {"start": [], "mid": [], "end": []}
    champions = defaultdict(int)
    dev_vs_rank = []   # (takım stat kazanımı, beklenen sıra - gerçek sıra)
    phase_team_wins = {ph[:2]: defaultdict(int) for ph in PHASES}

    for season in range(n_seasons):
        random.seed(8800 + season)
        u = GameUniverse(GameSettings())
        u.setup_season()
        start_tot = {t: sum(getattr(u.get_team_car(t), st) for st in CAR_STATS)
                        + sum(getattr(d, st) for d in u.get_team_drivers(t) for st in DRV_STATS)
                     for t in u.teams}
        spreads["start"].append(field_pace_spread(u))
        stats_t["start"].append(overall(u))

        race_no = 0
        while not u.season_finished:
            u.simulate_next_race()
            if u.season_finished:
                break
            race_no += 1
            ph = phase_of(race_no)
            res, grid = u.latest_raw, u.latest_grid
            cls = res["classification"]
            b = agg[ph]
            b["dnf"].append(sum(1 for c in cls if c["status"] == "DNF"))
            ev_types = {e["type"] for e in res["events"]}
            b["sc"].append(1 if ("SC" in ev_types or "RED_FLAG" in ev_types) else 0)
            b["rain"].append(1 if res["rained"] else 0)
            b["pits"].append(mean(c["pits"] for c in cls))
            b["ot"].append(sum(1 for e in res["events"]
                               if e["type"] == "OVERTAKE" and e.get("pos", 99) <= 10))
            winner = next(c for c in cls if c["position"] == 1)
            b["pole_win"].append(1 if winner["driver_id"] == grid[0] else 0)
            phase_team_wins[ph][winner["team_id"]] += 1

            if race_no == 12:
                spreads["mid"].append(field_pace_spread(u))
                stats_t["mid"].append(overall(u))

        spreads["end"].append(field_pace_spread(u))
        stats_t["end"].append(overall(u))

        ts = u.champ.team_standings
        order = sorted(u.teams, key=lambda t: -ts.get(t, 0))
        champions[u.teams[order[0]].name] += 1
        for rank, t_id in enumerate(order, 1):
            gain = (sum(getattr(u.get_team_car(t_id), st) for st in CAR_STATS)
                    + sum(getattr(d, st) for d in u.get_team_drivers(t_id) for st in DRV_STATS)
                    - start_tot[t_id])
            dev_vs_rank.append((gain, u.exp_team[t_id] - rank, u.teams[t_id].name))

    R = n_seasons
    print(f"\n{'='*92}")
    print(f" GELİŞİMLİ SEZON DENGE DENETİMİ  ({R} sezon, GameUniverse akışı — XP ekonomisi AÇIK)")
    print(f"{'='*92}")

    print("\n1) FAZLARA GÖRE GERÇEKÇİLİK  (statlar şişerken metrikler bozuluyor mu?)")
    print(f"   {'Faz':14s} {'DNF/yarış':>10s} {'SC%':>6s} {'Yağmur%':>8s} {'Pit/araç':>9s} "
          f"{'Sollama10':>10s} {'Pole->Win%':>11s}")
    for lo, hi, name in PHASES:
        b = agg[(lo, hi)]
        print(f"   {name:14s} {mean(b['dnf']):>10.2f} {mean(b['sc'])*100:>5.0f}% "
              f"{mean(b['rain'])*100:>7.0f}% {mean(b['pits']):>9.2f} "
              f"{mean(b['ot']):>10.1f} {mean(b['pole_win'])*100:>10.0f}%")
    print("   Referans: DNF 2-3 | SC %35-50 | pit 1.3-2.2 | sollama 15-40 | pole-win ~%40")

    print("\n2) STAT ENFLASYONU")
    for key, label in [("start", "Sezon başı"), ("mid", "12. yarış"), ("end", "Sezon sonu")]:
        car_a = mean(x[0] for x in stats_t[key]); drv_a = mean(x[1] for x in stats_t[key])
        o100 = mean(x[2] for x in stats_t[key]); cap = mean(x[3] for x in stats_t[key])
        print(f"   {label:11s}: araç ort {car_a:5.1f} | sürücü ort {drv_a:5.1f} | "
              f"100+ stat {o100:4.0f} adet | 130 tavanında {cap:3.0f}")

    print("\n3) SAHA YAYILIMI (temiz pace, ortalama pist)")
    for key, label in [("start", "Sezon başı"), ("mid", "12. yarış"), ("end", "Sezon sonu")]:
        g2 = mean(x[0] for x in spreads[key]); g5 = mean(x[1] for x in spreads[key])
        print(f"   {label:11s}: lider-P2 {g2:6.3f} s/tur | lider-P5 {g5:6.3f} s/tur")

    print("\n4) REKABET — faz bazlı galibiyet payları (en çok kazanan 4 takım)")
    totals = defaultdict(int)
    for ph in phase_team_wins.values():
        for t, w in ph.items():
            totals[t] += w
    top4 = sorted(totals, key=totals.get, reverse=True)[:4]
    name_of = {t_id: tm.name for t_id, tm in u.teams.items()}  # son sezonun evreni
    print(f"   {'Faz':14s}", end="")
    for t in top4:
        print(f" {name_of[t][:12]:>12s}", end="")
    print()
    for lo, hi, name in PHASES:
        races_in_phase = (hi - lo + 1) * R
        print(f"   {name:14s}", end="")
        for t in top4:
            print(f" {phase_team_wins[(lo, hi)][t]/races_in_phase*100:>11.0f}%", end="")
        print()
    print(f"   Şampiyon dağılımı: " + ", ".join(f"{k} x{v}" for k, v in
          sorted(champions.items(), key=lambda x: -x[1])))

    print("\n5) GELİŞİMİN GETİRİSİ (takım stat kazanımı vs beklentiye göre sıra değişimi)")
    dev_vs_rank.sort(key=lambda x: -x[0])
    hi_dev = dev_vs_rank[:len(dev_vs_rank)//3]
    lo_dev = dev_vs_rank[-len(dev_vs_rank)//3:]
    print(f"   En çok gelişen 1/3 (ort +{mean(g for g,_,_ in hi_dev):.0f} stat): "
          f"beklentiye göre ort {mean(d for _,d,_ in hi_dev):+.1f} sıra")
    print(f"   En az gelişen  1/3 (ort +{mean(g for g,_,_ in lo_dev):.0f} stat): "
          f"beklentiye göre ort {mean(d for _,d,_ in lo_dev):+.1f} sıra")
    print()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    run(n)
