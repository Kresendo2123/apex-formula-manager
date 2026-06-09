"""
POLE -> GALİBİYET DÖNÜŞÜM TESTİ
================================
"Bir sezonda 24 yarışın sadece 3'ünde pole'den başlayan kazanıyor (%12.5).
Bu oran çok mu düşük, bir hata mı var?" sorusunu yanıtlar.

Üç katmanlı ölçüm yapar (her pist için N koşu):

1. TEORİK (saf matematik, yarış simülasyonu YOK):
   Pole'ü alan pilot, AYNI ZAMANDA o yarışın temiz-hava pace'i en yüksek aracı mı?
   -> Sıralama (quali) ile yarış pace modelinin ne kadar örtüştüğünü gösterir.
   -> Üst sınırın üst sınırıdır: pole-sitter "hak ederek" ne sıklıkla en hızlı?

2. KAOSSUZ YARIŞ (DNF / SC / VSC / yağmur kapalı):
   Hiçbir şanssızlık olmazsa pole ne sıklıkla kazanır? -> Pace + track position tavanı.

3. TAM SİMÜLASYON (gerçek oyun koşulları):
   Oyuncunun gördüğü gerçek oran + podyum %, DNF %, ortalama bitiş sırası.

Gerçek hayat referansı: F1'de pole -> galibiyet dönüşümü uzun vadede ~%40,
dominant dönemlerde %50-60.

Çalıştırma:
    python test/pole_win_test.py            # N=200 (varsayılan)
    python test/pole_win_test.py 500         # N=500
"""
import os
import sys
import copy
import random

# Windows konsolunda (cp1254) emoji/ok karakterleri patlatmasın diye UTF-8'e zorla
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.strategy import plan_strategies, apply_qualifying_tire_rule
from main import load_data


def build_profiles(director, drivers, cars, teams, track, zero_luck=False):
    """Tüm pilotlar için yarış profillerini üretir.
    zero_luck=True ise kaza/arıza riskleri sıfırlanır (kaossuz senaryo)."""
    profiles = {}
    for d_id, drv in drivers.items():
        car = cars[teams[drv.team_id].car_id]
        p = director.build_profile(drv, car, track, 3, "normal", is_raining=False)
        if zero_luck:
            p["crash_risk"] = 0.0
            p["crash_incident_risk"] = 0.0
            p["mech_risk"] = 0.0
        profiles[d_id] = p
    return profiles


def race_pace_ranking(profiles, form):
    """Temiz-hava (lastik/olay yok) yarış pace sıralamasını döndürür (en hızlı önce).
    Motorun kullandığı formülle aynı: lap_time ~ base_lap_time(base_power) * (1 - form)."""
    timed = [(p["_clean_lap_time"] * (1 - form.get(d_id, 0.0)), d_id)
             for d_id, p in profiles.items()]
    timed.sort()
    return [d_id for _, d_id in timed]


def kaossuz_settings():
    """DNF/SC/VSC/yağmur üretmeyen ayar kopyası."""
    s = GameSettings()
    s.BASE_DNF_CHANCE = 0.0
    s.BATTLE_COLLISION_BASE = 0.0   # sollama teması -> SC kaynağı yok
    s.RAIN_EVENT_SCALE = 0.0        # yağmur olasılığı 0
    return s


