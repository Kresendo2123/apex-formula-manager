"""
APEX FORMULA MANAGER — OYNANABİLİR KONSOL DEMOSU
=================================================
Tek sezonluk menajer deneyimi:
  1. Açılışta rakip YZ modu seçilir (dinamik / sabit).
  2. Takımlar + sezon öncesi tahmini sıralamaları gösterilir, takım seçilir.
  3. Her yarış hafta sonu:
     - Pist bilgisi + hava tahmini -> AERO ayarı (sıralamayı da etkiler!)
     - Sıralama sonuçları
     - Pilot başına ayrı pit stratejisi kartı + sürüş stili
     - Yarış: pilotlarının olaylı turları + global olaylar (SC/VSC/yağmur/kırmızı)
     - Yarış sonucu + puan durumu
     - 5 geliştirme hakkı (sürücü statı / araç statı / tesis)
  4. Sezon sonu: kendi takım özeti + genel değerlendirme + grid aktiviteleri.

Çalıştırma: python play_demo.py
"""
import os
import sys
import random

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.championship import Championship
from engine.strategy import plan_strategies, build_strategy_options, apply_choice
from main import load_data, calculate_preseason_expectations, print_season_review

PTS = Championship.POINT_SYSTEM

DRIVER_STATS = [("pace", "Hız"), ("consistency", "İstikrar"),
                ("attack_defense", "Atak/Savunma"), ("tire_management", "Lastik Yönetimi")]
CAR_STATS = [("acceleration", "Hızlanma"), ("top_speed", "Son Sürat"), ("grip", "Yol Tutuş"),
             ("reliability", "Güvenilirlik"), ("tire_consumption", "Lastik Verimi")]
FACILITIES = [("wind_tunnel", "Rüzgar Tüneli", "araç Yol Tutuş + Hızlanma geliştirme hızı"),
              ("simulator", "Simülatör", "sürücü geliştirme hızı"),
              ("factory", "Fabrika", "araç Güvenilirlik/Sürat/Lastik geliştirme hızı")]
STYLES = [("normal", "Normal", "dengeli — her duruma uyar"),
          ("aggressive", "Agresif", "tempo + atak avantajı; lastik hızlı biter, kaza riski (kumar)"),
          ("long_stint", "Lastik Koruma", "temiz havada altın değerinde; trafikte yavaşlık cezası")]

# Pit duvarı talimatı: yarış içi dinamik kararların (SC fırsat piti, pencere
# esnetme) risk iştahı. None = kartın kendi risk etiketi kullanılır.
WALL_OPTIONS = ["Karttan (önerilen)", "Güvenli — sadece bariz fırsat",
                "Dengeli — makul fırsatları alır", "Cesur — marjinali de dener, SC/yağmur bekler"]
WALL_RISK_MAP = {WALL_OPTIONS[0]: None, WALL_OPTIONS[1]: "düşük",
                 WALL_OPTIONS[2]: "orta", WALL_OPTIONS[3]: "yüksek"}

# Gelişim ekonomisi artık GENEL SİSTEMDEN gelir (config/game_settings.py +
# models/game_universe.py aynı değerleri kullanır) — demo sadece yansıtır.
_ECON = GameSettings()
DRIVER_XP_PER_PRESS = _ECON.DRIVER_XP_PER_UPGRADE
CAR_XP_PER_PRESS = _ECON.CAR_XP_PER_UPGRADE
FACILITY_PRESS_COST = 0      # tesis geliştirmesi BEDAVA (hak yemez), sadece zaman alır
FACILITY_DURATION = _ECON.FACILITY_UPGRADE_TIME
UPGRADES_PER_RACE = _ECON.UPGRADES_PER_RACE


# ----------------------------------------------------------------- yardımcılar

def ask_int(prompt, lo, hi, default=None):
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            v = int(raw)
            if lo <= v <= hi:
                return v
        except ValueError:
            pass
        print(f"  (Lütfen {lo}-{hi} arası bir sayı gir)")


def header(title, ch="="):
    print("\n" + ch * 70)
    print(f" {title}")
    print(ch * 70)


def pause():
    input("\n[Enter] ile devam...")


def names_in(msg, name_of):
    """Event mesajındaki sürücü ID'lerini isimlere çevirir."""
    for d_id, name in name_of.items():
        msg = msg.replace(d_id, name)
    return msg


