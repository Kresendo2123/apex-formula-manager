class GameSettings:
    AERO_GRIP_MODIFIER = {1: 0.9, 2: 0.95, 3: 1.0, 4: 1.05, 5: 1.1}

    AERO_TOP_SPEED_MODIFIER = {1: 1.1, 2: 1.05, 3: 1.0, 4: 0.95, 5: 0.9}

    BASE_DNF_CHANCE = 0.015

    BASE_LAP_TIME = 90.0

    BASE_OVERTAKE_CHANCE = 0.28

    BASE_XP_PER_UPGRADE = 25000

    BATTLE_COLLISION_BASE = 0.0025

    BATTLE_TEMPO_DECAY = 0.55

    BATTLE_TEMPO_LOSS = 0.06

    BATTLE_WINDOW = 1.7

    CLEAN_AIR_ADVANTAGE_SEC = 0.15

    CRASH_DAMAGE_PROB = 0.38

    CRASH_RETIRE_PROB = 0.34

    DAMAGE_PACE_PENALTY = 0.013

    DEFAULT_RACE_LAPS = 55

    DIRTY_AIR_COOLDOWN_LAPS = 2

    DIRTY_AIR_GAP = 2.0

    DIRTY_AIR_MAX_LOSS = 0.16

    DRS_ACTIVATION_GAP = 1.0

    DRS_BOOST = 0.095

    DRS_FROM_LAP = 3

    DRS_TIME_GAIN = 0.12

    DRS_WET_CUTOFF = 0.3

    DRY_TYRE_WET_THRESHOLD = 0.22

    DRY_TYRE_BACK_THRESHOLD = 0.12

    EAGER_WET_BIAS = -0.07

    FACILITY_UPGRADE_TIME = 6

    FORECAST_CONFIDENCE = 0.65

    GAMBLER_WET_BIAS = 0.09

    GRID_ADVANTAGE = [1.01,
     1.009,
     1.008,
     1.007,
     1.006,
     1.005,
     1.004,
     1.003,
     1.002,
     1.001,
     1.0,
     0.999,
     0.998,
     0.997,
     0.996,
     0.995,
     0.994,
     0.993,
     0.992,
     0.991,
     0.99,
     0.989]

    GRID_ADVANTAGE_DIFFICULTY_POW = 1.6

    GRID_ADVANTAGE_FADE_LAPS = 8

    GRID_ADVANTAGE_POS_DECAY = 0.75

    GRID_ADVANTAGE_SPREAD = 12

    GRID_START_ADVANTAGE_SEC = 1.5

    LAP_NOISE_BASE = 0.003

    LATE_LIMP_PROB = 0.55

    LEAD_DRIVER_QUALI_BUFF = 1.01

    LIMP_PACE_PENALTY = 0.05

    LIMP_WINDOW = 0.8

    MAX_BATTLE_TEMPO_LOSS = 0.22

    MAX_PERKS_PER_DRIVER = 2

    MAX_STAT_VALUE = 100

    MECH_RETIRE_PROB = 0.55

    MINOR_TIME_LOSS = 6.0

    MIN_FOLLOW_GAP = 0.18

    OVERTAKE_DEFENDER_LOSS = 0.12

    OVERTAKE_PACE_DELTA_SCALE = 0.045

    OVERTAKE_TYRE_STATE_SCALE = 0.12

    OVERTAKE_TIME_GAIN = 0.08

    PACE_REFERENCE = 80.0

    PACE_SENSITIVITY = 0.0006

    PERK_LEARN_CHANCE = 0.1

    PIT_LANE_LOSS = 22.0

    QUALI_NOISE_MULT = 0.5

    RACE_FORM_SIGMA = 0.002

    RAIN_DNF_MULTIPLIER = 1.5

    RAIN_EVENT_SCALE = 2.0

    RED_FLAG_PROB = 0.04

    REPAIR_TIME = 35.0

    RESTART_CHAOS_LAPS = 2

    RESTART_INCIDENT_MULT = 1.5

    RISKY_STRATEGY_PROB = 0.12

    SC_FROM_CRASH_PROB = 0.35

    SC_GAP = 1.4

    SC_INLAP_PENALTY = 6.0

    SC_LAPS_MAX = 4

    SC_LAPS_MIN = 2

    SC_SPEED_MULT = 1.45

    SC_WET_BONUS = 0.2

    SLICK_FLOOD_PEN = 0.35

    SLIPSTREAM_GAP = 1.5

    SLIPSTREAM_TIME_GAIN = 0.04

    START_INCIDENT_MULT = 2.0

    START_OVERTAKE_BONUS = 0.04

    STRATEGY_STINT_MODIFIER = {'aggressive': {'pace': 1.1, 'tire_wear': 1.25, 'crash_risk': 1.5},
     'normal': {'pace': 1.0, 'tire_wear': 1.0, 'crash_risk': 1.0},
     'long_stint': {'pace': 0.9, 'tire_wear': 0.75, 'crash_risk': 0.8}}

    TYRE_COMPOUNDS = {'soft': {'pace': 0.006, 'wear_rate': 0.055, 'ideal_wet': 0.0, 'type': 'dry'},
     'medium': {'pace': 0.0, 'wear_rate': 0.04, 'ideal_wet': 0.0, 'type': 'dry'},
     'hard': {'pace': -0.005, 'wear_rate': 0.028, 'ideal_wet': 0.0, 'type': 'dry'},
     'inter': {'pace': -0.045, 'wear_rate': 0.045, 'ideal_wet': 0.4, 'type': 'wet'},
     'wet': {'pace': -0.09, 'wear_rate': 0.035, 'ideal_wet': 0.9, 'type': 'wet'}}

    UPGRADES_PER_RACE = 5

    VSC_FROM_CRASH_PROB = 0.3

    VSC_FROM_DAMAGE_PROB = 0.25

    VSC_FROM_MECH_PROB = 0.15

    VSC_LAPS_MAX = 3

    VSC_LAPS_MIN = 1

    VSC_SLOWDOWN = 1.28

    WEAR_CLIFF = 0.8

    WEAR_CLIFF_COEFF = 18.0

    WEAR_TIME_COEFF = 2.5

    WEATHER_REACTION_LAG = 1

    WET_CRASH_COEFF = 1.2

    WET_MISMATCH_PACE = 0.22

    WET_TYRE_BACK_THRESHOLD = 0.55

    WET_TYRE_THRESHOLD = 0.7

    WET_WEAR_COEFF = 0.45

    WRONG_TYRE_CRASH_STEP = 1.55

    XP_BASE_COST = 10

    XP_GROWTH_FACTOR = 1.15


    @classmethod
    def calculate_required_xp(cls, current_level: int) -> int:
        return int(cls.XP_BASE_COST * (cls.XP_GROWTH_FACTOR ** current_level))