def run(n_per_track=200):
    drivers, cars, teams, tracks = load_data()
    real_settings = GameSettings()
    nochaos_settings = kaossuz_settings()

    director = RaceDirector(real_settings)
    full_engine = LapRaceEngine(real_settings)
    nochaos_engine = LapRaceEngine(nochaos_settings)
    full_quali = Qualifying(real_settings)

    header = (f"{'Pist':28s} | {'Teo1':>6s} | {'Teo3':>6s} | {'Kaossuz':>8s} | "
              f"{'Tam':>6s} | {'Podyum':>7s} | {'DNF':>5s} | {'OrtBitiş':>8s}")
    print(f"\n{'='*len(header)}")
    print(f" POLE -> GALİBİYET TESTİ  (pist başına N={n_per_track} koşu) ")
    print(f"{'='*len(header)}")
    print(header)
    print("-" * len(header))

    agg = {"theo": 0, "theo3": 0, "nochaos": 0, "full_win": 0, "podium": 0, "dnf": 0,
           "finish_sum": 0, "finish_cnt": 0, "races": 0}

    for track in tracks:
        num_laps = track.num_laps or real_settings.DEFAULT_RACE_LAPS
        t_theo = t_theo3 = t_nochaos = t_win = t_podium = t_dnf = 0
        t_finish_sum = t_finish_cnt = 0

        for _ in range(n_per_track):
            form = {d_id: random.gauss(0, real_settings.RACE_FORM_SIGMA) for d_id in drivers}

            # --- Sıralama (kuru) -> pole ---
            grid, q3 = full_quali.simulate_qualifying(drivers, cars, teams, track, False, form=form)
            pole = grid[0]

            # --- 1) TEORİK: pole, yarış pace sıralamasında nerede? ---
            profiles = build_profiles(director, drivers, cars, teams, track)
            for d_id, p in profiles.items():
                p["_clean_lap_time"] = full_engine._base_lap_time(p["base_power"], track)
            pace_rank = race_pace_ranking(profiles, form)
            if pace_rank[0] == pole:
                t_theo += 1
            if pole in pace_rank[:3]:
                t_theo3 += 1

            # Strateji (her iki senaryoda ortak; kuru tahmin)
            fc = full_engine.make_forecast(track, num_laps)
            fc["rain_prob"] = 0.0
            strat = plan_strategies(grid, fc, num_laps, real_settings)
            apply_qualifying_tire_rule(strat, q3, fc)

            # --- 2) KAOSSUZ YARIŞ ---
            nc_profiles = build_profiles(director, drivers, cars, teams, track, zero_luck=True)
            nc_res = nochaos_engine.simulate_race(grid, nc_profiles, track, form=form,
                                                  strategies=strat, forecast=fc)
            nc_winner = next(c["driver_id"] for c in nc_res["classification"] if c["position"] == 1)
            if nc_winner == pole:
                t_nochaos += 1

            # --- 3) TAM SİMÜLASYON ---
            res = full_engine.simulate_race(grid, profiles, track, form=form,
                                            strategies=strat, forecast=fc)
            cls = res["classification"]
            pole_row = next(c for c in cls if c["driver_id"] == pole)
            if pole_row["position"] == 1:
                t_win += 1
            if pole_row["position"] <= 3:
                t_podium += 1
            if pole_row["status"] == "DNF":
                t_dnf += 1
            else:
                t_finish_sum += pole_row["position"]
                t_finish_cnt += 1

        n = n_per_track
        avg_fin = (t_finish_sum / t_finish_cnt) if t_finish_cnt else float("nan")
        print(f"{track.name[:28]:28s} | {t_theo/n*100:5.1f}% | {t_theo3/n*100:5.1f}% | "
              f"{t_nochaos/n*100:7.1f}% | {t_win/n*100:5.1f}% | {t_podium/n*100:6.1f}% | "
              f"{t_dnf/n*100:4.1f}% | {avg_fin:8.2f}")

        agg["theo"] += t_theo
        agg["theo3"] += t_theo3
        agg["nochaos"] += t_nochaos
        agg["full_win"] += t_win
        agg["podium"] += t_podium
        agg["dnf"] += t_dnf
        agg["finish_sum"] += t_finish_sum
        agg["finish_cnt"] += t_finish_cnt
        agg["races"] += n

    R = agg["races"]
    print("-" * len(header))
    avg_fin = agg["finish_sum"] / agg["finish_cnt"] if agg["finish_cnt"] else float("nan")
    print(f"{'TOPLAM / ORTALAMA':28s} | {agg['theo']/R*100:5.1f}% | {agg['theo3']/R*100:5.1f}% | "
          f"{agg['nochaos']/R*100:7.1f}% | {agg['full_win']/R*100:5.1f}% | {agg['podium']/R*100:6.1f}% | "
          f"{agg['dnf']/R*100:4.1f}% | {avg_fin:8.2f}")
    print(f"{'='*len(header)}")
    print("\nSutunlar:")
    print("  Teo1     = Pole'u alan, ayni zamanda yaris pace'i EN HIZLI araci mi? (quali-yaris uyumu)")
    print("  Teo3     = Pole'u alan, yaris pace'inde ilk 3 arac icinde mi? (saha sikisikligi)")
    print("  Kaossuz  = DNF/SC/yagmur kapaliyken pole kazanma orani (saf pace + track position tavani)")
    print("  Tam      = Gercek kosullarda pole kazanma orani (oyuncunun gordugu)")
    print("  Podyum   = Pole'un ilk 3 bitirme orani | DNF = pole'un yaris disi kalma orani")
    print("  OrtBitis = Pole'un ortalama bitis sirasi (DNF'ler haric)")
    print(f"\n  Gercek hayat referansi: pole->galibiyet ~%40 (uzun vade), %50-60 (dominant donem)")
    print(f"  Tek sezonda (24 yaris) 3 galibiyet = %12.5 -> {R} kosuluk istatistik")

    # --- SAHA PACE DAGILIMI TESHISI ---
    print(f"\n{'='*60}")
    print(" SAHA PACE DAGILIMI (Bahrain ornegi, temiz-hava lap suresi) ")
    print(f"{'='*60}")
    track = tracks[0]
    profiles = build_profiles(director, drivers, cars, teams, track)
    rows = sorted(((full_engine._base_lap_time(p["base_power"], track), d_id, p["base_power"])
                   for d_id, p in profiles.items()))
    leader_t = rows[0][0]
    print(f"  {'Pilot':12s} {'BasePow':>8s} {'LapTime':>9s} {'Lidere':>8s}")
    for lt, d_id, bp in rows[:8]:
        print(f"  {drivers[d_id].name[:12]:12s} {bp:8.2f} {lt:9.3f} {lt-leader_t:+8.3f}s")
    print(f"  ... (ilk 8 gosteriliyor)")
    print(f"  -> Lider ile 2. arasi: {rows[1][0]-rows[0][0]:.3f}s | "
          f"Lider ile 5. arasi: {rows[4][0]-rows[0][0]:.3f}s")
    print(f"  Quali gurultusu (std): ~{track.base_lap_time * real_settings.LAP_NOISE_BASE * 0.5:.3f}s")
    print(f"  -> Gurultu, en hizli 4-5 arac arasindaki farktan BUYUKSE pole bir piyangoya doner.\n")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    run(n)
