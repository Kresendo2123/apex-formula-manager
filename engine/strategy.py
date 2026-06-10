import random
from typing import List, Dict, Any


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
                    settings, rng: random.Random = None) -> Dict[str, Dict[str, Any]]:
    """
    Grid'deki her pilot için strateji üretir.
    - Çoğu pilot konvansiyonel (benzer) plan kullanır.
    - Bir azınlık riskli oynar: 2-stop, ters (offset) ya da YAĞMUR KUMARI
      (tahmine göre ıslak lastiğe erken davranma veya slick'te uzun kalma).
    Reaktif değildir: tüm seçimler yarış öncesi sabitlenir.
    """
    r = rng or random
    rain_prob = forecast.get("rain_prob", 0.0)
    strategies = {}

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

        strategies[d_id] = {
            "plan": _make_dry_plan(kind, num_laps),
            "wet_bias": wet_bias,
            "reaction_lag": reaction_lag,
            "tag": tag,
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

def build_strategy_options(forecast: Dict[str, Any], num_laps: int, settings) -> List[Dict[str, Any]]:
    """Yarış-öncesi strateji kartlarını üretir (UI/test bu listeden seçer)."""
    rain_prob = forecast.get("rain_prob", 0.0)
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
    return options


def apply_choice(strategies: Dict[str, Any], d_id: str, option: Dict[str, Any]) -> None:
    """Seçilen strateji kartını pilotun yarış stratejisine işler (AI varsayılanını ezer)."""
    strategies[d_id] = {
        "plan": [dict(stint) for stint in option["plan"]],
        "wet_bias": option["wet_bias"],
        "reaction_lag": option["reaction_lag"],
        "tag": option["id"],
    }
