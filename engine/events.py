"""
Yarış olay şeması (event schema) — istemci/sunucu sözleşmesi.

simulate_race() çıktısındaki her olay şu zarfı taşır:

    {
        "lap":  int,    # 0 = yarış öncesi (grid/tahmin), 1..N = tur
        "type": str,    # EVENT_FIELDS içindeki tiplerden biri
        "msg":  str,    # insan-okur özet (TR) — UI log'u; istemci PARSE ETMEZ
        ...             # tipe özgü yapılandırılmış alanlar (aşağıda)
    }

Kurallar (Unity/istemci tarafı için):
- Animasyon/sunum YALNIZ yapılandırılmış alanlardan beslenir; "msg" sadece
  metin günlüğüdür ve her an değişebilir.
- Bilinmeyen "type" değeri zarifçe yok sayılır (ileri uyumluluk).
- Şema kırıcı değişiklikte SCHEMA_VERSION artar; alan EKLEMEK kırıcı değildir.

Sürüm geçmişi:
    1 — ilk resmî sürüm (Faz 0).
"""

SCHEMA_VERSION = 1

# type -> {"required": {...}, "optional": {...}}
# Zarf alanları (lap/type/msg) burada tekrarlanmaz.
EVENT_FIELDS = {
    # ---- yarış öncesi (lap 0)
    "FORECAST":   {"required": {"rain_prob", "exp_start", "exp_intensity",
                                "exp_duration", "confidence"}, "optional": set()},
    "CONDITIONS": {"required": {"wear_mult", "ot_delta"}, "optional": set()},
    "START":      {"required": {"driver", "band", "num_laps"}, "optional": set()},
    "PERKS":      {"required": {"holders"}, "optional": set()},   # {driver: [perk,...]}

    # ---- pit duvarı (lap 0 = pencere tahmini, yarış içi = yeniden plan)
    # action: "window" (bilgi grafiği) | "plan" (hedef pit kuruldu) |
    #         "stay" (sona kadar devam) | "pass" (SC/VSC fırsatı pas geçildi)
    "PITWALL": {"required": {"driver", "action"},
                "optional": {"window", "pit_lap", "compound", "gain_est", "reason"}},

    # ---- kalkış / tur içi
    "LAUNCH":   {"required": {"driver", "delta"}, "optional": set()},
    "WEATHER":  {"required": {"band", "prev_band", "wetness", "trend"}, "optional": set()},
    "OVERTAKE": {"required": {"driver", "passed", "pos", "drs"}, "optional": set()},
    "LEAD":     {"required": {"driver"}, "optional": set()},
    "PERK":     {"required": {"driver", "perk"}, "optional": set()},

    # ---- kazalar / arızalar
    "DNF":    {"required": {"driver", "cause"}, "optional": {"context", "detail"}},
    "DAMAGE": {"required": {"driver", "context"}, "optional": set()},
    "SPIN":   {"required": {"driver", "context", "time_loss"}, "optional": set()},
    "LIMP":   {"required": {"driver", "detail"}, "optional": set()},
    "REPAIR": {"required": {"driver", "detail"}, "optional": set()},

    # ---- pit
    # reason: "plan" | "hava" | "SC" | "VSC"
    "PIT":      {"required": {"driver", "compound", "reason"}, "optional": {"gain_est"}},
    "PIT_RULE": {"required": {"driver"}, "optional": set()},
    "SLOW_PIT": {"required": {"driver", "extra"}, "optional": set()},

    # ---- neutralizasyon
    "SC":        {"required": {"driver", "laps"}, "optional": set()},
    "VSC":       {"required": {"driver", "laps"}, "optional": set()},
    "RED_FLAG":  {"required": {"driver"}, "optional": set()},
    "RED_TYRES": {"required": {"changes"}, "optional": set()},   # {driver: compound}
    "RESTART":   {"required": {"kind"}, "optional": set()},      # "SC" | "VSC"
}

_ENVELOPE = {"lap", "type", "msg"}


def validate_event(ev) -> list:
    """Bir olayın şemaya uygunluğunu denetler; hata listesi döner (boş = geçerli).
    Regresyon testleri ve sunucu tarafı assert'leri için."""
    errors = []
    missing_env = _ENVELOPE - set(ev)
    if missing_env:
        errors.append(f"zarf alanı eksik: {sorted(missing_env)}")
        return errors
    spec = EVENT_FIELDS.get(ev["type"])
    if spec is None:
        errors.append(f"bilinmeyen olay tipi: {ev['type']}")
        return errors
    missing = spec["required"] - set(ev)
    if missing:
        errors.append(f"{ev['type']}: zorunlu alan eksik: {sorted(missing)}")
    unknown = set(ev) - _ENVELOPE - spec["required"] - spec["optional"]
    if unknown:
        errors.append(f"{ev['type']}: şemada olmayan alan: {sorted(unknown)}")
    return errors


def validate_events(events) -> list:
    """Olay listesini denetler; (index, hata) çiftleri döner."""
    out = []
    for i, ev in enumerate(events):
        for err in validate_event(ev):
            out.append((i, err))
    return out
