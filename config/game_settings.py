class GameSettings:
    """
    Tüm oyun/simülasyon katsayıları. Değerler mantıksal bölümlere ayrılmıştır.
    NOT: Bir önceki dengeleme geçişinde dosya alfabetik düzleştirilip yorumlar
    silinmişti; değerler korunarak yorumlar ve gruplama geri eklendi.
    """

    # ==============================================================================
    # TEMEL LİMİTLER
    # ==============================================================================
    MAX_STAT_VALUE = 100
    MAX_PERKS_PER_DRIVER = 2

    # ==============================================================================
    # YARIŞ HAFTASI (XP) VE TESİS GELİŞTİRME
    # ==============================================================================
    UPGRADES_PER_RACE = 5          # Yarış arası takıma verilen hamle/antrenman hakkı
    BASE_XP_PER_UPGRADE = 25000    # Antrenman başına taban XP (tesis çarpanlarından önce)
    PERK_LEARN_CHANCE = 0.10       # Pilota odaklanınca stat yerine %10 perk kazanma şansı
    FACILITY_UPGRADE_TIME = 6      # Bir tesisin seviye atlaması için gereken yarış sayısı
    XP_BASE_COST = 10              # Eski gelişim eğrisi tabanı (yeni modeller OOP kullanıyor)
    XP_GROWTH_FACTOR = 1.15        # Eski gelişim eğrisi üstel büyüme faktörü

    # ==============================================================================
    # DNF (KAZA/ARIZA) TEMEL KATSAYILARI
    # ==============================================================================
    BASE_DNF_CHANCE = 0.015        # Temel yarış-dışı kalma ihtimali (denge geçişinde 0.03'ten düşürüldü)
    RAIN_DNF_MULTIPLIER = 1.5      # Yağmurda kaza ihtimali çarpanı
    RELIABILITY_RISK_SCALE = 4.0   # Mekanik risk = (100 - reliability) * bu (binde). 2.0'dan artırıldı:
                                   # gerçek F1'de mekanik DNF ~0.7-1.3/yarış iken motor 0.38 üretiyordu.

    # ==============================================================================
    # SIRALAMA (QUALIFYING) VE GRİD
    # ==============================================================================
    LEAD_DRIVER_QUALI_BUFF = 1.01  # 1. pilota küçük sıralama avantajı
    QUALI_NOISE_MULT = 0.5         # Sıralama tur-süresi gürültüsünün LAP_NOISE_BASE'e oranı.
                                   # Düşürmek pole'ü daha "hak edilir" yapar (saha sıkışıksa piyango olur).
    # Grid pozisyonuna göre yarış-içi güç çarpanı (yalnız eski tek-atış Simulator kullanır;
    # tur motoru bunu KULLANMAZ — orada track-position ayrı modellenir).
    GRID_ADVANTAGE = [
        1.010, 1.009, 1.008, 1.007, 1.006,
        1.005, 1.004, 1.003, 1.002, 1.001,
        1.000, 0.999, 0.998, 0.997, 0.996,
        0.995, 0.994, 0.993, 0.992, 0.991,
        0.990, 0.989,
    ]

    # ==============================================================================
    # AERODİNAMİK SEVİYE (DOWNFORCE) AYARI
    # 1 = düşük kanat (düzlük pisti) ... 5 = yüksek kanat (virajlı pist)
    # Her pistin grip/top-speed talebinden türeyen İDEAL kademesi vardır
    # (Monza ~1, Monaco ~5, dengeli pist ~3 — bkz. RaceDirector.ideal_aero).
    # Etki PARABOLİKTİR: ideal kademede en hızlı, uzaklaştıkça (fark²) ceza.
    # Eski lineer top_speed<->grip takası kaldırıldı: lineer modelde optimum
    # matematiksel olarak HER ZAMAN uç kademeye (1/5) düşüyordu, seçim ezbere
    # çözülen bir lookup'a dönüşüyordu. Parabol her piste kendi idealini verir.
    # ==============================================================================
    AERO_IDEAL_SPREAD = 8.0        # Grip payının (req_grip oranı) ideal kademeye esnetilmesi
    AERO_MISMATCH_COEFF = 0.008    # Kademe farkının KARESİ başına araç perf. cezası (oran)
    AERO_MISMATCH_MAX = 0.045      # Toplam ceza tavanı (çok kötü seçim cezalı ama felaket değil)

    # ==============================================================================
    # SÜRÜŞ STRATEJİSİ (STINT MODU) ÇARPANLARI
    # pace / lastik aşınması / kaza riski tradeoff'u
    # NOT (denge testi 2026-06): eski değerlerde (pace ±%10 sadece eff_pace'e,
    # wear ±%25) lastik tasarrufu pace kaybını ezdiği için long_stint üst takımda
    # şampiyonluk çeviren bir meta'ydı, aggressive ise herkes için tuzaktı.
    # Yeni model: pace çarpanı TÜM driver_performance'a uygulanır (gerçek etki),
    # wear takası daraltıldı. Hedef: üç stil de duruma göre oynanabilir, hiçbiri
    # ±40 puan/sezon bandının dışında baskın değil (test/setup_style_choice_test.py).
    # ==============================================================================
    STRATEGY_STINT_MODIFIER = {
        "aggressive": {"pace": 1.08, "tire_wear": 1.12, "crash_risk": 1.30},
        "normal":     {"pace": 1.00, "tire_wear": 1.00, "crash_risk": 1.00},
        "long_stint": {"pace": 0.96, "tire_wear": 0.94, "crash_risk": 0.90},
    }

    # ==============================================================================
    # TUR TABANLI YARIŞ MOTORU — TEMEL
    # ==============================================================================
    DEFAULT_RACE_LAPS = 55         # Pist tur sayısı vermezse varsayılan
    BASE_LAP_TIME = 90.0           # Pist base_lap_time vermezse varsayılan referans tur (sn)
    PACE_REFERENCE = 80.0          # base_power'ın "nötr" referansı (bunun üstü hızlı, altı yavaş)
    PACE_SENSITIVITY = 0.0006      # base_power farkının tur süresine etkisi. DÜŞÜK = saha sıkışık.
    LAP_NOISE_BASE = 0.003         # Tur süresi rastgele dalgalanma tabanı (consistency ile ölçeklenir)
    MIN_FOLLOW_GAP = 0.18          # İki araç arasındaki fiziksel minimum saniye farkı
    BASE_OVERTAKE_CHANCE = 0.28    # Sollama denemesi taban olasılığı (pist/zorlukla ölçeklenir)

    # ==============================================================================
    # GRID / TRACK-POSITION (START) AVANTAJI — TUR MOTORU
    # Önde başlamak iyi kalkış + clean-air avantajı verir. SABİT SANİYE (uzun turlu pistler
    # orantısız avantaj almasın) ve pistin GEÇİŞ ZORLUĞUYLA (ot_difficulty) ölçekli.
    # Denge geçişinde KALICI clean-air bileşeni kaldırıldı; artık yalnız START fazında
    # (lap <= FADE_LAPS) uygulanıyor — geri kalan turlarda lider, peşindeki aracın dirty-air
    # cezası sayesinde önde kalır (bedava süre kazanmaz).
    # ==============================================================================
    GRID_START_ADVANTAGE_SEC = 1.5    # Lider için lap-1 taban avantajı (saniye); tura göre söner
    CLEAN_AIR_ADVANTAGE_SEC = 0.15    # (ŞU AN KULLANILMIYOR — kalıcı clean-air bileşeni kaldırıldı)
    GRID_ADVANTAGE_DIFFICULTY_POW = 1.6  # Zorluk ölçeği üssü: >1 zor/kolay pist farkını keskinleştirir
    GRID_ADVANTAGE_FADE_LAPS = 8      # Start avantajının 0'a indiği tur (kısa start penceresi)
    GRID_ADVANTAGE_SPREAD = 12        # Avantajın hissedildiği pozisyon derinliği (bu sıradan sonra 0)
    GRID_ADVANTAGE_POS_DECAY = 0.75   # Pozisyon başına üstel azalma: lider tam, P2=0.75x, P3=0.56x...

    # ==============================================================================
    # LASTİK BİLEŞİMLERİ VE AŞINMA
    # pace: tur süresine oransal etki (+ hızlı) | wear_rate: tur başına aşınma
    # ideal_wet: en iyi çalıştığı ıslaklık | type: dry/wet
    # ==============================================================================
    # Aşınma eğrisi artık BİLEŞİM BAZLI (gerçek F1/Pirelli deseni): yumuşak bileşim
    # hızlı aşınır VE uçuruma (cliff) erken + sert girer; sert bileşim yavaş aşınır,
    # uçurumu geç ve yumuşaktır. medium = eski global değerler (denge tabanı korunur).
    #   wear_time_coeff: aşınmanın tur süresine lineer etkisi (sn / tam-aşınma)
    #   cliff: uçurumun başladığı aşınma | cliff_coeff: uçurum sertliği (sn katsayısı)
    TYRE_COMPOUNDS = {
        "soft":   {"pace": 0.006,  "wear_rate": 0.055, "ideal_wet": 0.00, "type": "dry",
                   "wear_time_coeff": 3.0, "cliff": 0.72, "cliff_coeff": 20.0},
        "medium": {"pace": 0.000,  "wear_rate": 0.040, "ideal_wet": 0.00, "type": "dry",
                   "wear_time_coeff": 2.5, "cliff": 0.80, "cliff_coeff": 18.0},
        "hard":   {"pace": -0.005, "wear_rate": 0.028, "ideal_wet": 0.00, "type": "dry",
                   "wear_time_coeff": 2.0, "cliff": 0.90, "cliff_coeff": 12.0},
        "inter":  {"pace": -0.045, "wear_rate": 0.045, "ideal_wet": 0.40, "type": "wet",
                   "wear_time_coeff": 2.5, "cliff": 0.80, "cliff_coeff": 16.0},
        "wet":    {"pace": -0.090, "wear_rate": 0.035, "ideal_wet": 0.90, "type": "wet",
                   "wear_time_coeff": 2.2, "cliff": 0.85, "cliff_coeff": 14.0},
    }
    # Global yedek değerler (bileşim kendi eğrisini vermezse kullanılır)
    WEAR_TIME_COEFF = 2.5          # Aşınmanın tur süresine etkisi (lineer bölge)
    WEAR_CLIFF = 0.80             # Bu aşınma üstünde "uçurum" (cliff) başlar
    WEAR_CLIFF_COEFF = 18.0       # Cliff sonrası ek süre kaybı katsayısı (sert düşüş)
    PIT_LANE_LOSS = 22.0          # Pist pit_loss vermezse varsayılan pit kaybı (sn)
    # Pit süresi varyansı: gerçek hayatta lastik değişimi ~1.9-3.0s oynar; nadiren sıkışan
    # bijon/yavaş pit büyük kayıp yaratır. Hem gerçekçilik hissi hem sürpriz/drama üretir.
    PIT_TIME_SIGMA = 0.35         # Normal pit süresi sapması (sn, gauss)
    SLOW_PIT_PROB = 0.07          # "Yavaş pit" (sıkışan bijon vb.) olasılığı
    SLOW_PIT_EXTRA_MIN = 1.5      # Yavaş pit ek kaybı alt sınırı (sn)
    SLOW_PIT_EXTRA_MAX = 5.0      # Yavaş pit ek kaybı üst sınırı (sn)

    # ==============================================================================
    # SOLLAMA DETAYI (DRS / SLIPSTREAM / KİRLİ HAVA / MÜCADELE)
    # ==============================================================================
    # Pace farkı sollamayı SÜPERLİNEER ödüllendirir: bonus = Δ × SCALE × (1 + |Δ| × CURVE).
    # Δ artık TEMİZ tur farkından ölçülür (clean_lap_time: battle/kaza/onarım kayıpları
    # hariç) — eski modelde atak yapanın kendi mücadele kayıpları kendi pace'ini
    # kirletiyordu (negatif geri besleme: hücum etmek hücum gücünü düşürüyordu).
    OVERTAKE_PACE_DELTA_SCALE = 0.08    # Temiz tur farkının sollama şansına lineer ölçeği
    OVERTAKE_PACE_DELTA_CURVE = 1.2     # Süperlineer büyüme: |Δ| sn başına ek çarpan
    OVERTAKE_PACE_BONUS_CAP = 0.30      # Pace bonusu üst sınırı (alt sınır -0.10)
    OVERTAKE_CAP_RELAX = 0.5            # Büyük pace farkı max_prob tavanını da yukarı iter
                                        # ("backmarker, çok daha hızlı aracı sonsuza dek tutamaz")
    OVERTAKE_TYRE_STATE_SCALE = 0.12    # Lastik durumu (bileşim+aşınma) farkının sollama katkısı
    OVERTAKE_TIME_GAIN = 0.08           # (yardımcı katsayı)
    OVERTAKE_DEFENDER_LOSS = 0.12       # (yardımcı katsayı)

    DRS_FROM_LAP = 3              # DRS'in açıldığı tur
    DRS_BOOST = 0.095            # DRS'in sollama olasılığına katkısı (denge geçişinde 0.06'dan artırıldı)
    DRS_WET_CUTOFF = 0.30        # Bu ıslaklık üstünde DRS kapalı
    DRS_ACTIVATION_GAP = 1.0    # DRS yalnızca öndekiyle makas ≤ bu saniye ise aktif (gerçek "1sn kuralı")
    DRS_TIME_GAIN = 0.12        # DRS menzilindeyken tur-süresi kazancı (sn)
    SLIPSTREAM_GAP = 1.5        # Slipstream (tow) bu saniye içinde hissedilir
    SLIPSTREAM_TIME_GAIN = 0.04 # Slipstream tur-süresi kazancı (sn)

    DIRTY_AIR_GAP = 2.0          # Öndeki araca bu saniye içinde kirli hava cezası başlar
    DIRTY_AIR_MAX_LOSS = 0.16    # Maks. kirli hava tempo kaybı (yakınlıkla artar, sn/tur)
    DIRTY_AIR_COOLDOWN_LAPS = 2  # Kirli hava cezası her tur üst üste yazılmaz; cooldown ile hızlı araç kapanabilir

    BATTLE_WINDOW = 1.7          # İki araç bu saniye içindeyse "mücadele" (sollama denemesi + tempo kaybı)
    BATTLE_TEMPO_LOSS_MIN = 0.04 # Mücadele tur kaybı alt sınırı (her tur bu aralıktan rastgele çekilir;
    BATTLE_TEMPO_LOSS_MAX = 0.08 #  ortalama 0.06 = eski sabit değer, denge korunur, varyans eklenir)
    MAX_BATTLE_TEMPO_LOSS = 0.22 # Birikmiş mücadele tempo kaybı tavanı
    BATTLE_TEMPO_DECAY = 0.40    # KALAN oranı: her tur battle_time_loss *= bu değer.
                                 # DÜŞÜK = hızlı toparlanma. 0.55'ten düşürüldü: gerçek F1'de
                                 # mücadele bitince araçlar temposuna hızla döner (~2 turda %85 geri).

    # ==============================================================================
    # HAFTA SONU FORMU
    # ==============================================================================
    RACE_FORM_SIGMA = 0.002       # Pilot başına haftalık form sapması (çok küçük tutulur)

    # ==============================================================================
    # YARIŞ GÜNÜ KOŞULLARI (RACE-DAY VARIANCE) — META KIRICI KATMAN
    # Fizik sabitleri sabit kalır; "günün koşulları" yarıştan yarışa küçük oynar:
    # pist sıcaklığı aşınmayı, rüzgar/pist evrimi geçiş kolaylığını etkiler.
    # Ortalama denge korunur ama optimal strateji her yarış aynı olmaz (anti-meta).
    # Koşullar yarış öncesi CONDITIONS olayı olarak loglanır -> ileride strateji
    # menüsünde oyuncuya gösterilebilir ("bugün pist sıcak, aşınma yüksek").
    # ==============================================================================
    RACE_DAY_OT_SIGMA = 0.04      # Geçiş zorluğunun yarış günü sapması (gauss, clamp 0.05-0.95)
    RACE_DAY_WEAR_VAR = 0.10      # Aşınma şiddeti gün çarpanı: uniform(1-x, 1+x)

    # ==============================================================================
    # DİNAMİK HAVA DURUMU
    # ==============================================================================
    RAIN_EVENT_SCALE = 2.0        # weather_volatility'nin yağış olasılığına ölçeği (4.0'dan düşürüldü)
    WET_MISMATCH_PACE = 0.22      # Lastik-ıslaklık uyumsuzluğunun pace cezası
    SLICK_FLOOD_PEN = 0.35        # Slick lastikle su birikintisinde ek ceza
    WET_WEAR_COEFF = 0.45         # Uyumsuzlukta ek aşınma katsayısı
    WET_CRASH_COEFF = 1.20        # Islaklığın kaza ihtimaline katkısı
    # Lastik geçiş eşikleri — histerezi: "git" ve "dönüş" eşikleri farklı, böylece eşik
    # civarında ıslaklık dalgalanınca araç sürekli lastik değiştirmez (flip-flop önlenir).
    DRY_TYRE_WET_THRESHOLD = 0.22 # dry -> inter geçiş eşiği
    DRY_TYRE_BACK_THRESHOLD = 0.12 # inter -> dry geri dönüş eşiği (daha düşük)
    WET_TYRE_THRESHOLD = 0.70     # inter -> wet geçiş eşiği
    WET_TYRE_BACK_THRESHOLD = 0.55 # wet -> inter geri dönüş eşiği (daha düşük)
    WEATHER_REACTION_LAG = 1      # Takımların hava değişimine pit tepki gecikmesi (tur)

    # ==============================================================================
    # HAVA TAHMİNİ (SİMÜLASYON ÖNCESİ)
    # ==============================================================================
    FORECAST_CONFIDENCE = 0.65    # Tahminin gerçeğe ne kadar yakın çıkacağı (1=kusursuz)

    # ==============================================================================
    # YAPAY ZEKA STRATEJİ KARARLARI
    # ==============================================================================
    RISKY_STRATEGY_PROB = 0.12    # Bir takımın riskli (agresif/uç) strateji seçme olasılığı
    EAGER_WET_BIAS = -0.07        # Erken lastik değiştiren (yağmurda aceleci) eğilim
    GAMBLER_WET_BIAS = 0.09       # Slick'te uzun kalan (kumarbaz) eğilim

    # ==============================================================================
    # OLAYLAR, KAZALAR VE MEKANİK ARIZALAR
    # ==============================================================================
    START_INCIDENT_MULT = 2.0     # 1. turda kaza ihtimali çarpanı (start kaosu)
    RESTART_INCIDENT_MULT = 1.5   # SC/VSC sonrası restart turlarında kaza çarpanı
    RESTART_CHAOS_LAPS = 2        # Restart kaosunun sürdüğü tur sayısı
    BATTLE_COLLISION_BASE = 0.0025 # Yakın mücadelede temas/çarpışma taban olasılığı (0.005'ten düşürüldü)
    WRONG_TYRE_CRASH_STEP = 1.55  # Yanlış lastik kategorisinin kaza çarpanı (kademe başına)
    CRASH_RETIRE_PROB = 0.34      # Kaza olayında DNF (geri çekilme) olasılığı
    CRASH_DAMAGE_PROB = 0.38      # Kaza olayında hasar (pit + pace cezası) olasılığı
    MECH_RETIRE_PROB = 0.55       # Mekanik olayında DNF olasılığı (kalanı topallayarak/parça değişimi)
    REPAIR_TIME = 35.0            # Hasar onarımı pit süre kaybı (sn)
    DAMAGE_PACE_PENALTY = 0.013   # Hasar sonrası kalıcı pace cezası
    MINOR_TIME_LOSS = 6.0         # Spin/çıkış küçük zaman kaybı (sn)
    LIMP_WINDOW = 0.80            # Yarışın bu oranından sonra "topallayarak devam" penceresi
    LATE_LIMP_PROB = 0.55         # Geç mekanik olayında topallayarak devam etme olasılığı
    LIMP_PACE_PENALTY = 0.05      # Topallarken pace cezası
    VSC_FROM_DAMAGE_PROB = 0.15   # Hasardan VSC çıkma olasılığı (0.25'ten düşürüldü, VSC oranı için)
    START_OVERTAKE_BONUS = 0.04   # 1. tur / restart sollama bonusu (0.10'dan düşürüldü)

    # ==============================================================================
    # GÜVENLİK ARACI (SC), SANAL SC (VSC), KIRMIZI BAYRAK
    # ==============================================================================
    SC_FROM_CRASH_PROB = 0.35     # DNF'lik kazadan SC çıkma olasılığı
    VSC_FROM_CRASH_PROB = 0.20    # DNF'lik kazadan VSC çıkma olasılığı (0.30'dan düşürüldü:
                                  # VSC'li yarış oranı %50'ye çıkmıştı, gerçek F1 ~%30-45)
    RED_FLAG_PROB = 0.04          # Kazadan kırmızı bayrak olasılığı
    VSC_FROM_MECH_PROB = 0.15     # Mekanik DNF'ten VSC olasılığı
    SC_WET_BONUS = 0.20           # Islaklığın SC olasılığına katkısı
    SC_LAPS_MIN, SC_LAPS_MAX = 2, 4   # SC süresi (tur) aralığı
    VSC_LAPS_MIN, VSC_LAPS_MAX = 1, 3 # VSC süresi (tur) aralığı
    SC_GAP = 1.4                  # SC arkasında araçların toplanma aralığı (sn)
    SC_SPEED_MULT = 1.45          # SC turunun yavaşlık çarpanı
    VSC_SLOWDOWN = 1.28           # VSC turunun yavaşlık çarpanı
    SC_INLAP_PENALTY = 6.0        # SC çağrıldığı turdaki ek kayıp (sn)

    # --- SC/VSC altında UCUZ PİT penceresi (gerçek F1 strateji temel taşı) ---
    # Saha yavaşken pit kaybı küçülür. Fırsatçı pit yalnız "zaten durması yakın"
    # araçlar için: lastik aşınmış VEYA plandaki stop yaklaşmış. Taze lastikli araç
    # ucuz diye girmez; yeni pitlenen tekrar girmez (anti-saçmalık korumaları).
    SC_PIT_DISCOUNT = 0.50        # SC altında pit kaybı çarpanı
    VSC_PIT_DISCOUNT = 0.65      # VSC altında pit kaybı çarpanı (daha az kazançlı)
    SC_PIT_WEAR_MIN = 0.45       # Fırsatçı pit için minimum lastik aşınması
    SC_PIT_LOOKAHEAD = 8         # Planlı stop bu kadar tur içindeyse öne çekilir
    SC_PIT_MIN_GAP_LAPS = 6      # Son pitten bu kadar tur geçmediyse tekrar girilmez

    # --- Kalkış (launch) varyansı ---
    # Işıklar söndüğünde refleks farkı: iyi/kötü start 1-3 pozisyon oynatır.
    # Consistency düşük pilot startı daha sık batırır; Clutch Start perki kötü
    # kalkışı yumuşatır. Yavaş araç iyi kalksa da pace'i yoksa pozisyonu koruyamaz.
    GRID_SLOT_SPACING = 0.40     # Start anında ardışık grid slotları arası fiziksel mesafe (sn).
                                 # Kalkış deltası bununla yarışır: tipik iyi/kötü start 1-3 sıra
                                 # oynatır; P15'teki araç süper kalkışla bile lider OLAMAZ.
    LAUNCH_SIGMA = 0.35          # Kalkış sapması (sn; consistency ile ölçeklenir).
                                 # 0.5'ten düşürüldü: pole'ün startta liderliği kaybetme oranı
                                 # gerçek F1 (~%30-40) seviyesinde kalsın diye.
    LAUNCH_MAX = 2.0             # Tek kalkışta maksimum kazanç/kayıp (sn)

    # --- Perk: dinamik yarış içi etkiler ---
    RAINMASTER_WET_PACE = 0.0012 # Rainmaster: ıslak zeminde oransal tur bonusu (~0.1s/tur)

    @classmethod
    def calculate_required_xp(cls, current_level: int) -> int:
        return int(cls.XP_BASE_COST * (cls.XP_GROWTH_FACTOR ** current_level))
