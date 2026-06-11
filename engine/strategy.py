import random
from typing import List, Dict, Any, Optional


# -----------------------------------------------------------------------------
# PİST-BİLİNÇLİ KURU PLAN ÜRETİMİ
# Gerçek F1'deki gibi her pistin kendi meta'sı olsun diye: bileşim ömürleri o
# pistin lastik şiddetiyle hesaplanır, aday diziler (M-H, S-H, S-M-S, H-M...)
# kabaca simüle edilip tahmini toplam süreye göre sıralanır. Oyuncu menüsünde
# her kart "en hızlıya göre +X sn" tahminiyle gösterilir (yayın grafiği gibi).
# -----------------------------------------------------------------------------

def _track_severity(track) -> float:
    """Pistin lastik şiddeti — race_engine._track_tyre_severity ile aynı formül."""
    explicit = getattr(track, "tyre_severity", None)
    if explicit is not None:
        return explicit
    return 0.7 + track.req_grip * 0.9


def _compound_life(comp_name: str, severity: float, settings) -> int:
    """Bileşimin bu pistte uçuruma (cliff) kadar dayandığı tahmini tur sayısı."""
    comp = settings.TYRE_COMPOUNDS[comp_name]
    cliff = comp.get("cliff", settings.WEAR_CLIFF)
    return max(1, int(cliff / (comp["wear_rate"] * severity)))


def _build_plan_from_seq(seq, num_laps: int, severity: float, settings):
    """Bileşim dizisinden stint planı kurar. Ara stintler kendi ömründe kapanır,
    kalan turlar son stinte düşer. Son stint ömrünün ~%30 fazlasını aşıyorsa bu
    dizi bu pistte gerçekçi değildir -> None (uçurumda sürünmek plan sayılmaz)."""
    lives = [_compound_life(c, severity, settings) for c in seq]
    total = sum(lives)
    plan, used = [], 0
    for i, (c, life) in enumerate(zip(seq, lives)):
        if i == len(seq) - 1:
            laps = num_laps - used
            if laps < 1 or laps > life * 1.30:
                return None
        else:
            laps = max(1, min(int(round(num_laps * life / total)), life))
            if used + laps >= num_laps:  # ara stint yarışı bitiriyor olmasın
                return None
        plan.append({"compound": c, "laps": laps})
        used += laps
    return plan


def _estimate_plan_time(plan, track, settings) -> float:
    """Planın GÖRECELİ tahmini süre maliyeti (sn): bileşim temposu + aşınma +
    pit kayıpları. Mutlak değil — kartlar arası kıyas için kullanılır."""
    severity = _track_severity(track)
    base = getattr(track, "base_lap_time", None) or settings.BASE_LAP_TIME
    pit_loss = getattr(track, "pit_loss", None) or settings.PIT_LANE_LOSS
    total = (len(plan) - 1) * pit_loss
    for stint in plan:
        comp = settings.TYRE_COMPOUNDS[stint["compound"]]
        cliff = comp.get("cliff", settings.WEAR_CLIFF)
        tc = comp.get("wear_time_coeff", settings.WEAR_TIME_COEFF)
        cc = comp.get("cliff_coeff", settings.WEAR_CLIFF_COEFF)
        wear = 0.0
        for _ in range(stint["laps"]):
            wear += comp["wear_rate"] * severity
            total += -comp["pace"] * base + tc * wear
            if wear > cliff:
                total += cc * (wear - cliff)
    return total


# Aday kuru stratejiler: gerçek F1'de görülen dizi çeşitliliği.
# 3-stop adayları yüksek aşınmalı/uzun yarışlar için (örn. motorun Monaco'su).
_DRY_SEQS_1STOP = [("medium", "hard"), ("soft", "hard"), ("hard", "medium"),
                   ("medium", "soft"), ("soft", "medium")]
_DRY_SEQS_2STOP = [("soft", "medium", "hard"), ("soft", "medium", "soft"),
                   ("medium", "hard", "medium"), ("soft", "hard", "soft"),
                   ("medium", "soft", "soft"), ("hard", "hard", "medium"),
                   ("medium", "hard", "hard")]
_DRY_SEQS_3STOP = [("soft", "medium", "soft", "medium"),
                   ("medium", "hard", "medium", "hard"),
                   ("hard", "hard", "medium", "medium"),
                   ("soft", "hard", "hard", "medium")]


def _seq_label(seq) -> str:
    kisa = {"soft": "S", "medium": "M", "hard": "H"}
    return "-".join(kisa[c] for c in seq)


