import random
from typing import Dict, Any
from engine.perks import get_perk_instance

class RaceDirector:
    def __init__(self, settings):
        self.settings = settings

    @staticmethod
    def ideal_aero(track, settings) -> float:
        """
        Pistin İDEAL aero kademesi (sürekli değer, 1.0-5.0).
        Grip talebinin (top_speed+grip içindeki) payından türetilir:
        Monza (düzlük) ~1, Monaco (viraj) ~5, dengeli pistler ~3.
        UI oyuncuya yuvarlanmış halini ipucu olarak gösterebilir.
        """
        g_share = track.req_grip / max(0.05, track.req_grip + track.req_top_speed)
        ideal = 3.0 + (g_share - 0.5) * settings.AERO_IDEAL_SPREAD
        return min(5.0, max(1.0, ideal))

    def build_profile(
            self, driver, car, track, aero_level: int, strategy: str, is_raining: bool
    ) -> Dict[str, Any]:
        """
        Bir araç-pilot kombinasyonunun DETERMİNİSTİK performans profilini üretir.
        RNG ve grid avantajı UYGULANMAZ; bunlar yarış motorunun sorumluluğundadır.
        Hem tek-atış (calculate_effective_power) hem de tur tabanlı motor bunu kullanır.
        """
        perk_instances = [get_perk_instance(p_id) for p_id in driver.perks]

        eff_pace = driver.get_effective_stat("pace")
        eff_consistency = driver.get_effective_stat("consistency")
        eff_attack = driver.get_effective_stat("attack_defense")
        eff_tire_mgmt = driver.get_effective_stat("tire_management")
        
        for perk in perk_instances:
            eff_pace = perk.apply_stat_modifier("pace", eff_pace, track, is_raining)
            eff_consistency = perk.apply_stat_modifier("consistency", eff_consistency, track, is_raining)
            eff_attack = perk.apply_stat_modifier("attack_defense", eff_attack, track, is_raining)
            eff_tire_mgmt = perk.apply_stat_modifier("tire_management", eff_tire_mgmt, track, is_raining)
            
        strat_mods = self.settings.STRATEGY_STINT_MODIFIER.get(
            strategy, self.settings.STRATEGY_STINT_MODIFIER["normal"]
        )
        car_performance = (car.top_speed * track.req_top_speed) + (car.acceleration * track.req_acceleration) + (
                    car.grip * track.req_grip)

        # Aero uyumu: pistin ideal kademesinden uzaklaştıkça parabolik ceza.
        # İdealde ceza yok; 1 kademe sapma ucuz, ters uç seçimi pahalı.
        aero_mismatch = (aero_level - self.ideal_aero(track, self.settings)) ** 2
        aero_penalty = min(self.settings.AERO_MISMATCH_MAX,
                           self.settings.AERO_MISMATCH_COEFF * aero_mismatch)
        car_performance *= (1 - aero_penalty)
        # Agresif stil saldırı/savunmada da avantaj verir (öndekini zorlama),
        # long_stint hafifçe pasifleştirir.
        eff_attack *= strat_mods.get("attack", 1.0)

        # Stil pace çarpanı TÜM sürücü performansına uygulanır (eskiden yalnız
        # eff_pace'e uygulanıyordu; etki o kadar küçük kalıyordu ki stil seçiminde
        # pace tarafı hiç hissedilmiyor, takas tek yönlü "aşınma kazanır"a dönüyordu).
        driver_performance = ((eff_pace * 0.5) + (eff_consistency * 0.3) + (
                    eff_attack * 0.2)) * strat_mods["pace"]

        # Aero'nun lastik etkisi (gerçekçi, küçük): az kanat = az tutuş = viraj
        # kayması -> lastiği ısıtıp yer; yüksek kanat aracı oturtur. İdealden
        # sapma da (hangi yöne olursa olsun) kaymayı artırır.
        aero_wear_mult = (1
                          + self.settings.AERO_WEAR_PER_LEVEL * (3 - aero_level)
                          + min(self.settings.AERO_WEAR_MISMATCH_MAX,
                                self.settings.AERO_WEAR_MISMATCH_COEFF * aero_mismatch))

        tire_wear = car.tire_consumption * strat_mods["tire_wear"] * aero_wear_mult * (1 - (eff_tire_mgmt * 0.005))
        tyre_wear_coeff_val = (
            strat_mods["tire_wear"]
            * aero_wear_mult
            * (1.9 - car.tire_consumption / 100.0)
            * (1 - eff_tire_mgmt * 0.003)
        )
        
        for perk in perk_instances:
            tire_wear = perk.modify_tire_wear(tire_wear)
            tyre_wear_coeff_val = perk.modify_tire_wear(tyre_wear_coeff_val)

        base_risk = self.settings.BASE_DNF_CHANCE * 1000
        reliability_penalty = (100 - car.reliability) * self.settings.RELIABILITY_RISK_SCALE
        consistency_penalty = (100 - eff_consistency) * strat_mods["crash_risk"]
        
        for perk in perk_instances:
            reliability_penalty = perk.modify_reliability_penalty(reliability_penalty)
            consistency_penalty = perk.modify_consistency_penalty(consistency_penalty)
            
        total_crash_risk = base_risk + reliability_penalty + consistency_penalty

        if is_raining:
            total_crash_risk *= self.settings.RAIN_DNF_MULTIPLIER

        base_power = (car_performance * (1 - track.req_driver_skill)) + (driver_performance * track.req_driver_skill)
        
        for perk in perk_instances:
            base_power += perk.apply_base_power_bonus(eff_pace, eff_consistency, track, is_raining)

        return {
            "driver_id": driver.id,
            "team_id": driver.team_id,
            "base_power": base_power,
            "crash_risk": total_crash_risk,
            "crash_incident_risk": base_risk + consistency_penalty,
            "mech_risk": reliability_penalty,
            "tire_wear": tire_wear,
            "tyre_wear_coeff": tyre_wear_coeff_val,
            "consistency": eff_consistency,
            "attack_defense": eff_attack,
            "tire_management": eff_tire_mgmt,
            "perks": driver.perks 
        }

    def calculate_effective_power(
            self, driver, car, track, aero_level: int, strategy: str,
            is_raining: bool, grid_position: int, current_lap: int = 1
    ) -> Dict[str, Any]:
        """Tek-atış (single-shot) rulet motoru veya Tur motorunun başlangıcı için güç hesaplar."""
        profile = self.build_profile(driver, car, track, aero_level, strategy, is_raining)
        perk_instances = [get_perk_instance(p_id) for p_id in driver.perks]

        variance_range = track.weather_volatility if is_raining else 0.05
        rng_multiplier = random.uniform(1 - variance_range, 1 + variance_range)
        final_power = profile["base_power"] * rng_multiplier

        # GRID AVANTAJI: Sadece yarışın başında (Lap 1) tam etkili olmalı.
        # Eğer current_lap > 1 ise bu avantajı tamamen devreden çıkarıyoruz.
        if current_lap == 1:
            grid_multiplier = self.settings.GRID_ADVANTAGE[grid_position - 1]
            for perk in perk_instances:
                grid_multiplier = perk.apply_grid_advantage_modifier(grid_multiplier)
            final_power *= grid_multiplier

        return {
            "driver_id": profile["driver_id"],
            "team_id": profile["team_id"],
            "raw_power": final_power,
            "crash_risk": profile["crash_risk"],
            "tire_wear": profile["tire_wear"],
        }