# ----------------------------------------------------------------- YZ davranışı

def ai_pick_aero(s, track, dynamic):
    if not dynamic:
        return 3
    ideal = int(round(RaceDirector.ideal_aero(track, s)))
    r = random.random()
    if r < 0.60: off = 0
    elif r < 0.90: off = random.choice([-1, 1])
    else: off = random.choice([-2, 2])
    return max(1, min(5, ideal + off))


def ai_pick_style(dynamic):
    if not dynamic:
        return "normal"
    return random.choices(["normal", "aggressive", "long_stint"], weights=[60, 20, 20])[0]


def ai_pick_card(options, dynamic):
    """Dinamik YZ bazen kart oynar (her zaman en iyisini değil — varyanslı)."""
    if not dynamic or random.random() < 0.45:
        return None  # varsayılan planında kalır
    return random.choice(options)


def ai_spend_upgrades(team, car, d1, d2, dynamic, log_lines):
    """Dinamik YZ yarış arası 5 geliştirme hakkını varyanslı harcar."""
    if not dynamic:
        return
    presses = UPGRADES_PER_RACE
    # Tesis: ŞANSA BAĞLI DEĞİL — boştaysa hemen yeni inşaat başlar (bedava,
    # hak tüketmez; genel sistemle [game_universe] aynı davranış).
    if team.active_facility_upgrade is None:
        avail = [f for f, _, _ in FACILITIES if team.facilities.get(f, 3) < 3]
        if avail:
            f = random.choice(avail)   # hangisi olacağı çeşitlilik için rastgele
            team.start_facility_upgrade(f, FACILITY_DURATION)
            log_lines.append((team.id, f"tesis: {f}"))
    while presses > 0:
        presses -= 1
        if random.random() < 0.6:  # araç — en zayıf stata eğilimli ama varyanslı
            stats = sorted(CAR_STATS, key=lambda x: getattr(car, x[0]))
            stat = (stats[0] if random.random() < 0.5 else random.choice(CAR_STATS))[0]
            mult = team.get_facility_multiplier(
                "wind_tunnel" if stat in ("grip", "acceleration") else "factory")
            car.add_xp_to_stat(stat, int(CAR_XP_PER_PRESS * mult))
        else:  # sürücü — lider pilota eğilimli
            drv = d1 if random.random() < 0.65 else d2
            stat = random.choice(DRIVER_STATS)[0]
            mult = team.get_facility_multiplier("simulator")
            drv.add_xp_to_stat(stat, int(DRIVER_XP_PER_PRESS * mult))


# ----------------------------------------------------------------- oyuncu ekranları

def screen_pick_team(teams, drivers, cars, expected_teams):
    header("TAKIM SEÇİMİ — Sezon Öncesi Tahminler")
    print(f"{'#':>2s}  {'Takım':14s} {'Tahmin':>7s}  Pilotlar")
    rank_of = {t_id: pos for pos, (t_id, _) in enumerate(expected_teams, 1)}
    listed = [t_id for t_id, _ in expected_teams]
    for pos, t_id in enumerate(listed, 1):
        t = teams[t_id]
        d1, d2 = drivers[t.lead_driver_id], drivers[t.second_driver_id]
        print(f"{pos:2d}. {t.name:14s} {'P' + str(rank_of[t_id]):>7s}  {d1.name} & {d2.name}")
    n = ask_int("\nHangi takımı yöneteceksin? (1-11): ", 1, len(listed))
    return listed[n - 1]


def screen_aero(s, track, race_no, total, fc):
    header(f"YARIŞ {race_no}/{total} — {track.name}", "-")
    ideal = RaceDirector.ideal_aero(track, s)
    if ideal <= 2.2: karakter = "DÜZLÜK ağırlıklı (düşük kanat sever)"
    elif ideal >= 3.8: karakter = "VİRAJ ağırlıklı (yüksek kanat sever)"
    else: karakter = "DENGELİ"
    print(f"Tur sayısı: {track.num_laps} | Pist karakteri: {karakter}")
    print(f"Mühendis önerisi: ideal kanat kademesi ~{round(ideal)}")
    print(f"Hava: {fc['label']}")
    print("\nAERO AYARI (sıralamayı VE yarışı etkiler; yanlış uç pahalıya patlar)")
    print("  1=çok düşük kanat ... 5=çok yüksek kanat")
    return ask_int(f"Kanat kademesi seç (1-5) [öneri {round(ideal)}]: ", 1, 5, default=round(ideal))