def build_track_dry_cards(track, num_laps: int, settings) -> List[Dict[str, Any]]:
    """Bu pist için en mantıklı kuru strateji kartlarını üretir (tahmini süreli).
    Dönen kartlar: en iyi 1-stop (safe_1stop), en iyi 2-stop (aggressive_2stop),
    hard-başlayan en iyi plan (offset) + varsa farklı bir alternatif (alt_plan)."""
    severity = _track_severity(track)
    cands = []
    for seq in _DRY_SEQS_1STOP + _DRY_SEQS_2STOP + _DRY_SEQS_3STOP:
        plan = _build_plan_from_seq(seq, num_laps, severity, settings)
        if plan:
            cands.append({"seq": seq, "plan": plan,
                          "est": _estimate_plan_time(plan, track, settings)})
    cands.sort(key=lambda c: c["est"])
    best_est = cands[0]["est"]

    def make(c, cid, desc, risk):
        stops = len(c["seq"]) - 1
        delta = c["est"] - best_est
        if delta < 0.5:
            delta_txt = "tahmini EN HIZLI" if c is cands[0] else "≈ en hızlıyla başa baş"
        else:
            delta_txt = f"tahmini +{delta:.0f} sn"
        return {"id": cid,
                "label": f"{_seq_label(c['seq'])} ({stops} stop) — {delta_txt}",
                "desc": desc, "plan": [dict(s) for s in c["plan"]],
                "wet_bias": 0.0, "reaction_lag": 0, "risk": risk,
                "est_delta": round(delta, 1)}

    cards, used_seqs = [], set()

    def pick(filt, cid, desc, risk):
        for c in cands:
            if c["seq"] not in used_seqs and filt(c):
                used_seqs.add(c["seq"])
                cards.append(make(c, cid, desc, risk))
                return

    # En az stoplu en hızlı plan = güvenli kart; en hızlı çok-stoplu = agresif
    min_stops = min(len(c["seq"]) for c in cands) - 1
    pick(lambda c: len(c["seq"]) - 1 == min_stops, "safe_1stop",
         "Az pit = az risk (yavaş pit / trafik). Stint sonlarında tempo düşebilir.",
         "düşük")
    pick(lambda c: len(c["seq"]) - 1 > min_stops, "aggressive_2stop",
         "Taze lastik temposu ve sollama gücü; ekstra pit riski.", "orta")
    pick(lambda c: c["seq"][0] == "hard", "offset",
         "Uzun ilk stint; SC/VSC pencerene denk gelirse büyük kazanç, gelmezse vasat.",
         "orta")
    # Farklı karakterde bir alternatif daha (varsa): en iyi kalan aday
    pick(lambda c: True, "alt_plan",
         "Bu pistte işleyebilecek alternatif pencere — farklı stint ritmi.", "orta")
    cards.sort(key=lambda k: k["est_delta"])
    return cards


def _make_dry_plan(kind: str, num_laps: int) -> List[Dict[str, Any]]:
    """Kuru lastik planı üretir. Çoğu pilot 'conv' (tek-stop) kullanır."""
    if kind == "two_stop":
        # Stint boyları bileşim ömrüne göre: soft kısa tutulur (uçurum 0.72'den önce
        # pite girilsin), hard en uzun stinti taşır. Eski eşit-üçe-bölme soft'u
        # uçurumun çok ötesine taşıyıp agresif planı intihara çeviriyordu.
        first = max(1, round(num_laps * 0.26))
        second = max(1, round(num_laps * 0.36))
        return [
            {"compound": "soft", "laps": first},
            {"compound": "medium", "laps": second},
            {"compound": "hard", "laps": num_laps - first - second},
        ]
    if kind == "offset":
        # Ters strateji: uzun ilk stint (hard), sonra medium -> farklı pencere/track position
        first = max(1, round(num_laps * 0.60))
        return [
            {"compound": "hard", "laps": first},
            {"compound": "medium", "laps": num_laps - first},
        ]
    # conv: standart tek-stop
    half = max(1, round(num_laps * 0.5))
    return [
        {"compound": "medium", "laps": half},
        {"compound": "hard", "laps": num_laps - half},
    ]


