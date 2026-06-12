"""
DETERMİNİZM + OLAY ŞEMASI REGRESYON TESTİ (Faz 0)
==================================================
Üç güvence:

1) REPLAY: simulate_race(seed=N) aynı girdilerle BİREBİR aynı sonucu üretir
   (events, classification, lap_positions). Replay = seed + girdiler.
2) AYRIŞMA: farklı seed'ler (pratikte) farklı yarışlar üretir — RNG enjeksiyonu
   gerçekten zar atıyor, sabit kalmıyor.
3) ŞEMA: üretilen TÜM olaylar engine/events.py sözleşmesine uyar
   (zorunlu alanlar tam, şema dışı alan yok, bilinmeyen tip yok).

Çalıştırma: python test/determinism_test.py [yarış_sayısı]   (varsayılan 30)
"""
import os
import sys
import json
import random

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.strategy import plan_strategies
from engine.events import SCHEMA_VERSION, validate_events
from main import load_data


def build_race_inputs(s, drivers, cars, teams, tracks, seed):
    """Bir yarışın TÜM girdilerini deterministik üretir (grid/profil/strateji/tahmin)."""
    rng = random.Random(seed)
    track = rng.choice(tracks)
    director = RaceDirector(s, rng=rng)
    quali = Qualifying(s, rng=rng)
    form = {d: rng.gauss(0, s.RACE_FORM_SIGMA) for d in drivers}
    grid, _ = quali.simulate_qualifying(drivers, cars, teams, track, False, form=form)
    profiles = {d: director.build_profile(dr, cars[teams[dr.team_id].car_id],
                                          track, 3, "normal", False)
                for d, dr in drivers.items()}
    nl = track.num_laps or s.DEFAULT_RACE_LAPS
    engine = LapRaceEngine(s, rng=rng)
    fc = engine.make_forecast(track, nl)
    cond = engine.roll_race_conditions()
    strat = plan_strategies(grid, fc, nl, s, rng=rng, track=track)
    return track, grid, profiles, form, fc, cond, strat


def main():
    n_races = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    s = GameSettings()
    drivers, cars, teams, tracks = load_data()
    fails = 0

    for i in range(n_races):
        input_seed = 1000 + i
        race_seed = 77000 + i
        track, grid, profiles, form, fc, cond, strat = build_race_inputs(
            s, drivers, cars, teams, tracks, input_seed)

        def run():
            engine = LapRaceEngine(s)
            return engine.simulate_race(grid, profiles, track, form=form,
                                        strategies=strat, forecast=fc,
                                        conditions=cond, seed=race_seed)

        r1, r2 = run(), run()

        # 1) Replay: birebir aynı çıktı
        if json.dumps(r1, default=sorted, sort_keys=True) != \
           json.dumps(r2, default=sorted, sort_keys=True):
            print(f"❌ [{i}] Aynı seed farklı sonuç üretti! (pist: {track.name})")
            fails += 1

        if r1["seed"] != race_seed or r1["schema_version"] != SCHEMA_VERSION:
            print(f"❌ [{i}] Sonuç zarfı hatalı: seed={r1['seed']}, "
                  f"schema_version={r1['schema_version']}")
            fails += 1

        # 3) Şema doğrulaması
        errors = validate_events(r1["events"])
        if errors:
            fails += 1
            print(f"❌ [{i}] Şema ihlali ({track.name}):")
            for idx, err in errors[:10]:
                print(f"    event[{idx}]: {err} -> {r1['events'][idx]}")

    # 2) Ayrışma: aynı girdiler, farklı seed -> farklı klasman/olaylar beklenir.
    #    30 farklı seed'in HEPSİNİN aynı sonucu vermesi RNG'nin bağlı olmadığını gösterir.
    track, grid, profiles, form, fc, cond, strat = build_race_inputs(
        s, drivers, cars, teams, tracks, 1)
    engine = LapRaceEngine(s)
    outcomes = set()
    for k in range(30):
        r = engine.simulate_race(grid, profiles, track, form=form, strategies=strat,
                                 forecast=fc, conditions=cond, seed=k)
        outcomes.add(tuple(c["driver_id"] for c in r["classification"]))
    if len(outcomes) < 2:
        print("❌ Farklı seed'ler hep aynı yarışı üretti — RNG enjeksiyonu şüpheli")
        fails += 1

    print(f"\n{'='*60}")
    if fails == 0:
        print(f"✅ {n_races} yarış: replay determinizmi, sonuç zarfı ve olay şeması "
              f"(v{SCHEMA_VERSION}) TEMİZ; {len(outcomes)} farklı seed-sonucu görüldü.")
    else:
        print(f"❌ {fails} hata bulundu.")
        sys.exit(1)


if __name__ == "__main__":
    main()