def screen_quali_result(grid, my_ids, drivers, teams, is_rain):
    header("SIRALAMA SONUÇLARI" + ("  [💧 ıslak zemin]" if is_rain else ""), "-")
    for pos, d_id in enumerate(grid, 1):
        d = drivers[d_id]
        mark = " <== SEN" if d_id in my_ids else ""
        if pos <= 10 or d_id in my_ids:
            print(f"  P{pos:<2d} {d.name:14s} ({teams[d.team_id].name}){mark}")
    my_pos = [grid.index(d) + 1 for d in my_ids]
    print(f"\nPilotların: P{my_pos[0]} ve P{my_pos[1]}")


def screen_strategy(options, my_drivers, drivers):
    """Pilot başına ayrı kart + ayrı stil seçimi. Döner: {d_id: (card, style)}"""
    header("YARIŞ ÖNCESİ STRATEJİ", "-")
    print("Pit stratejisi kartları (bu piste özel):")
    for i, o in enumerate(options, 1):
        stints = " ".join(f"{st['compound'][:1].upper()}{st['laps']}" for st in o["plan"])
        print(f"  {i}. {o['label']}  [risk: {o['risk']}]")
        print(f"     plan: {stints} | {o['desc']}")
    print("\nSürüş stilleri:")
    for i, (sid, name, desc) in enumerate(STYLES, 1):
        print(f"  {i}. {name} — {desc}")
    print("\nPit duvarı talimatı (yarış içi dinamik kararların risk iştahı):")
    for i, o in enumerate(WALL_OPTIONS, 1):
        print(f"  {i}. {o}")
    choices = {}
    for d_id in my_drivers:
        print(f"\n--- {drivers[d_id].name} ---")
        c = ask_int(f"  Pit stratejisi (1-{len(options)}) [1]: ", 1, len(options), default=1)
        st = ask_int("  Sürüş stili (1-3) [1]: ", 1, 3, default=1)
        w = ask_int(f"  Pit duvarı talimatı (1-{len(WALL_OPTIONS)}) [1]: ",
                    1, len(WALL_OPTIONS), default=1)
        choices[d_id] = (options[c - 1], STYLES[st - 1][0],
                         WALL_RISK_MAP[WALL_OPTIONS[w - 1]])
    return choices


GLOBAL_EVENTS = {"WEATHER", "SC", "VSC", "RED_FLAG", "RED_TYRES", "RESTART"}
MY_EVENTS = {"LAUNCH", "OVERTAKE", "PIT", "SLOW_PIT", "DNF", "DAMAGE", "SPIN",
             "LIMP", "REPAIR", "PERK", "PIT_RULE", "PITWALL"}


