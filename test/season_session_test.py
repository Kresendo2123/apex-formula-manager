"""
SEASONSESSION ÇEKİRDEK TESTİ (Faz 1)
=====================================
1) AKIŞ: 2 insan + 9 YZ takımla kısaltılmış sezon (4 yarış) faz makinesinden
   sorunsuz geçer (aero -> quali -> strategy -> race -> upgrade -> ... -> end).
2) DETERMİNİZM: aynı seed + aynı girdiler = birebir aynı sonuçlar.
3) AUTO-FILL: hiç girdi vermeyen (AFK) oyuncularla da sezon tamamlanır.
4) DOĞRULAMA: geçersiz girdiler SubmitError fırlatır; olaylar şemaya uyar.

Çalıştırma: python test/season_session_test.py
"""
import os
import sys
import json

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.season_session import (SeasonSession, SubmitError,
                                   PHASE_AERO, PHASE_STRATEGY, PHASE_UPGRADE, PHASE_END)
from engine.events import validate_events

HUMANS = ["T_MCL", "T_FER"]


def play_season(seed, submit=True, races=4):
    """Sezonu sonuna kadar oynar; (yarış sonuçları, final klasman) döner."""
    ses = SeasonSession(HUMANS, seed=seed, num_races=races)
    ses.start()
    results = []
    guard = 0
    while ses.phase != PHASE_END:
        guard += 1
        assert guard < 200, "faz makinesi ilerlemiyor (sonsuz döngü)"
        if submit:
            if ses.phase == PHASE_AERO:
                ses.submit_aero("T_MCL", 4)
                ses.submit_aero("T_FER", 2)
            elif ses.phase == PHASE_STRATEGY:
                card = ses.options[1]["id"] if len(ses.options) > 1 else None
                d1, d2 = ses.team_drivers("T_MCL")
                ses.submit_strategy("T_MCL", {
                    d1: {"card_id": card, "style": "aggressive", "wall": "yüksek"},
                    d2: {"card_id": None, "style": "long_stint", "wall": None},
                })
                ses.submit_strategy("T_FER", {})
            elif ses.phase == PHASE_UPGRADE:
                d1, _ = ses.team_drivers("T_MCL")
                ses.submit_upgrades("T_MCL", [
                    {"kind": "driver", "driver_id": d1, "stat": "pace"},
                    {"kind": "car", "stat": "grip"},
                ], facility="simulator")
                ses.submit_upgrades("T_FER", [], None)
        else:
            ses.auto_fill_phase()   # AFK senaryosu
        for name, payload in ses.advance():
            if name == "race_result":
                results.append(payload)
    return results, ses.phase_payload()["final_standings"]


def main():
    fails = 0

    # 1+2) Akış + determinizm
    r1, s1 = play_season(seed=7)
    r2, s2 = play_season(seed=7)
    if json.dumps(r1, default=sorted, sort_keys=True) != \
       json.dumps(r2, default=sorted, sort_keys=True) or s1 != s2:
        print("❌ Aynı seed + aynı girdiler farklı sezon üretti")
        fails += 1
    if len(r1) != 4:
        print(f"❌ 4 yarış beklenirken {len(r1)} sonuç geldi")
        fails += 1

    r3, _ = play_season(seed=8)
    if json.dumps(r1, default=sorted, sort_keys=True) == \
       json.dumps(r3, default=sorted, sort_keys=True):
        print("❌ Farklı seed aynı sezonu üretti")
        fails += 1

    # 3) AFK: hiç girdi yok, auto_fill ile sezon biter
    r4, _ = play_season(seed=7, submit=False)
    if len(r4) != 4:
        print("❌ AFK sezonu tamamlanamadı")
        fails += 1

    # 4) Şema + geçersiz girdi denetimleri
    for payload in r1:
        errs = validate_events(payload["result"]["events"])
        if errs:
            print(f"❌ Yarış {payload['race_no']}: şema ihlali: {errs[:3]}")
            fails += 1

    ses = SeasonSession(HUMANS, seed=1, num_races=2)
    ses.start()
    for fn, args, desc in [
        (ses.submit_aero, ("T_RBR", 3), "insan olmayan takım kabul edildi"),
        (ses.submit_aero, ("T_MCL", 9), "aero=9 kabul edildi"),
        (ses.submit_strategy, ("T_MCL", {}), "aero fazında strateji kabul edildi"),
    ]:
        try:
            fn(*args)
            print(f"❌ {desc}")
            fails += 1
        except SubmitError:
            pass

    print("=" * 60)
    if fails == 0:
        print("✅ SeasonSession: akış, determinizm, AFK auto-fill, doğrulama TEMİZ.")
        print(f"   Örnek: {len(r1)} yarış, şampiyon takım: {s1['teams'][0]}")
    else:
        print(f"❌ {fails} hata.")
        sys.exit(1)


if __name__ == "__main__":
    main()
