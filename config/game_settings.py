class GameSettings:
    # ==============================================================================
    # TEMEL LİMİTLER
    # Oyun içi geçerli olan ana sınırlandırmalar.
    # ==============================================================================
    MAX_STAT_VALUE = 100
    MAX_PERKS_PER_DRIVER = 2

    # ==============================================================================
    # YARIŞ HAFTASI (XP) VE TESİS GELİŞTİRME AYARLARI
    # ==============================================================================
    UPGRADES_PER_RACE = 5          # Yarış aralarında takımlara verilen hamle / antrenman hakkı sayısı.
    BASE_XP_PER_UPGRADE = 25000    # Her antrenmanda pilota/araca verilecek taban XP (Tesis çarpanlarından önce).
    PERK_LEARN_CHANCE = 0.10       # Pilota odaklanıldığında stat yerine %10 ihtimalle özel yetenek (perk) kazanma şansı.
    FACILITY_UPGRADE_TIME = 6      # Bir tesisin (Rüzgar Tüneli vb.) inşaatının süreceği yarış sayısı.

    # ==============================================================================
    # GELİŞİM EĞRİSİ (ESKİ SİSTEM - YENİ MODELLER OOP KULLANIYOR)
    # ==============================================================================
    XP_BASE_COST = 10
    XP_GROWTH_FACTOR = 1.15

    # ==============================================================================
    # DNF (KAZA VE ARIZA) KATSAYILARI
    # ==============================================================================
    BASE_DNF_CHANCE = 0.03  # Temel yarış dışı kalma ihtimali
    RAIN_DNF_MULTIPLIER = 1.5  # Yağmur başladığında kaza ihtimalini artıran çarpan

    # ==============================================================================
    # SIRALAMA TURU (QUALIFYING) VE GRİD (START) AYARLARI
    # ==============================================================================
    LEAD_DRIVER_QUALI_BUFF = 1.01  
    
    # Grid Pozisyonuna Göre Yarış İçi Güç Çarpanı
    # Eskiden lider %5 avantajlıydı, 20. sıra %4.5 dezavantajlıydı.
    # Uçurumu kapatmak için avantaj oranları çok azaltıldı! Lider artık sadece %1 avantajlı.
    GRID_ADVANTAGE = [
        1.010, 1.009, 1.008, 1.007, 1.006,
        1.005, 1.004, 1.003, 1.002, 1.001,
        1.000, 0.999, 0.998, 0.997, 0.996,
        0.995, 0.994, 0.993, 0.992, 0.991,
        0.990, 0.989
    ]

    # ==============================================================================
    # YERE BASIKLIK (AERODİNAMİK SEVİYE) KATSAYILARI
    # ==============================================================================
    AERO_TOP_SPEED_MODIFIER = {1: 1.10, 2: 1.05, 3: 1.00, 4: 0.95, 5: 0.90}
    AERO_GRIP_MODIFIER = {1: 0.90, 2: 0.95, 3: 1.00, 4: 1.05, 5: 1.10}

    # ==============================================================================
    # SÜRÜŞ STRATEJİSİ KATSAYILARI
    # ==============================================================================
    STRATEGY_STINT_MODIFIER = {
        "aggressive": {"pace": 1.10, "tire_wear": 1.25, "crash_risk": 1.50},
        "normal": {"pace": 1.00, "tire_wear": 1.00, "crash_risk": 1.00},
        "long_stint": {"pace": 0.90, "tire_wear": 0.75, "crash_risk": 0.80}
    }

    # ==============================================================================
    # TUR TABANLI (LAP-BY-LAP) YARIŞ MOTORU
    # ==============================================================================
    DEFAULT_RACE_LAPS = 55
    BASE_LAP_TIME = 90.0
    PACE_REFERENCE = 80.0
    PACE_SENSITIVITY = 0.0006
    LAP_NOISE_BASE = 0.003
    MIN_FOLLOW_GAP = 0.18
    BASE_OVERTAKE_CHANCE = 0.28

    # ==============================================================================
    # GRID / TRACK-POSITION (START) AVANTAJI — TUR MOTORU
    # Önde başlamak gerçek hayatta clean-air + iyi kalkış avantajı verir. Avantaj MEVCUT
    # pozisyona bağlı, SABİT SANİYE (uzun turlu Spa orantısız avantaj almasın) ve pistin
    # GEÇİŞ ZORLUĞUYLA (ot_difficulty) ölçekli. Pole->galibiyet oranını ~%15'ten ~%25'e çeker.
    #
    # İki bileşen:
    #   1) START bileşeni: kalkış + ilk turlar; tura göre söner (GRID_ADVANTAGE_FADE_LAPS).
    #   2) CLEAN-AIR bileşeni: KALICI; öndeki temiz havada olduğu için her tur avantajlı.
    #
    # BİLİNEN SINIR (test ile doğrulandı): Bu mekanizma pole-win ORTALAMASINI yükseltir ama
    # pist DAĞILIMINI gerçek F1'e çeviremez. Zor geçişli pistlerde (Monaco, Macaristan) pole
    # hâlâ DÜŞÜK (~%14-16) kalır çünkü liderlik PİT FAZINDA kayboluyor: pit'te sıkışık sahada
    # trafiğe düşen lider, geçiş zor olduğu için bir daha öne çıkamıyor. START'ı 6sn'e çıkarmak
    # bile Monaco'yu kurtarmıyor. Gerçek çözüm pit/track-position mantığının elden geçirilmesi
    # (lider pit boyunca track position'ı korusun) — ileride yapılacak. Kök sebep #2: saha çok
    # sıkışık olduğu için quali bir piyango (pole gerçekten en hızlı araç olma oranı ~%18).
    # ==============================================================================
    GRID_START_ADVANTAGE_SEC = 3.5   # START bileşeni: lider için lap-1 taban avantajı (saniye)
    CLEAN_AIR_ADVANTAGE_SEC = 0.35   # CLEAN-AIR bileşeni: lider için her tur kalıcı avantaj (saniye)
    GRID_ADVANTAGE_DIFFICULTY_POW = 1.6  # Zorluk ölçeği üssü: >1 ise zor/kolay pist farkını keskinleştirir
    GRID_ADVANTAGE_FADE_LAPS = 22   # START bileşeninin 0'a indiği tur
    GRID_ADVANTAGE_SPREAD = 10      # Avantajın hissedildiği pozisyon derinliği (bu sıradan sonra 0)
    GRID_ADVANTAGE_POS_DECAY = 0.55 # Pozisyon başına üstel azalma: lider tam, P2=0.55x, P3=0.30x...
                                    # (liderin asıl rakipleri P2-P5'e karşı net önde kalması için)

    # ==============================================================================
    # LASTİK BİLEŞİMLERİ VE AŞINMA DİNAMİKLERİ
    # ==============================================================================
    TYRE_COMPOUNDS = {
        "soft":   {"pace": 0.006,  "wear_rate": 0.055, "ideal_wet": 0.00, "type": "dry"},
        "medium": {"pace": 0.000,  "wear_rate": 0.040, "ideal_wet": 0.00, "type": "dry"},
        "hard":   {"pace": -0.005, "wear_rate": 0.028, "ideal_wet": 0.00, "type": "dry"},
        "inter":  {"pace": -0.045, "wear_rate": 0.045, "ideal_wet": 0.40, "type": "wet"},
        "wet":    {"pace": -0.090, "wear_rate": 0.035, "ideal_wet": 0.90, "type": "wet"},
    }
    WEAR_TIME_COEFF = 2.5        
    WEAR_CLIFF = 0.80            
    WEAR_CLIFF_COEFF = 18.0      
    PIT_LANE_LOSS = 22.0         

    # ==============================================================================
    # HAFTA SONU FORMU
    # ==============================================================================
    # HATA BURADAYDI! 0.018 olan şans faktörü tur başına 1.5 saniye gibi saçma farklar
    # yaratarak uçurumlara neden oluyordu. Bu değer inanılmaz derecede küçültüldü!
    RACE_FORM_SIGMA = 0.002

    # ==============================================================================
    # DİNAMİK HAVA DURUMU (YAĞMUR/KURU GEÇİŞLERİ)
    # ==============================================================================
    RAIN_EVENT_SCALE = 4.0         
    WET_MISMATCH_PACE = 0.38       
    SLICK_FLOOD_PEN = 0.60         
    WET_WEAR_COEFF = 0.80          
    WET_CRASH_COEFF = 1.20         
    DRY_TYRE_WET_THRESHOLD = 0.22  
    WET_TYRE_THRESHOLD = 0.62      
    WEATHER_REACTION_LAG = 2       

    # ==============================================================================
    # HAVA TAHMİNİ (SİMÜLASYON ÖNCESİ)
    # ==============================================================================
    FORECAST_CONFIDENCE = 0.65     

    # ==============================================================================
    # TAKIMLARIN / YAPAY ZEKANIN STRATEJİ KARARLARI
    # ==============================================================================
    RISKY_STRATEGY_PROB = 0.22     
    EAGER_WET_BIAS = -0.07         
    GAMBLER_WET_BIAS = 0.09        

    # ==============================================================================
    # OLAYLAR, KAZALAR VE MEKANİK ARIZALAR
    # ==============================================================================
    START_INCIDENT_MULT = 2.0      
    RESTART_INCIDENT_MULT = 1.5    
    RESTART_CHAOS_LAPS = 2         
    BATTLE_COLLISION_BASE = 0.0050 
    WRONG_TYRE_CRASH_STEP = 1.55   
    CRASH_RETIRE_PROB = 0.34       
    CRASH_DAMAGE_PROB = 0.38       
    MECH_RETIRE_PROB = 0.55        
    REPAIR_TIME = 35.0             
    DAMAGE_PACE_PENALTY = 0.013    
    MINOR_TIME_LOSS = 6.0          
    LIMP_WINDOW = 0.80             
    LATE_LIMP_PROB = 0.55          
    LIMP_PACE_PENALTY = 0.05       
    VSC_FROM_DAMAGE_PROB = 0.25    
    START_OVERTAKE_BONUS = 0.10    
    DRS_ACTIVATION_GAP = 1.0
    SLIPSTREAM_GAP = 1.5
    DRS_TIME_GAIN = 0.12
    SLIPSTREAM_TIME_GAIN = 0.04
    DIRTY_AIR_GAP = 1.3
    DIRTY_AIR_MAX_LOSS = 0.20
    BATTLE_WINDOW = 1.05
    BATTLE_TEMPO_LOSS = 0.06
    MAX_BATTLE_TEMPO_LOSS = 0.22
    BATTLE_TEMPO_DECAY = 0.55
    OVERTAKE_TIME_GAIN = 0.08
    OVERTAKE_DEFENDER_LOSS = 0.12

    # ==============================================================================
    # GÜVENLİK ARACI (SC), SANAL SC (VSC) VE KIRMIZI BAYRAK
    # ==============================================================================
    SC_FROM_CRASH_PROB = 0.35      
    VSC_FROM_CRASH_PROB = 0.30     
    RED_FLAG_PROB = 0.04           
    VSC_FROM_MECH_PROB = 0.15      
    SC_WET_BONUS = 0.20            
    SC_LAPS_MIN, SC_LAPS_MAX = 2, 4    
    VSC_LAPS_MIN, VSC_LAPS_MAX = 1, 3  
    SC_GAP = 1.4                   
    SC_SPEED_MULT = 1.45           
    VSC_SLOWDOWN = 1.28            
    SC_INLAP_PENALTY = 6.0         

    # ==============================================================================
    # DRS (DRAG REDUCTION SYSTEM)
    # ==============================================================================
    DRS_FROM_LAP = 3
    DRS_BOOST = 0.06
    DRS_WET_CUTOFF = 0.30

    # ==============================================================================
    # SIRALAMA (QUALIFYING) RASTGELELİĞİ
    # Sıralama turundaki tur süresi dalgalanmasının LAP_NOISE_BASE'e oranı. Saha çok
    # sıkışıksa (araçlar arası fark < gürültü) pole bir piyangoya döner; bu değeri
    # düşürmek en hızlı aracın pole'ü daha sık almasını (pole'ün "hak edilmesini") sağlar.
    # ==============================================================================
    QUALI_NOISE_MULT = 0.5

    @classmethod
    def calculate_required_xp(cls, current_level: int) -> int:
        return int(cls.XP_BASE_COST * (cls.XP_GROWTH_FACTOR ** current_level))
