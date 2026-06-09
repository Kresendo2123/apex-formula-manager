import random
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.strategy import plan_strategies, apply_qualifying_tire_rule
from main import load_data

def run_narrative_race():
    settings = GameSettings()
    drivers, cars, teams, tracks = load_data()
    
    # 24 pist içinden rastgele birini seç
    track = random.choice(tracks)
    num_laps = track.num_laps or settings.DEFAULT_RACE_LAPS
    
    # Hafta sonu form salınımı
    form = {d_id: random.gauss(0, settings.RACE_FORM_SIGMA) for d_id in drivers}
    
    # Qualifying (Sıralama)
    quali = Qualifying(settings)
    is_quali_raining = random.random() < track.weather_volatility
    grid, q3_tire_choices = quali.simulate_qualifying(
        drivers, cars, teams, track, is_quali_raining, form=form
    )
    
    # Her araca ait performans profillerini hesapla
    director = RaceDirector(settings)
    profiles = {
        d_id: director.build_profile(drv, cars[teams[drv.team_id].car_id], track, 3, "normal", False)
        for d_id, drv in drivers.items()
    }
    
    # Yarış simülasyonu
    engine = LapRaceEngine(settings)
    forecast = engine.make_forecast(track, num_laps)
    strategies = plan_strategies(grid, forecast, num_laps, settings)
    apply_qualifying_tire_rule(strategies, q3_tire_choices, forecast)
    
    result = engine.simulate_race(grid, profiles, track, form=form,
                                  strategies=strategies, forecast=forecast)
    
    print(f"\n==================================================")
    print(f"🏎️  GRAND PRIX: {track.name}")
    print(f"🌦️  Tahmin: {forecast['label']}")
    print(f"==================================================\n")
    
    # Yarış Olayları (Spiker Anlatımı)
    print("🎙️ YARIŞ ANLATIMI (Kritik Olaylar):")
    for ev in result["events"]:
        if ev["lap"] == 0:
            lap_str = "START"
        else:
            lap_str = f"Tur {ev['lap']:02d}"
        
        # Olay mesajındaki id'leri isimle değiştir
        msg = ev["msg"]
        for key in ("driver", "passed"):
            if key in ev and ev[key] in drivers:
                drv = drivers[ev[key]]
                tag = f"{drv.name} ({teams[drv.team_id].name[:3].upper()})"
                msg = msg.replace(ev[key], tag)
                
        print(f"[{lap_str}] [{ev['type']}] {msg}")
    
    # Sonuç Klasmanı
    print("\n🏁 YARIŞ SONUCU:")
    grid_pos = {d_id: i + 1 for i, d_id in enumerate(grid)}
    
    winner_time = None
    winner_laps = 0
    for e in result["classification"]:
        if e["position"] == 1 and e["status"] == "FIN":
            winner_time = e["total_time"]
            winner_laps = e["laps_completed"]
            break

    def format_time(total_seconds):
        if total_seconds is None:
            return ""
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int(round((total_seconds - int(total_seconds)) * 1000))
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        else:
            return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
            
    print(f"{'Sıra':<5} | {'Pilot':<15} | {'Takım':<15} | {'Grid':<4} | {'Δ':<4} | {'Pit':<3} | {'Durum'}")
    print("-" * 75)
    
    for i, e in enumerate(result["classification"]):
        d_id = e["driver_id"]
        delta = grid_pos[d_id] - e["position"]
        delta_str = f"+{delta}" if delta > 0 else (str(delta) if delta < 0 else "-")
        
        if e["status"] == "DNF":
            durum = f"DNF ({e.get('dnf_cause', 'Unknown')})"
        else:
            if e["position"] == 1:
                durum = format_time(e["total_time"])
            else:
                lap_diff = winner_laps - e["laps_completed"]
                if lap_diff > 0:
                    durum = f"+{lap_diff} LAP"
                else:
                    prev_time = result["classification"][i-1]["total_time"]
                    time_diff = e["total_time"] - prev_time
                    sec = int(time_diff)
                    ms = int(round((time_diff - sec) * 1000))
                    durum = f"+{sec}.{ms:03d}"
                    
        drv_name = drivers[d_id].name
        team_name = teams[e["team_id"]].name
        
        print(f"{e['position']:<5} | {drv_name:<15} | {team_name:<15} | {grid_pos[d_id]:<4} | {delta_str:<4} | {e['pits']:<3} | {durum}")

if __name__ == "__main__":
    run_narrative_race()
