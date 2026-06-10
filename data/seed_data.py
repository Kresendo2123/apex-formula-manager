# data/seed_data.py

SEED_TEAMS = [
    {"id": "T_MER", "name": "Mercedes", "lead_driver_id": "D_ANT", "second_driver_id": "D_RUS", "car_id": "C_MER"},
    {"id": "T_FER", "name": "Ferrari", "lead_driver_id": "D_LEC", "second_driver_id": "D_HAM", "car_id": "C_FER"},
    {"id": "T_MCL", "name": "McLaren", "lead_driver_id": "D_NOR", "second_driver_id": "D_PIA", "car_id": "C_MCL"},
    {"id": "T_RBR", "name": "Red Bull", "lead_driver_id": "D_VER", "second_driver_id": "D_HAD", "car_id": "C_RBR"},
    {"id": "T_AST", "name": "Aston Martin", "lead_driver_id": "D_ALO", "second_driver_id": "D_STR", "car_id": "C_AST"},
    {"id": "T_ALP", "name": "Alpine", "lead_driver_id": "D_GAS", "second_driver_id": "D_DOO", "car_id": "C_ALP"},
    {"id": "T_HAS", "name": "Haas", "lead_driver_id": "D_BEA", "second_driver_id": "D_OCO", "car_id": "C_HAS"},
    {"id": "T_WIL", "name": "Williams", "lead_driver_id": "D_SAI", "second_driver_id": "D_ALB", "car_id": "C_WIL"},
    {"id": "T_VCB", "name": "Racing Bulls", "lead_driver_id": "D_LIN", "second_driver_id": "D_LAW", "car_id": "C_VCB"},
    {"id": "T_AUD", "name": "Audi", "lead_driver_id": "D_HUL", "second_driver_id": "D_BOR", "car_id": "C_AUD"},
    {"id": "T_CAD", "name": "Cadillac", "lead_driver_id": "D_HER", "second_driver_id": "D_SAR", "car_id": "C_CAD"}
]

SEED_DRIVERS = [
    {"id": "D_ANT", "team_id": "T_MER", "name": "Antonelli", "pace": 85, "consistency": 70, "attack_defense": 83, "tire_management": 75, "potential": 99},
    {"id": "D_RUS", "team_id": "T_MER", "name": "Russell", "pace": 94, "consistency": 83, "attack_defense": 94, "tire_management": 93, "potential": 92},

    {"id": "D_LEC", "team_id": "T_FER", "name": "Leclerc", "pace": 93, "consistency": 83, "attack_defense": 92, "tire_management": 91, "potential": 95},
    {"id": "D_HAM", "team_id": "T_FER", "name": "Hamilton", "pace": 89, "consistency": 98, "attack_defense": 93, "tire_management": 91, "potential": 82},

    {"id": "D_NOR", "team_id": "T_MCL", "name": "Norris", "pace": 97, "consistency": 83, "attack_defense": 93, "tire_management": 82, "potential": 95},
    {"id": "D_PIA", "team_id": "T_MCL", "name": "Piastri", "pace": 92, "consistency": 77, "attack_defense": 95, "tire_management": 81, "potential": 97},

    {"id": "D_VER", "team_id": "T_RBR", "name": "Verstappen", "pace": 97, "consistency": 88, "attack_defense": 96, "tire_management": 82, "potential": 94},
    {"id": "D_HAD", "team_id": "T_RBR", "name": "Hadjar", "pace": 85, "consistency": 71, "attack_defense": 81, "tire_management": 82, "potential": 86},

    {"id": "D_ALO", "team_id": "T_AST", "name": "Alonso", "pace": 91, "consistency": 99, "attack_defense": 87, "tire_management": 85, "potential": 75},
    {"id": "D_STR", "team_id": "T_AST", "name": "Stroll", "pace": 77, "consistency": 84, "attack_defense": 77, "tire_management": 73, "potential": 78},

    {"id": "D_GAS", "team_id": "T_ALP", "name": "Gasly", "pace": 85, "consistency": 83, "attack_defense": 83, "tire_management": 78, "potential": 86},
    {"id": "D_COL", "team_id": "T_ALP", "name": "Colapinto", "pace": 75, "consistency": 69, "attack_defense": 71, "tire_management": 74, "potential": 87},

    {"id": "D_BEA", "team_id": "T_HAS", "name": "Bearman", "pace": 83, "consistency": 72, "attack_defense": 88, "tire_management": 70, "potential": 93},
    {"id": "D_OCO", "team_id": "T_HAS", "name": "Ocon", "pace": 84, "consistency": 83, "attack_defense": 85, "tire_management": 84, "potential": 84},

    {"id": "D_SAI", "team_id": "T_WIL", "name": "Sainz", "pace": 86, "consistency": 88, "attack_defense": 88, "tire_management": 80, "potential": 87},
    {"id": "D_ALB", "team_id": "T_WIL", "name": "Albon", "pace": 85, "consistency": 84, "attack_defense": 87, "tire_management": 77, "potential": 87},

    {"id": "D_LAW", "team_id": "T_VCB", "name": "Lawson", "pace": 81, "consistency": 73, "attack_defense": 79,"tire_management": 71, "potential": 88},
    {"id": "D_LIN", "team_id": "T_VCB", "name": "Lindblad", "pace": 72, "consistency": 32, "attack_defense": 70, "tire_management": 60, "potential": 96},

    {"id": "D_HUL", "team_id": "T_AUD", "name": "Hulkenberg", "pace": 85, "consistency": 88, "attack_defense": 85, "tire_management": 85, "potential": 80},
    {"id": "D_BOR", "team_id": "T_AUD", "name": "Bortoleto", "pace": 81, "consistency": 69, "attack_defense": 81, "tire_management": 77, "potential": 90},
    
    {"id": "D_PER", "team_id": "T_CAD", "name": "Perez", "pace": 85, "consistency": 92, "attack_defense": 83, "tire_management": 81, "potential": 88},
    {"id": "D_BOT", "team_id": "T_CAD", "name": "Bottas", "pace": 87, "consistency": 89, "attack_defense": 75, "tire_management": 95, "potential": 82}
]

