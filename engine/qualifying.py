import random
from typing import List, Dict, Any

class Qualifying:
    def __init__(self, settings):
        self.settings = settings

    def _calculate_lap_time(self, driver, car, track, is_raining, form_val, track_evolution):
        """Sürücünün o anki şartlardaki tek tur zamanını hesaplar."""
        s = self.settings
        
        # 1. Temel Performans (Base Power)
        car_perf = (car.top_speed * track.req_top_speed) + \
                   (car.acceleration * track.req_acceleration) + \
                   (car.grip * track.req_grip)
        driver_perf = driver.get_effective_stat("pace")
        
        base_power = (car_perf * (1 - track.req_driver_skill)) + (driver_perf * track.req_driver_skill)
        
        # 2. Form ve Tesis Etkileri
        base_power *= (1 + form_val)
        
        # 3. Referans Tur Süresi
        track_base_time = getattr(track, "base_lap_time", None) or s.BASE_LAP_TIME
        diff = base_power - s.PACE_REFERENCE
        multiplier = 1 - (diff * s.PACE_SENSITIVITY)
        
        lap_time = track_base_time * multiplier
        
        # 4. Hava Durumu ve Pist Gelişimi (Track Evolution)
        # track_evolution: 0.0 (seans başı, yavaş) -> 1.0 (seans sonu, hızlı/lastik izli)
        # Pist gelişiminden dolayı tur süresi %1.5'e kadar kısalabilir.
        evolution_bonus = track_evolution * 0.015 
        lap_time *= (1 - evolution_bonus)
        
        # Yağmur Cezası
        if is_raining:
            lap_time *= (1 + s.WET_MISMATCH_PACE * 0.5)
            
        # 5. Rastgele Dalgalanma (Qualy'de kaza riski çok düşüktür)
        # Pilotun consistency statına göre dalgalanma
        noise = random.gauss(0, s.LAP_NOISE_BASE * s.QUALI_NOISE_MULT)
        lap_time *= (1 + noise)
        
        return round(lap_time, 3)

    def simulate_qualifying(self, drivers, cars, teams, track, season_is_raining, form=None):
        """
        Q1, Q2, Q3 formatında sıralama turlarını simüle eder.
        Döner: (grid_order, q3_tire_choices)
        """
        form = form or {}
        all_drivers = list(drivers.values())
        
        # Sonuçları tutmak için
        results = {d.id: {"q1": None, "q2": None, "q3": None, "tire": "medium"} for d in all_drivers}
        
        # --- SEANS BAŞLATICI ---
        # Q1: Herkes katılır
        q1_times = []
        for d in all_drivers:
            # Seans sonuna doğru tur atma şansı (Evolution yüksek)
            evolution = random.uniform(0.7, 1.0) 
            time = self._calculate_lap_time(d, cars[teams[d.team_id].car_id], track, season_is_raining, form.get(d.id, 0.0), evolution)
            q1_times.append((d.id, time))
            results[d.id]["q1"] = time
            
        q1_times.sort(key=lambda x: x[1])
        top_16 = [x[0] for x in q1_times[:16]] # Son 6 elenir (22 araç varsa)
        
        # Q2: İlk 16
        q2_times = []
        for d_id in top_16:
            d = drivers[d_id]
            evolution = random.uniform(0.8, 1.0)
            time = self._calculate_lap_time(d, cars[teams[d.team_id].car_id], track, season_is_raining, form.get(d.id, 0.0), evolution)
            q2_times.append((d_id, time))
            results[d_id]["q2"] = time
            
        q2_times.sort(key=lambda x: x[1])
        top_10 = [x[0] for x in q2_times[:10]] # Son 6 elenir
        
        # Q3: İlk 10
        q3_times = []
        q3_tire_compounds = {}
        for d_id in top_10:
            d = drivers[d_id]
            evolution = random.uniform(0.9, 1.0) # Q3'te pist en hızlı halindedir
            time = self._calculate_lap_time(d, cars[teams[d.team_id].car_id], track, season_is_raining, form.get(d.id, 0.0), evolution)
            q3_times.append((d_id, time))
            results[d_id]["q3"] = time
            
            # Q3'te kullanılan lastiği kaydet (Yarış başlangıç kuralı için)
            if season_is_raining:
                q3_tire_compounds[d_id] = "inter" if random.random() > 0.5 else "wet"
            else:
                q3_tire_compounds[d_id] = "soft" # Genelde en hızlı tur soft ile atılır
                
        q3_times.sort(key=lambda x: x[1])
        
        # NİHAİ GRİD OLUŞTURMA
        grid = []
        # 1-10: Q3 sıralaması
        grid.extend([x[0] for x in q3_times])
        # 11-16: Q2'de elenenler
        grid.extend([x[0] for x in q2_times[10:]])
        # 17-22: Q1'de elenenler
        grid.extend([x[0] for x in q1_times[16:]])
        
        return grid, q3_tire_compounds
