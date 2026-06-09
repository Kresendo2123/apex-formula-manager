import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
import copy
from config.game_settings import GameSettings
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.qualifying import Qualifying
from engine.championship import Championship
from engine.strategy import plan_strategies, apply_qualifying_tire_rule
from main import load_data

def calculate_theoretical_weights():
    """
    RaceDirector.build_profile() içindeki formüllere göre statların tur süresine
    etki eden baz puan üzerindeki teorik ağırlıklarını hesaplar.
    """
    settings = GameSettings()
    _, _, _, tracks = load_data()
    
    # Ortalama pist karakteristiklerini bul
    avg_req_top_speed = sum(t.req_top_speed for t in tracks) / len(tracks)
    avg_req_accel = sum(t.req_acceleration for t in tracks) / len(tracks)
    avg_req_grip = sum(t.req_grip for t in tracks) / len(tracks)
    avg_req_driver_skill = sum(t.req_driver_skill for t in tracks) / len(tracks)
    
    car_weight = (1 - avg_req_driver_skill)
    driver_weight = avg_req_driver_skill
    
    # Strateji çarpanı 'normal' olduğunu varsayarsak
    strat_pace_mod = settings.STRATEGY_STINT_MODIFIER["normal"]["pace"]
    
    # Araç statlarının car_performance içindeki çarpanları
    w_top_speed = avg_req_top_speed * car_weight
    w_acceleration = avg_req_accel * car_weight
    w_grip = avg_req_grip * car_weight
    
    # Sürücü statlarının driver_performance içindeki çarpanları
    w_pace = (strat_pace_mod * 0.5) * driver_weight
    w_consistency = 0.3 * driver_weight
    w_attack_defense = 0.2 * driver_weight
    
    total_w = w_top_speed + w_acceleration + w_grip + w_pace + w_consistency + w_attack_defense
    
    print("\n--- TEORİK BAZ GÜÇ AĞIRLIKLARI (Ortalama Bir Pistte) ---")
    print("Bu statlar RaceDirector içerisindeki 'base_power' değerini hesaplarken kullanılır.")
    print(f"Araç Ağırlığı (car_weight): %{car_weight*100:.1f}")
    print(f"Pilot Ağırlığı (driver_weight): %{driver_weight*100:.1f}\n")
    
    print("Araç Statları Etkisi:")
    print(f"  Top Speed:     %{ (w_top_speed/total_w)*100 :.2f}")
    print(f"  Acceleration:  %{ (w_acceleration/total_w)*100 :.2f}")
    print(f"  Grip:          %{ (w_grip/total_w)*100 :.2f}")
    
    print("Sürücü Statları Etkisi:")
    print(f"  Pace:          %{ (w_pace/total_w)*100 :.2f}")
    print(f"  Consistency:   %{ (w_consistency/total_w)*100 :.2f}")
    print(f"  Attack/Def:    %{ (w_attack_defense/total_w)*100 :.2f}")
    
    print("\n* Not: Reliability ve Consistency statları aynı zamanda DNF riskini etkiler.")
    print("* Not: Tire Consumption ve Tire Management statları doğrudan lastik aşınma hızını etkileyerek yarış içi pit stratejilerini şekillendirir.\n")