SEED_CARS = [
    {"id": "C_MER", "team_id": "T_MER", "acceleration": 89, "top_speed": 88, "grip": 88, "reliability": 87, "tire_consumption": 86},
    {"id": "C_FER", "team_id": "T_FER", "acceleration": 86, "top_speed": 86, "grip": 85, "reliability": 85, "tire_consumption": 84},
    {"id": "C_MCL", "team_id": "T_MCL", "acceleration": 85, "top_speed": 86, "grip": 85, "reliability": 84, "tire_consumption": 85},
    {"id": "C_RBR", "team_id": "T_RBR", "acceleration": 83, "top_speed": 83, "grip": 84, "reliability": 82, "tire_consumption": 83},
    {"id": "C_AST", "team_id": "T_AST", "acceleration": 80, "top_speed": 80, "grip": 79, "reliability": 81, "tire_consumption": 80},
    {"id": "C_ALP", "team_id": "T_ALP", "acceleration": 80, "top_speed": 81, "grip": 80, "reliability": 83, "tire_consumption": 81},
    {"id": "C_HAS", "team_id": "T_HAS", "acceleration": 79, "top_speed": 79, "grip": 78, "reliability": 81, "tire_consumption": 79},
    {"id": "C_WIL", "team_id": "T_WIL", "acceleration": 78, "top_speed": 82, "grip": 74, "reliability": 74, "tire_consumption": 73},
    {"id": "C_VCB", "team_id": "T_VCB", "acceleration": 75, "top_speed": 75, "grip": 76, "reliability": 78, "tire_consumption": 76},
    {"id": "C_AUD", "team_id": "T_AUD", "acceleration": 73, "top_speed": 73, "grip": 78, "reliability": 77, "tire_consumption": 75},
    {"id": "C_CAD", "team_id": "T_CAD", "acceleration": 72, "top_speed": 72, "grip": 72, "reliability": 75, "tire_consumption": 72}
]