def plan_strategies(grid_ids: List[str], forecast: Dict[str, Any], num_laps: int,
                    settings, rng: random.Random = None,
                    track=None) -> Dict[str, Dict[str, Any]]:
    """
    Grid'deki her pilot için strateji üretir.
    - Çoğu pilot konvansiyonel (benzer) plan kullanır.
    - Bir azınlık riskli oynar: 2-stop, ters (offset) ya da YAĞMUR KUMARI
      (tahmine göre ıslak lastiğe erken davranma veya slick'te uzun kalma).
    Reaktif değildir: tüm seçimler yarış öncesi sabitlenir.
    track verilirse planlar piste özel üretilir (bileşim ömrü bazlı).
    """
    r = rng or random
    rain_prob = forecast.get("rain_prob", 0.0)
    strategies = {}

    # Piste özel plan havuzu: conv/two_stop/offset -> o pistin en iyi karşılığı
    track_plans = None
    if track is not None:
        cards = {c["id"]: c["plan"] for c in build_track_dry_cards(track, num_laps, settings)}
        track_plans = {
            "conv": cards.get("safe_1stop"),
            "two_stop": cards.get("aggressive_2stop"),
            "offset": cards.get("offset"),
        }

    for idx, d_id in enumerate(grid_ids):
        # HATA DÜZELTME: d_id zaten string (ID) olmalı. Eğer bir liste geliyorsa (TypeError: unhashable type: 'list') 
        # grid_ids parametresini kontrol etmeliyiz.
        if isinstance(d_id, list):
             d_id = d_id[0]

        # Gridin gerisindekiler kaybedecek bir şeyi olmadığından biraz daha sık risk alır.
        # Bu bonus küçük tutulur; aksi halde arka sıra stratejileri fazla sık overcut/undercut kazandırır.
        back_of_grid = idx >= len(grid_ids) * 0.6
        risky = r.random() < (settings.RISKY_STRATEGY_PROB + (0.04 if back_of_grid else 0.0))

        wet_bias = 0.0
        reaction_lag = settings.WEATHER_REACTION_LAG
        kind = "conv"
        tag = "konvansiyonel"

        if risky:
            choice = r.random()
            if rain_prob > 0.4 and choice < 0.55:
                # Yağmur kumarı: ya erken davran ya da slick'te kal
                if r.random() < 0.5:
                    wet_bias = settings.EAGER_WET_BIAS      # erken inter/wet
                    reaction_lag = 0
                    tag = "erken-ıslak kumarı"
                else:
                    wet_bias = settings.GAMBLER_WET_BIAS    # slick'te uzun kal
                    reaction_lag = settings.WEATHER_REACTION_LAG + 1
                    tag = "slick kumarı"
            elif choice < 0.78:
                kind = "two_stop"
                tag = "agresif 2-stop"
            else:
                kind = "offset"
                tag = "ters (offset)"

        plan = None
        if track_plans is not None:
            plan = track_plans.get(kind)
        if plan is None:
            plan = _make_dry_plan(kind, num_laps)
        # Pit duvarı risk profili: offset (SC piyangosu kovalar) ve yağmur
        # kumarcıları yüksek risk; konvansiyonel planlar orta.
        risk = "yüksek" if (kind == "offset" or "kumar" in tag) else "orta"
        strategies[d_id] = {
            "plan": [dict(s) for s in plan],
            "wet_bias": wet_bias,
            "reaction_lag": reaction_lag,
            "tag": tag,
            "risk": risk,
        }
    return strategies


def apply_qualifying_tire_rule(strategies: Dict[str, Any],
                               q3_tire_choices: Dict[str, str],
                               forecast: Dict[str, Any] = None) -> None:
    """
    Modern F1'de Q3 lastigiyle yarisa baslama kurali yok.
    Bu fonksiyon geriye donuk uyumluluk icin tutulur, fakat stratejiyi degistirmez.
    """
    return


# -----------------------------------------------------------------------------
# YARIŞ ÖNCESİ STRATEJİ MENÜSÜ (oyuncu seçimi — yarış içi etkileşim YOK)
# Oyuncuya 3-5 "strateji kartı" sunulur; seçim yarış öncesi sabitlenir, yarış
# içindeki tepkileri (hava pitleri vb.) seçilen kartın karakteri (wet_bias,
# reaction_lag) otomatik yönetir. Yağmur olasılığı TAHMİN olarak karta yansır
# (gerçek F1'de takımlar radar görür); kumar kartları açıkça "riskli ama ödüllü"
# diye etiketlenir — böylece seçim bilgilendirilmiş, adil bir kumardır.
# -----------------------------------------------------------------------------