def simulate_stat_impact(target_stat, stat_type="car", num_seasons=3):
    """
    Belirli bir statın +10 artırılmasının, sezon sonundaki şampiyona puanına etkisini 
    Monte Carlo benzeri yöntemle (çoklu sezon simülasyonu) test eder.
    """
    settings = GameSettings()
    
    baseline_points = []
    upgraded_points = []
    
    print(f"Simüle ediliyor: {target_stat} (+10 Puan) | Sezon Sayısı: {num_seasons}")
    
    for seed in range(101, 101 + num_seasons):
        drivers, cars, teams, tracks = load_data()
        
        for d_id, drv in drivers.items():
            drv.pace = 80
            drv.consistency = 80
            drv.attack_defense = 80
            drv.tire_management = 80
            drv.potential = 80
        for c_id, car in cars.items():
            car.acceleration = 80
            car.top_speed = 80
            car.grip = 80
            car.reliability = 80
            car.tire_consumption = 80
            
        target_team_id = "T_MER"
        target_driver_id = teams[target_team_id].lead_driver_id
        
        champ_base = run_headless_season(copy.deepcopy(drivers), copy.deepcopy(cars), teams, tracks, settings, seed)
        base_score = champ_base.driver_standings.get(target_driver_id, 0)
        baseline_points.append(base_score)
        
        drivers_upg = copy.deepcopy(drivers)
        cars_upg = copy.deepcopy(cars)
        
        if stat_type == "car":
            car_id = teams[target_team_id].car_id
            current_val = getattr(cars_upg[car_id], target_stat)
            setattr(cars_upg[car_id], target_stat, current_val + 10)
        else:
            current_val = getattr(drivers_upg[target_driver_id], target_stat)
            setattr(drivers_upg[target_driver_id], target_stat, current_val + 10)
            
        champ_upg = run_headless_season(drivers_upg, cars_upg, teams, tracks, settings, seed)
        upg_score = champ_upg.driver_standings.get(target_driver_id, 0)
        upgraded_points.append(upg_score)
    
    avg_base = sum(baseline_points) / num_seasons
    avg_upg = sum(upgraded_points) / num_seasons
    diff = avg_upg - avg_base
    
    print(f" -> {target_stat.upper()}: Baseline Ort Puan: {avg_base:.1f} | Upgraded Ort Puan: {avg_upg:.1f} | FARK: +{diff:.1f} Puan")
    return diff

def run_headless_season(drivers, cars, teams, tracks, settings, seed):
    import random
    random.seed(seed)
    director = RaceDirector(settings)
    engine = LapRaceEngine(settings)
    quali = Qualifying(settings)
    champ = Championship()
    
    for track in tracks:
        form = {d_id: random.gauss(0, settings.RACE_FORM_SIGMA) for d_id in drivers}
        is_quali_raining = random.random() < track.weather_volatility
        grid, q3_tire_choices = quali.simulate_qualifying(
            drivers, cars, teams, track, is_quali_raining, form=form
        )
        profiles = {
            d_id: director.build_profile(drv, cars[teams[drv.team_id].car_id], track, 3, "normal", False)
            for d_id, drv in drivers.items()
        }
        num_laps = track.num_laps or settings.DEFAULT_RACE_LAPS
        forecast = engine.make_forecast(track, num_laps)
        strategies = plan_strategies(grid, forecast, num_laps, settings)
        apply_qualifying_tire_rule(strategies, q3_tire_choices, forecast)
        result = engine.simulate_race(grid, profiles, track, form=form,
                                      strategies=strategies, forecast=forecast)
        champ.process_race_result(result["classification"])
    return champ

if __name__ == "__main__":
    calculate_theoretical_weights()
    
    print("\n--- PRATİK ETKİ ANALİZİ (YARIŞ SİMÜLASYONLARI ÜZERİNDEN) ---")
    print("Herkes 80 stata sahipken, sadece 1 sürücünün/aracın tek bir statı +10 artırılır.")
    print("Simülasyon 3 tam sezon koşarak ortalama puan farkını bulur.\n")
    
    results = {}
    results["top_speed"] = simulate_stat_impact("top_speed", "car")
    results["acceleration"] = simulate_stat_impact("acceleration", "car")
    results["grip"] = simulate_stat_impact("grip", "car")
    results["reliability"] = simulate_stat_impact("reliability", "car")
    results["tire_consumption"] = simulate_stat_impact("tire_consumption", "car")
    
    results["pace"] = simulate_stat_impact("pace", "driver")
    results["consistency"] = simulate_stat_impact("consistency", "driver")
    results["attack_defense"] = simulate_stat_impact("attack_defense", "driver")
    results["tire_management"] = simulate_stat_impact("tire_management", "driver")
    
    print("\n--- SONUÇLAR (Etki Büyüklüğüne Göre Sıralı) ---")
    sorted_res = sorted(results.items(), key=lambda x: x[1], reverse=True)
    for stat, diff in sorted_res:
        print(f"{stat.upper():<18}: Sezon başına +{diff:.1f} puan")
