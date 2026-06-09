import random
import copy
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.championship import Championship
from engine.strategy import plan_strategies, apply_qualifying_tire_rule
from main import load_data

def run_mass_simulation(num_seasons=10):
    settings = GameSettings()
    drivers_orig, cars_orig, teams_orig, tracks_orig = load_data()
    
    overall_driver_standings = {d_id: 0 for d_id in drivers_orig}
    overall_team_standings = {t_id: 0 for t_id in teams_orig}
    
    print(f"Büyük simülasyon başlatılıyor: {num_seasons} Sezon...")
    
    for season in range(1, num_seasons + 1):
        # Her sezon için farklı bir rastgele seed
        random.seed(season * 100)
        
        # Orijinal verileri kopyala (her sezon statlar sıfırdan başlar)
        drivers = copy.deepcopy(drivers_orig)
        cars = copy.deepcopy(cars_orig)
        teams = copy.deepcopy(teams_orig)
        tracks = copy.deepcopy(tracks_orig)
        
        director = RaceDirector(settings)
        engine = LapRaceEngine(settings)
        quali = Qualifying(settings)
        champ = Championship()
        
        for track in tracks:
            # Hafta sonu formu
            form = {d_id: random.gauss(0, settings.RACE_FORM_SIGMA) for d_id in drivers}
            
            # Sıralama turları
            is_quali_raining = random.random() < track.weather_volatility
            grid, q3_tire_choices = quali.simulate_qualifying(
                drivers, cars, teams, track, is_quali_raining, form=form
            )
            
            # Profiller
            profiles = {
                d_id: director.build_profile(drv, cars[teams[drv.team_id].car_id], track, 3, "normal", False)
                for d_id, drv in drivers.items()
            }
            
            # Strateji & Yarış
            num_laps = track.num_laps or settings.DEFAULT_RACE_LAPS
            forecast = engine.make_forecast(track, num_laps)
            strategies = plan_strategies(grid, forecast, num_laps, settings)
            apply_qualifying_tire_rule(strategies, q3_tire_choices, forecast)
            result = engine.simulate_race(grid, profiles, track, form=form,
                                          strategies=strategies, forecast=forecast)
            
            # Şampiyona puanı ekle
            champ.process_race_result(result["classification"])
            
        # Sezon sonu puanlarını genel toplama ekle
        for d_id, pts in champ.driver_standings.items():
            overall_driver_standings[d_id] += pts
        for t_id, pts in champ.team_standings.items():
            overall_team_standings[t_id] += pts
            
        if season % 10 == 0 or season == num_seasons:
            print(f"... {season} sezon tamamlandı.")
            
    # Ortalama Puanları Hesapla
    avg_driver_standings = {d_id: pts / num_seasons for d_id, pts in overall_driver_standings.items()}
    avg_team_standings = {t_id: pts / num_seasons for t_id, pts in overall_team_standings.items()}
    
    # Sırala
    sorted_drivers = sorted(avg_driver_standings.items(), key=lambda x: x[1], reverse=True)
    sorted_teams = sorted(avg_team_standings.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n--- {num_seasons} SEZON ORTALAMA SÜRÜCÜLER ŞAMPİYONASI ---")
    for idx, (d_id, pts) in enumerate(sorted_drivers, 1):
        drv_name = drivers_orig[d_id].name
        team_name = teams_orig[drivers_orig[d_id].team_id].name
        print(f"{idx}. {drv_name} ({team_name}): {pts:.1f} Puan")
        
    print(f"\n--- {num_seasons} SEZON ORTALAMA MARKALAR ŞAMPİYONASI ---")
    for idx, (t_id, pts) in enumerate(sorted_teams, 1):
        team_name = teams_orig[t_id].name
        print(f"{idx}. {team_name}: {pts:.1f} Puan")

if __name__ == "__main__":
    run_mass_simulation(10)
