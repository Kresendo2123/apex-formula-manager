# Yarış Olay Şeması — İstemci/Sunucu Sözleşmesi (v1)

Bu doküman `LapRaceEngine.simulate_race()` çıktısının resmî sözleşmesidir.
Unity istemcisi (ve ileride sunucu API'si) yalnızca buradaki yapılandırılmış
alanlara yaslanır. Kaynak gerçeği: [engine/events.py](../engine/events.py)
(`SCHEMA_VERSION`, `EVENT_FIELDS`, `validate_event`).

## İstemci kuralları

1. **`msg` alanı asla parse edilmez.** İnsan-okur Türkçe log metnidir, her an
   değişebilir. Animasyon/sunum yalnızca yapılandırılmış alanlardan beslenir.
2. **Bilinmeyen olay tipi yok sayılır.** Sunucu yeni tip eklediğinde eski
   istemci kırılmaz (ileri uyumluluk).
3. **Alan eklemek kırıcı değildir; alan silmek/yeniden adlandırmak kırıcıdır**
   ve `schema_version` artar.

## Determinizm / Replay

- `simulate_race(..., seed=N)` aynı girdilerle (grid, profiles, strategies,
  forecast, conditions) **birebir aynı yarışı** üretir.
- Seed verilmezse motor üretir; her durumda sonuçta `seed` raporlanır.
- Replay saklamak için olay listesini saklamaya gerek yoktur: *seed + girdiler*
  yeterlidir. (`GameUniverse(settings, seed=N)` tüm sezonu deterministik yapar;
  yarış başına türetilen seed `latest_raw["seed"]` içindedir.)

## Sonuç zarfı (`simulate_race` dönüşü)

| Alan | Tip | Açıklama |
|---|---|---|
| `schema_version` | int | Bu doküman sürümü (şu an 1) |
| `seed` | int | Yarışın RNG seedi (replay anahtarı) |
| `classification` | list | Nihai klasman (aşağıda) |
| `dnf_count` | int | Yarış dışı kalan araç sayısı |
| `events` | list | Kronolojik olay akışı (aşağıda) |
| `lap_positions` | list[list[str]] | index 0 = kalkış sonrası, index L = L. tur sonu sıralama (driver_id) |
| `forecast` | dict | Yarış öncesi hava tahmini (girdiyle aynı) |
| `weather_peak` | float | Gerçekleşen en yüksek ıslaklık (0-1) |
| `rained` | bool | Yarışta yağmur gerçekleşti mi |

### `classification` girdisi

`driver_id, team_id, position, status ("FIN"|"DNF"), laps_completed,
total_time (DNF'te null), pits, final_compound, repairs, stints`.
FIN için ek: `loss_breakdown {pit, repair, incident, battle, dirty_air, aero_gain}` (saniye).
DNF için ek: `dnf_cause ("crash"|"mech"), dnf_detail`.

`stints`: `[{compound, from, reason}]` — reason: `"start" | "plan" | "hava" |
"SC" | "VSC" | "kırmızı" | "kırmızı (taze set)"`.

## Olay zarfı

```json
{ "lap": 12, "type": "OVERTAKE", "msg": "P3: ver -> ham geçti (DRS)", ...tip alanları }
```

`lap: 0` = yarış öncesi (tahmin/koşullar/grid bilgisi). Liste sıralı üretildiği
için akış sırası = sunum sırasıdır.

## Olay tipleri

### Yarış öncesi (lap 0)

| Tip | Alanlar | Ne zaman |
|---|---|---|
| `FORECAST` | `rain_prob, exp_start, exp_intensity, exp_duration, confidence` | Her yarış başı |
| `CONDITIONS` | `wear_mult, ot_delta` | Yarış günü pist koşulları |
| `START` | `driver` (pole), `band`, `num_laps` | Yarış başlangıcı |
| `PERKS` | `holders` ({driver: [perk,...]}) | Sahada perk varsa |
| `PITWALL` | `driver, action:"window", window:[lo,hi]` | Tahmini ilk pit penceresi |

### Pit duvarı (yarış içi yeniden planlama)

`PITWALL` — `driver, action, reason?` + action'a göre:

| `action` | Ek alanlar | Anlamı |
|---|---|---|
| `"plan"` | `pit_lap, compound, window` | Hedef pit turu kuruldu |
| `"stay"` | — | Sona kadar pit yok |
| `"pass"` | `gain_est` | SC/VSC ucuz pit fırsatı bilinçli pas geçildi |
| `"window"` | `window` | Yarış öncesi pencere tahmini |

### Tur içi

| Tip | Alanlar | Anlamı |
|---|---|---|
| `LAUNCH` | `driver, delta` | Kalkışta belirgin kazanç (delta<0) / kayıp (delta>0), saniye |
| `WEATHER` | `band, prev_band, wetness, trend ("worsening"\|"improving")` | Hava bandı değişti |
| `OVERTAKE` | `driver` (geçen), `passed`, `pos` (kazanılan pozisyon, 1=lider), `drs` (bool) | Sollama |
| `LEAD` | `driver` | Yeni lider |
| `PERK` | `driver, perk` | Perk devreye girdi (yarışta ilk kez) |

### Kaza / arıza

| Tip | Alanlar | Anlamı |
|---|---|---|
| `DNF` | `driver, cause ("crash"\|"mech"), context?, detail?` | Yarış dışı |
| `DAMAGE` | `driver, context` | Hasar — pite girip onaracak |
| `SPIN` | `driver, context, time_loss` | Küçük hata, zaman kaybı (sn) |
| `LIMP` | `driver, detail` | Mekanik sorunla yavaşlayarak devam |
| `REPAIR` | `driver, detail` | Parça değişimi piti |

`context`: `"tek araç" | "sollama teması"` — `detail`: `"motor" | "şanzıman" |
"hidrolik" | "fren" | "elektrik" | "soğutma"`.

### Pit

| Tip | Alanlar | Anlamı |
|---|---|---|
| `PIT` | `driver, compound, reason ("plan"\|"hava"\|"SC"\|"VSC"), gain_est?` | Pit stop |
| `PIT_RULE` | `driver` | İki bileşim kuralı zorunlu piti |
| `SLOW_PIT` | `driver, extra` | Yavaş pit (+sn) — PIT olayına ek yayınlanır |

### Neutralizasyon

| Tip | Alanlar | Anlamı |
|---|---|---|
| `SC` | `driver` (sebep), `laps` | Güvenlik aracı |
| `VSC` | `driver` (sebep), `laps` | Sanal güvenlik aracı |
| `RED_FLAG` | `driver` (sebep) | Kırmızı bayrak — yarış durdu |
| `RED_TYRES` | `changes` ({driver: compound}) | Kırmızıda bedava lastik |
| `RESTART` | `kind ("SC"\|"VSC")` | Yeşil bayrak |

## Doğrulama

`engine.events.validate_events(result["events"])` boş liste dönmelidir.
Regresyon: [test/determinism_test.py](../test/determinism_test.py) hem şemayı
hem seed tekrarlanabilirliğini denetler.