# Pistlerin referans tur süreleri ve pit stop süreleri gerçek dünya verilerine yaklaştırıldı.
# base_lap_time: Normal yarış koşullarındaki ortalama referans tur süresi (saniye).
# pit_loss: Pit stop'un tur süresine eklediği net kayıp (saniye).
SEED_TRACKS = [
    # 1. Bahreyn (Sakhir): ~1m34s ortalama tempo, ~24s pit loss
    {"id": "TRK_01", "name": "Bahrain (Sakhir)", "req_top_speed": 0.30, "req_acceleration": 0.40, "req_grip": 0.30,
     "req_driver_skill": 0.15, "weather_volatility": 0.01, "num_laps": 57, "base_lap_time": 94.0, "pit_loss": 24.0},
     
    # 2. Suudi Arabistan (Jeddah): ~1m31s, ~21s pit loss
    {"id": "TRK_02", "name": "Saudi Arabia (Jeddah)", "req_top_speed": 0.40, "req_acceleration": 0.20, "req_grip": 0.40,
     "req_driver_skill": 0.25, "weather_volatility": 0.01, "num_laps": 50, "base_lap_time": 91.0, "pit_loss": 21.0},

    # 3. Avustralya (Melbourne): ~1m20s, ~20s pit loss
    {"id": "TRK_03", "name": "Australia (Melbourne)", "req_top_speed": 0.35, "req_acceleration": 0.35, "req_grip": 0.30,
     "req_driver_skill": 0.20, "weather_volatility": 0.10, "num_laps": 58, "base_lap_time": 80.0, "pit_loss": 20.0},
     
    # 4. Japonya (Suzuka): ~1m33s, ~23s pit loss
    {"id": "TRK_04", "name": "Japan (Suzuka)", "req_top_speed": 0.25, "req_acceleration": 0.25, "req_grip": 0.50,
     "req_driver_skill": 0.30, "weather_volatility": 0.15, "num_laps": 53, "base_lap_time": 93.0, "pit_loss": 23.0},
     
    # 5. Çin (Shanghai): ~1m37s, ~24s pit loss
    {"id": "TRK_05", "name": "China (Shanghai)", "req_top_speed": 0.40, "req_acceleration": 0.35, "req_grip": 0.25,
     "req_driver_skill": 0.15, "weather_volatility": 0.10, "num_laps": 56, "base_lap_time": 97.0, "pit_loss": 24.0},
     
    # 6. Miami: ~1m31s, ~22s pit loss
    {"id": "TRK_06", "name": "Miami", "req_top_speed": 0.45, "req_acceleration": 0.30, "req_grip": 0.25,
     "req_driver_skill": 0.20, "weather_volatility": 0.10, "num_laps": 57, "base_lap_time": 91.0, "pit_loss": 22.0},
     
    # 7. Emilia Romagna (Imola): ~1m18s, ~28s pit loss (pit yolu çok uzundur)
    {"id": "TRK_07", "name": "Emilia Romagna (Imola)", "req_top_speed": 0.25, "req_acceleration": 0.35,
     "req_grip": 0.40, "req_driver_skill": 0.25, "weather_volatility": 0.15, "num_laps": 63, "base_lap_time": 78.0, "pit_loss": 28.0},

    # 8. Monaco: ~1m14s, ~22s pit loss
    {"id": "TRK_08", "name": "Monaco", "req_top_speed": 0.05, "req_acceleration": 0.35, "req_grip": 0.60,
     "req_driver_skill": 0.40, "weather_volatility": 0.10, "num_laps": 78, "base_lap_time": 74.0, "pit_loss": 22.0},
     
    # 9. Kanada (Montreal): ~1m15s, ~18s pit loss (çok kısa pit)
    {"id": "TRK_09", "name": "Canada (Montreal)", "req_top_speed": 0.35, "req_acceleration": 0.45, "req_grip": 0.20,
     "req_driver_skill": 0.20, "weather_volatility": 0.15, "num_laps": 70, "base_lap_time": 75.0, "pit_loss": 18.0},
     
    # 10. İspanya (Barcelona): ~1m16s, ~22s pit loss
    {"id": "TRK_10", "name": "Spain (Barcelona)", "req_top_speed": 0.25, "req_acceleration": 0.25, "req_grip": 0.50,
     "req_driver_skill": 0.15, "weather_volatility": 0.05, "num_laps": 66, "base_lap_time": 76.0, "pit_loss": 22.0},
     
    # 11. Avusturya (Red Bull Ring): ~1m07s, ~21s pit loss (en kısa tur)
    {"id": "TRK_11", "name": "Austria (Red Bull Ring)", "req_top_speed": 0.40, "req_acceleration": 0.40,
     "req_grip": 0.20, "req_driver_skill": 0.15, "weather_volatility": 0.15, "num_laps": 71, "base_lap_time": 67.0, "pit_loss": 21.0},

    # 12. Britanya (Silverstone): ~1m30s, ~29s pit loss (uzun pit yolu)
    {"id": "TRK_12", "name": "Great Britain (Silverstone)", "req_top_speed": 0.35, "req_acceleration": 0.20,
     "req_grip": 0.45, "req_driver_skill": 0.25, "weather_volatility": 0.20, "num_laps": 52, "base_lap_time": 90.0, "pit_loss": 29.0},
     
    # 13. Macaristan (Hungaroring): ~1m20s, ~20s pit loss
    {"id": "TRK_13", "name": "Hungary (Hungaroring)", "req_top_speed": 0.15, "req_acceleration": 0.35, "req_grip": 0.50,
     "req_driver_skill": 0.25, "weather_volatility": 0.10, "num_laps": 70, "base_lap_time": 80.0, "pit_loss": 20.0},

    # 14. Belçika (Spa): ~1m48s, ~20s pit loss (çok uzun tur)
    # overtaking_difficulty açık verildi: formül (req_grip ağırlıklı) Spa'yı 0.57'ye koyuyordu,
    # oysa Spa gerçekte uzun DRS düzlükleriyle geçişe en açık pistlerden (Kemmel straight).
    {"id": "TRK_14", "name": "Belgium (Spa)", "req_top_speed": 0.45, "req_acceleration": 0.20, "req_grip": 0.35,
     "req_driver_skill": 0.25, "weather_volatility": 0.30, "num_laps": 44, "base_lap_time": 108.0, "pit_loss": 20.0,
     "overtaking_difficulty": 0.45},
     
    # 15. Hollanda (Zandvoort): ~1m13s, ~20s pit loss
    {"id": "TRK_15", "name": "Netherlands (Zandvoort)", "req_top_speed": 0.15, "req_acceleration": 0.30,
     "req_grip": 0.55, "req_driver_skill": 0.25, "weather_volatility": 0.20, "num_laps": 72, "base_lap_time": 73.0, "pit_loss": 20.0},
     
    # 16. İtalya (Monza): ~1m24s, ~24s pit loss
    {"id": "TRK_16", "name": "Italy (Monza)", "req_top_speed": 0.60, "req_acceleration": 0.25, "req_grip": 0.15,
     "req_driver_skill": 0.10, "weather_volatility": 0.10, "num_laps": 53, "base_lap_time": 84.0, "pit_loss": 24.0},

    # 17. Azerbaycan (Baku): ~1m45s, ~21s pit loss
    {"id": "TRK_17", "name": "Azerbaijan (Baku)", "req_top_speed": 0.50, "req_acceleration": 0.25, "req_grip": 0.25,
     "req_driver_skill": 0.30, "weather_volatility": 0.05, "num_laps": 51, "base_lap_time": 105.0, "pit_loss": 21.0},
     
    # 18. Singapur: ~1m36s, ~28s pit loss (uzun pit yolu, yavaş yarış)
    {"id": "TRK_18", "name": "Singapore", "req_top_speed": 0.15, "req_acceleration": 0.40, "req_grip": 0.45,
     "req_driver_skill": 0.35, "weather_volatility": 0.20, "num_laps": 62, "base_lap_time": 96.0, "pit_loss": 28.0},

    # 19. ABD (Austin): ~1m38s, ~20s pit loss
    {"id": "TRK_19", "name": "USA (Austin)", "req_top_speed": 0.30, "req_acceleration": 0.30, "req_grip": 0.40,
     "req_driver_skill": 0.20, "weather_volatility": 0.10, "num_laps": 56, "base_lap_time": 98.0, "pit_loss": 20.0},
     
    # 20. Meksika (Mexico City): ~1m21s, ~22s pit loss
    {"id": "TRK_20", "name": "Mexico (Mexico City)", "req_top_speed": 0.40, "req_acceleration": 0.35, "req_grip": 0.25,
     "req_driver_skill": 0.15, "weather_volatility": 0.10, "num_laps": 71, "base_lap_time": 81.0, "pit_loss": 22.0},
     
    # 21. Brezilya (Interlagos): ~1m12s, ~20s pit loss
    {"id": "TRK_21", "name": "Brazil (Interlagos)", "req_top_speed": 0.35, "req_acceleration": 0.30, "req_grip": 0.35,
     "req_driver_skill": 0.25, "weather_volatility": 0.25, "num_laps": 71, "base_lap_time": 72.0, "pit_loss": 20.0},
     
    # 22. Las Vegas: ~1m35s, ~20s pit loss
    {"id": "TRK_22", "name": "Las Vegas", "req_top_speed": 0.55, "req_acceleration": 0.25, "req_grip": 0.20,
     "req_driver_skill": 0.20, "weather_volatility": 0.05, "num_laps": 50, "base_lap_time": 95.0, "pit_loss": 20.0},

    # 23. Katar (Lusail): ~1m26s, ~25s pit loss
    {"id": "TRK_23", "name": "Qatar (Lusail)", "req_top_speed": 0.30, "req_acceleration": 0.20, "req_grip": 0.50,
     "req_driver_skill": 0.20, "weather_volatility": 0.01, "num_laps": 57, "base_lap_time": 86.0, "pit_loss": 25.0},
     
    # 24. Abu Dabi (Yas Marina): ~1m27s, ~22s pit loss
    {"id": "TRK_24", "name": "Abu Dhabi (Yas Marina)", "req_top_speed": 0.35, "req_acceleration": 0.35,
     "req_grip": 0.30, "req_driver_skill": 0.15, "weather_volatility": 0.01, "num_laps": 58, "base_lap_time": 87.0, "pit_loss": 22.0}
]