def build_strategy_options(forecast: Dict[str, Any], num_laps: int, settings,
                           track=None) -> List[Dict[str, Any]]:
    """Yarış-öncesi strateji kartlarını üretir (UI/test bu listeden seçer).
    track verilirse kartlar PİSTE ÖZEL üretilir: bileşim dizileri ve stint
    pencereleri o pistin lastik şiddeti/pit kaybına göre seçilir ve her kart
    en hızlı plana göre tahmini süre farkı taşır (est_delta)."""
    rain_prob = forecast.get("rain_prob", 0.0)
    exp_start = forecast.get("exp_start", 0)
    if track is not None:
        options = build_track_dry_cards(track, num_laps, settings)
    else:
        # Geriye dönük uyum: pist verilmezse eski sabit şablonlar
        options = [
            {
                "id": "safe_1stop",
                "label": "Güvenli 1-stop (M→H)",
                "desc": "Az pit = az risk (yavaş pit / trafik). Stint sonlarında tempo düşebilir.",
                "plan": _make_dry_plan("conv", num_laps),
                "wet_bias": 0.0, "reaction_lag": 0, "risk": "düşük",
            },
            {
                "id": "aggressive_2stop",
                "label": "Agresif 2-stop (S→M→H)",
                "desc": "Taze lastik temposu ve sollama gücü; ekstra pit riski + soft uçurumu riski.",
                "plan": _make_dry_plan("two_stop", num_laps),
                "wet_bias": 0.0, "reaction_lag": settings.WEATHER_REACTION_LAG, "risk": "orta",
            },
            {
                "id": "offset",
                "label": "Ters strateji (H→M)",
                "desc": "Uzun ilk stint; SC/VSC pencerene denk gelirse büyük kazanç, gelmezse vasat.",
                "plan": _make_dry_plan("offset", num_laps),
                "wet_bias": 0.0, "reaction_lag": settings.WEATHER_REACTION_LAG, "risk": "orta",
            },
        ]
    # Yağmur bekleniyorsa: planlı piti tahmini yağmur turuna yakın düşen kuru
    # kartlar işaretlenir — oyuncu "yağmur için uygun" piti tek bakışta görür.
    if rain_prob >= 0.25 and exp_start:
        for o in options:
            pit_laps, cum = [], 0
            for stint in o["plan"][:-1]:
                cum += stint["laps"]
                pit_laps.append(cum)
            if any(abs(pl - exp_start) <= 6 for pl in pit_laps):
                o["label"] += "  🌧 yağmur penceresiyle uyumlu"
                o["rain_fit"] = True

    if rain_prob >= 0.25:
        options.append({
            "id": "weather_eager",
            "label": f"Tedbirli ıslak plan (yağış ~%{rain_prob * 100:.0f})",
            "desc": "Yağmur gelirse ıslak lastiğe İLK geçen sen olursun; gelmezse erken pit kaybı.",
            "plan": _make_dry_plan("conv", num_laps),
            "wet_bias": settings.EAGER_WET_BIAS, "reaction_lag": 0, "risk": "orta",
        })
        options.append({
            "id": "slick_gamble",
            "label": f"Slick kumarı (yağış ~%{rain_prob * 100:.0f})",
            "desc": "Hafif yağmurda pite girmeyip pozisyon kazanırsın; sağanakta çok kaybedersin.",
            "plan": _make_dry_plan("conv", num_laps),
            "wet_bias": settings.GAMBLER_WET_BIAS,
            "reaction_lag": settings.WEATHER_REACTION_LAG + 1, "risk": "yüksek",
        })
    # YAĞMURA KÖPRÜ: tahmin "orta/geç yarışta yağmur" diyorsa, hard ile başlayıp
    # TEK planlı piti beklenen yağmur turuna konumlandır. Yağmur o civarda gelirse
    # hava-değişim mantığı aynı pitte inter'e çevirir -> tek pitle yarış biter.
    # Erken gelirse pit öne çekilir (yine tek pit); hiç gelmezse plan kuruda
    # H->M tek-stop'a düşer (failsafe) ama uzun hard stint pahalıya patlayabilir.
    # Long_stint sürüş stiliyle doğal sinerji (gerçek F1'in "köprü kurma" oyunu).
    if rain_prob >= 0.30 and 0.30 * num_laps <= exp_start <= 0.75 * num_laps:
        bridge = max(1, int(exp_start))
        options.append({
            "id": "rain_bridge",
            "label": f"Yağmura köprü (H, tek pit ~{bridge}. turda — yağış ~%{rain_prob * 100:.0f})",
            "desc": "Hard ile yağmura kadar uzan; tek pitin yağmur piti olur. Yağmur gelmezse uzun hard stint + vasat son bölüm.",
            "plan": [
                {"compound": "hard", "laps": bridge},
                {"compound": "medium", "laps": num_laps - bridge},
            ],
            "wet_bias": 0.0, "reaction_lag": 0, "risk": "yüksek",
        })
    return options


def apply_choice(strategies: Dict[str, Any], d_id: str, option: Dict[str, Any]) -> None:
    """Seçilen strateji kartını pilotun yarış stratejisine işler (AI varsayılanını ezer)."""
    strategies[d_id] = {
        "plan": [dict(stint) for stint in option["plan"]],
        "wet_bias": option["wet_bias"],
        "reaction_lag": option["reaction_lag"],
        "tag": option["id"],
        # Kartın risk etiketi pit duvarının yarış içi karakterini belirler
        # (SC fırsat eşiği, pencere esnetme, karar zarı) — oyuncu ajansı buradan.
        "risk": option.get("risk", "orta"),
    }
