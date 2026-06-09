import random
from typing import List, Dict, Any


def _make_dry_plan(kind: str, num_laps: int) -> List[Dict[str, Any]]:
    """Kuru lastik planı üretir. Çoğu pilot 'conv' (tek-stop) kullanır."""
    if kind == "two_stop":
        third = max(1, num_laps // 3)
        return [
            {"compound": "soft", "laps": third},
            {"compound": "medium", "laps": third},
            {"compound": "hard", "laps": num_laps - 2 * third},
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

        # Gridin gerisindekiler kaybedecek bir şeyi olmadığından biraz daha sık risk alır
        back_of_grid = idx >= len(grid_ids) * 0.6
        risky = r.random() < (settings.RISKY_STRATEGY_PROB + (0.12 if back_of_grid else 0.0))

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
                    reaction_lag = settings.WEATHER_REACTION_LAG + 2
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
    Q3'e kalan pilotlarin kuru start lastigi kuralini mevcut strateji planina uygular.
    plan_strategies() dict dondurur, eski demolar ise dogrudan stint listesi verebilir.
    """
    forecast = forecast or {}
    if forecast.get("rain_prob", 0.0) > 0.6:
        return

    dry_compounds = {"soft", "medium", "hard"}
    for d_id, tire in q3_tire_choices.items():
        if tire not in dry_compounds:
            continue

        strategy = strategies.get(d_id)
        if isinstance(strategy, dict):
            plan = strategy.get("plan")
        elif isinstance(strategy, list):
            plan = strategy
        else:
            continue

        if plan:
            plan[0]["compound"] = tire