def build_replay_lines(res, my_ids, name_of, num_laps):
    """Oyuncu odaklı yarış replay satırlarını üretir (konsol + GUI ortak kullanır).
    Döner: [(lap, kind, text)] — kind: 'global' / 'mine' / 'pos'."""
    lines = []
    for e in res["events"]:
        if e["lap"] == 0 and e["type"] != "PITWALL":
            continue   # tur-0 idari loglar hariç; pit penceresi tahmini gösterilir
        is_global = e["type"] in GLOBAL_EVENTS
        is_mine = e["type"] in MY_EVENTS and (
            e.get("driver") in my_ids or e.get("passed") in my_ids)
        if is_global or is_mine:
            if is_global:
                kind, tag = "global", "🌐"
            elif e["type"] in ("PIT", "SLOW_PIT", "PIT_RULE"):
                kind, tag = "pit", "🔧"   # oyuncunun pitleri ayrı renkte gösterilir
            elif e["type"] == "PITWALL":
                kind, tag = "wall", "🧠"  # pit duvarı kararları (pencere/replan/EV)
            else:
                kind, tag = "mine", "▶"
            lines.append((e["lap"], 1, kind,
                          f"T{e['lap']:>2d} {tag} {names_in(e['msg'], name_of)}"))
    # Periyodik pozisyon kontrol noktaları
    lp = res.get("lap_positions") or []
    step = max(1, num_laps // 6)
    for L in range(step, num_laps + 1, step):
        if L < len(lp):
            pos_txt = " | ".join(
                f"{name_of[d]} P{lp[L].index(d) + 1}" if d in lp[L] else f"{name_of[d]} OUT"
                for d in my_ids)
            lines.append((L, 0, "pos", f"T{L:>2d} 📊 {pos_txt}"))
    lines.sort(key=lambda x: (x[0], x[1]))
    return [(lap, kind, txt) for lap, _, kind, txt in lines]


def screen_race_replay(res, my_ids, name_of, num_laps):
    header("YARIŞ — pilotlarının olaylı turları + global olaylar", "-")
    lines = build_replay_lines(res, my_ids, name_of, num_laps)
    if not lines:
        print("  (Sakin bir yarış — kayda değer olay yok)")
    for _, _, txt in lines:
        print("  " + txt)


def pit_report_lines(res, my_ids, my_choices, name_of):
    """Pilot başına 'planlanan vs gerçekleşen' strateji raporu (konsol + GUI ortak).
    Plan = seçilen kartın stint dizisi; Gerçek = motorun stint geçmişi
    (tur aralıkları + her pitin sebebi: plan/hava/SC/VSC/kırmızı)."""
    K = {"soft": "S", "medium": "M", "hard": "H", "inter": "I", "wet": "W"}
    lines = []
    for d_id in my_ids:
        row = next(c for c in res["classification"] if c["driver_id"] == d_id)
        card = my_choices[d_id][0]
        plan_txt = " → ".join(f"{K[st['compound']]}{st['laps']}" for st in card["plan"])
        stints = row.get("stints", [])
        parts = []
        for i, sti in enumerate(stints):
            end = (stints[i + 1]["from"] - 1) if i + 1 < len(stints) else row["laps_completed"]
            seg = f"{K[sti['compound']]}(T{sti['from']}-{end})"
            if sti["reason"] != "start":
                seg += f"[{sti['reason']}]"
            parts.append(seg)
        durum = "" if row["status"] == "FIN" else " — DNF"
        lines.append(f"{name_of[d_id]:<11s} Plan : {plan_txt}")
        lines.append(f"{'':<11s} Gerçek: {' '.join(parts)}  | {row['pits']} pit{durum}")
    return lines


def screen_race_result(res, my_ids, drivers, teams, name_of):
    header("YARIŞ SONUCU", "-")
    my_points = 0
    for row in res["classification"]:
        d_id = row["driver_id"]
        mark = " <== SEN" if d_id in my_ids else ""
        pts = PTS.get(row.get("position"), 0)
        if row["status"] == "FIN":
            ptxt = f"(+{pts} puan)" if pts else ""
            print(f"  P{row['position']:<2d} {drivers[d_id].name:14s} "
                  f"({teams[row['team_id']].name[:12]:12s}) {ptxt}{mark}")
        else:
            detay = row.get("dnf_detail") or row.get("dnf_cause") or "?"
            print(f"  DNF {drivers[d_id].name:14s} "
                  f"({teams[row['team_id']].name[:12]:12s}) [{detay}]{mark}")
        if d_id in my_ids:
            my_points += pts
    print(f"\nBu yarıştan takımına: {my_points} puan")
    return my_points


def screen_standings(champ, teams, my_team, top=5):
    order = sorted(teams, key=lambda t: -champ.team_standings.get(t, 0))
    print("\nMARKALAR PUAN DURUMU:")
    for pos, t_id in enumerate(order, 1):
        if pos <= top or t_id == my_team:
            mark = " <== SEN" if t_id == my_team else ""
            print(f"  {pos:2d}. {teams[t_id].name:14s} {champ.team_standings.get(t_id, 0):4d} puan{mark}")


def stat_line(obj, stats):
    return " | ".join(f"{lbl} {getattr(obj, st):.0f}" for st, lbl in stats)


def screen_upgrades(team, car, d1, d2):
    header(f"GELİŞTİRME — {UPGRADES_PER_RACE} hakkın var", "-")
    presses = UPGRADES_PER_RACE
    while presses > 0:
        print(f"\nKalan hak: {presses}")
        print(f"  1. {d1.name:14s} -> {stat_line(d1, DRIVER_STATS)}")
        print(f"  2. {d2.name:14s} -> {stat_line(d2, DRIVER_STATS)}")
        print(f"  3. Araç           -> {stat_line(car, CAR_STATS)}")
        fac_txt = ", ".join(f"{n} sv{team.facilities[f]}" for f, n, _ in FACILITIES)
        busy = (f" (devam eden: {team.active_facility_upgrade}, "
                f"{team.facility_upgrade_remaining_races} yarış)" if team.active_facility_upgrade else "")
        print(f"  4. Tesis geliştir (BEDAVA — hak yemez, {FACILITY_DURATION} yarış sürer) -> {fac_txt}{busy}")
        print("  0. Kalan hakları geç")
        sec = ask_int("Seçim: ", 0, 4)
        if sec == 0:
            break
        if sec in (1, 2):
            drv = d1 if sec == 1 else d2
            for i, (st, lbl) in enumerate(DRIVER_STATS, 1):
                req = drv.get_required_xp_for_stat(st)
                cur = getattr(drv, f"{st}_xp")
                print(f"    {i}. {lbl:16s} {getattr(drv, st):3.0f}  (xp {cur}/{req})")
            k = ask_int("  Hangi stat? (1-4): ", 1, 4)
            st = DRIVER_STATS[k - 1][0]
            before = getattr(drv, st)
            mult = team.get_facility_multiplier("simulator")
            drv.add_xp_to_stat(st, int(DRIVER_XP_PER_PRESS * mult))
            gained = getattr(drv, st) - before
            print(f"  -> {drv.name} {DRIVER_STATS[k-1][1]}: +{int(DRIVER_XP_PER_PRESS*mult)} xp"
                  + (f"  ⬆ STAT +{gained:.0f}!" if gained else ""))
            presses -= 1
        elif sec == 3:
            for i, (st, lbl) in enumerate(CAR_STATS, 1):
                req = car.get_required_xp_for_stat(st)
                cur = getattr(car, f"{st}_xp")
                print(f"    {i}. {lbl:16s} {getattr(car, st):3.0f}  (xp {cur}/{req})")
            k = ask_int("  Hangi stat? (1-5): ", 1, 5)
            st = CAR_STATS[k - 1][0]
            before = getattr(car, st)
            mult = team.get_facility_multiplier(
                "wind_tunnel" if st in ("grip", "acceleration") else "factory")
            car.add_xp_to_stat(st, int(CAR_XP_PER_PRESS * mult))
            gained = getattr(car, st) - before
            print(f"  -> Araç {CAR_STATS[k-1][1]}: +{int(CAR_XP_PER_PRESS*mult)} xp"
                  + (f"  ⬆ STAT +{gained:.0f}!" if gained else ""))
            presses -= 1
        elif sec == 4:
            if team.active_facility_upgrade:
                print("  Zaten devam eden bir tesis geliştirmesi var!")
                continue
            avail = [(f, n, d) for f, n, d in FACILITIES if team.facilities.get(f, 3) < 3]
            if not avail:
                print("  Tüm tesisler maksimum seviyede!")
                continue
            for i, (f, n, d) in enumerate(avail, 1):
                print(f"    {i}. {n} (sv{team.facilities[f]} -> {team.facilities[f]+1}) — {d}")
            k = ask_int(f"  Hangi tesis? (1-{len(avail)}): ", 1, len(avail))
            team.start_facility_upgrade(avail[k - 1][0], FACILITY_DURATION)
            print(f"  -> {avail[k-1][1]} geliştirmesi başladı ({FACILITY_DURATION} yarış) — hak harcanmadı")


# ----------------------------------------------------------------- sezon sonu

def screen_season_end(my_team, teams, drivers, cars, champ, history,
                      expected_drivers, expected_teams, start_snapshot, dynamic):
    header("SEZON BİTTİ — PİLOTLAR ŞAMPİYONASI")
    order = sorted(champ.driver_standings.items(), key=lambda x: -x[1])
    for pos, (d_id, p) in enumerate(order, 1):
        mark = " <== SEN" if drivers[d_id].team_id == my_team else ""
        print(f"  {pos:2d}. {drivers[d_id].name:15s} {p:4d} puan{mark}")
    screen_standings(champ, teams, my_team, top=11)

    t = teams[my_team]
    header(f"TAKIM SEZON ÖZETİN — {t.name}")
    print(f"{'Yarış':22s} {'Grid':>9s} {'Bitiş':>11s} {'Puan':>5s}  Seçimler")
    for h in history:
        print(f"{h['track'][:21]:22s} {h['grid']:>9s} {h['finish']:>11s} {h['pts']:>5d}  {h['secim']}")
    total = sum(h["pts"] for h in history)
    exp_rank = next(i for i, (tid, _) in enumerate(expected_teams, 1) if tid == my_team)
    act_order = sorted(teams, key=lambda x: -champ.team_standings.get(x, 0))
    act_rank = act_order.index(my_team) + 1
    print(f"\nToplam: {total} puan | Sezon öncesi tahmin: P{exp_rank} -> Gerçekleşen: P{act_rank}"
          + ("  🎉 BEKLENTİYİ AŞTIN!" if act_rank < exp_rank else
             "  (beklentinin altında)" if act_rank > exp_rank else "  (tam beklendiği gibi)"))

    print_season_review(expected_drivers, expected_teams, champ, drivers, teams)

    header("GRİD AKTİVİTESİ — takımlar bu sezon ne yaptı?")
    if not dynamic:
        print("  (Sabit mod: rakip takımlar geliştirme/strateji yapmadı)")
    for t_id, team in teams.items():
        car = cars[team.car_id]
        snap = start_snapshot[t_id]
        car_delta = sum(getattr(car, st) for st, _ in CAR_STATS) - snap["car"]
        drv_delta = sum(
            getattr(drivers[d], st) for d in (team.lead_driver_id, team.second_driver_id)
            for st, _ in DRIVER_STATS) - snap["drv"]
        kisa = {"wind_tunnel": "Tünel", "simulator": "Sim", "factory": "Fabrika"}
        fac = ", ".join(f"{kisa[f]} sv{team.facilities[f]}" for f, n, _ in FACILITIES)
        mark = " <== SEN" if t_id == my_team else ""
        print(f"  {team.name:14s} araç +{car_delta:.0f} stat | sürücüler +{drv_delta:.0f} stat | "
              f"tesisler: {fac}{mark}")


# ----------------------------------------------------------------- ana akış

def run_demo():
    s = GameSettings()
    drivers, cars, teams, tracks = load_data()
    # Yarış takvimi her sezon karıştırılır (hep aynı sırayla gitmesin)
    tracks = list(tracks)
    random.shuffle(tracks)
    director = RaceDirector(s)
    engine = LapRaceEngine(s)
    quali = Qualifying(s)
    champ = Championship()

    header("APEX FORMULA MANAGER — DEMO")
    print("Rakip takımlar nasıl davransın?")
    print("  1. DİNAMİK — strateji kartı oynar, stil seçer, araç/sürücü geliştirir,")
    print("     tesis yatırımı yapar (her zaman en iyi hamleyi değil; varyanslı)")
    print("  2. SABİT   — sezon boyunca hiçbir şey yapmazlar (saf güç karşılaştırması)")
    dynamic = ask_int("Seçim (1-2) [1]: ", 1, 2, default=1) == 1

    expected_drivers, expected_teams = calculate_preseason_expectations(
        drivers, cars, teams, tracks, director)
    my_team = screen_pick_team(teams, drivers, cars, expected_teams)
    t = teams[my_team]
    my_ids = [t.lead_driver_id, t.second_driver_id]
    my_car = cars[t.car_id]
    name_of = {d_id: d.name for d_id, d in drivers.items()}
    print(f"\n{t.name} seçildi! Pilotların: {name_of[my_ids[0]]} & {name_of[my_ids[1]]}")
    print(f"Araç: {stat_line(my_car, CAR_STATS)}")

    start_snapshot = {
        t_id: {"car": sum(getattr(cars[tm.car_id], st) for st, _ in CAR_STATS),
               "drv": sum(getattr(drivers[d], st)
                          for d in (tm.lead_driver_id, tm.second_driver_id)
                          for st, _ in DRIVER_STATS)}
        for t_id, tm in teams.items()}
    history = []

    for race_no, track in enumerate(tracks, 1):
        num_laps = track.num_laps or s.DEFAULT_RACE_LAPS
        fc = engine.make_forecast(track, num_laps)
        conditions = engine.roll_race_conditions()

        # --- AERO + SIRALAMA ---
        my_aero = screen_aero(s, track, race_no, len(tracks), fc)
        aero_lv = {}
        for d_id, dr in drivers.items():
            aero_lv[d_id] = my_aero if dr.team_id == my_team else ai_pick_aero(s, track, dynamic)
        form = {d: random.gauss(0, s.RACE_FORM_SIGMA) for d in drivers}
        is_q_rain = random.random() < track.weather_volatility
        grid, q3 = quali.simulate_qualifying(drivers, cars, teams, track, is_q_rain,
                                             form=form, aero_levels=aero_lv)
        screen_quali_result(grid, my_ids, drivers, teams, is_q_rain)

        # --- STRATEJİ + STİL --- (kartlar piste özel: bileşim ömrü + tahmini süre)
        options = build_strategy_options(fc, num_laps, s, track=track)
        my_choices = screen_strategy(options, my_ids, drivers)
        strat = plan_strategies(grid, fc, num_laps, s, track=track)
        styles = {}
        for d_id, dr in drivers.items():
            if dr.team_id == my_team:
                card, style, wall_risk = my_choices[d_id]
                apply_choice(strat, d_id, card)
                if wall_risk is not None:   # talimat kartın risk etiketini ezer
                    strat[d_id]["risk"] = wall_risk
                styles[d_id] = style
            else:
                card = ai_pick_card(options, dynamic)
                if card is not None:
                    apply_choice(strat, d_id, card)
                styles[d_id] = ai_pick_style(dynamic)

        if conditions["wear_day_mult"] > 1.05:
            print("\n☀️ Pist bugün SICAK — lastik aşınması normalden yüksek olacak!")
        elif conditions["wear_day_mult"] < 0.95:
            print("\n🌥️ Pist bugün SERİN — lastikler normalden uzun dayanacak.")

        profiles = {d: director.build_profile(
            dr, cars[teams[dr.team_id].car_id], track, aero_lv[d], styles[d], False)
            for d, dr in drivers.items()}

        # --- YARIŞ ---
        res = engine.simulate_race(grid, profiles, track, form=form, strategies=strat,
                                   forecast=fc, conditions=conditions)
        screen_race_replay(res, my_ids, name_of, num_laps)
        pts = screen_race_result(res, my_ids, drivers, teams, name_of)
        print("\nPİT RAPORU (plan vs gerçekleşen):")
        for line in pit_report_lines(res, my_ids, my_choices, name_of):
            print("  " + line)
        champ.process_race_result(res["classification"])
        screen_standings(champ, teams, my_team)

        # geçmişe yaz
        fin_txt, grid_txt = [], []
        for d_id in my_ids:
            row = next(c for c in res["classification"] if c["driver_id"] == d_id)
            fin_txt.append(f"P{row['position']}" if row["status"] == "FIN" else "DNF")
            grid_txt.append(f"P{grid.index(d_id) + 1}")
        history.append({
            "track": track.name, "grid": "/".join(grid_txt), "finish": "/".join(fin_txt),
            "pts": pts,
            "secim": f"aero{my_aero}, " + "+".join(
                f"{my_choices[d][0]['id'][:9]}|{my_choices[d][1][:6]}" for d in my_ids)})

        # --- GELİŞTİRME (son yarıştan sonra yok) ---
        if race_no < len(tracks):
            screen_upgrades(t, my_car, drivers[my_ids[0]], drivers[my_ids[1]])
            ai_logs = []
            for t_id, team in teams.items():
                if t_id == my_team:
                    continue
                ai_spend_upgrades(team, cars[team.car_id],
                                  drivers[team.lead_driver_id], drivers[team.second_driver_id],
                                  dynamic, ai_logs)
            # tesis ilerlemeleri (tüm takımlar)
            for t_id, team in teams.items():
                was = team.active_facility_upgrade
                team.process_facility_upgrade()
                if t_id == my_team and was and team.active_facility_upgrade is None:
                    fname = dict((f, n) for f, n, _ in FACILITIES)[was]
                    print(f"\n🏗️ Tesis geliştirmesi TAMAMLANDI: {fname} artık seviye "
                          f"{team.facilities[was]}!")
            pause()

    screen_season_end(my_team, teams, drivers, cars, champ, history,
                      expected_drivers, expected_teams, start_snapshot, dynamic)
    print("\nDemo bitti — oynadığın için sağ ol! 🏁\n")


if __name__ == "__main__":
    run_demo()
