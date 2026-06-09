# engine/perks.py

"""
Bu dosyada oyundaki tüm özel yeteneklerin (Perk) Object Oriented karşılıkları bulunur.
Kullanıcı yeni bir perk eklemek isterse bu sınıflardan birini kalıtım (inherit) alarak ekleyebilir.
"""
from typing import Dict, Any, List

class Perk:
    """Temel Perk (Özel Yetenek) Sınıfı"""
    id: str = "Base Perk"
    description: str = "Temel yetenek"
    
    def apply_base_power_bonus(self, driver_eff_pace: float, driver_eff_cons: float, 
                               track: Any, is_raining: bool) -> float:
        """Base Power hesaplamasına direkt eklenecek gücü (bonus) döner."""
        return 0.0

    def apply_stat_modifier(self, stat_name: str, base_val: float, track: Any, is_raining: bool) -> float:
        """Pace, Consistency gibi statları geçici veya kalıcı olarak değiştirmek için kullanılır."""
        return base_val

    def modify_tire_wear(self, wear_amount: float) -> float:
        """Lastik aşınma oranını değiştirir."""
        return wear_amount
        
    def modify_reliability_penalty(self, penalty: float) -> float:
        """Mekanik arıza (DNF) cezasını değiştirir."""
        return penalty

    def modify_consistency_penalty(self, penalty: float) -> float:
        """Kaza ihtimali yaratan tutarsızlık cezasını değiştirir."""
        return penalty

    def apply_grid_advantage_modifier(self, grid_multiplier: float) -> float:
        """Start anındaki dezavantaj/avantaj katsayısını değiştirir."""
        return grid_multiplier

    def apply_xp_modifier(self, base_xp: int) -> int:
        """Kazanılan eğitim/geliştirme XP'sine çarpan uygular."""
        return base_xp


class Rainmaster(Perk):
    id = "Rainmaster"
    description = "Yağmurlu yarışlarda Pace +10 artar."
    
    def apply_stat_modifier(self, stat_name: str, base_val: float, track: Any, is_raining: bool) -> float:
        if stat_name == "pace" and is_raining:
            return base_val + 10.0
        return base_val


class Divebomber(Perk):
    id = "Divebomber"
    description = "Yarış içi baz gücüne +2 atak bonusu ekler, fakat kaza (crash) riski x1.5 artar."
    
    def apply_base_power_bonus(self, driver_eff_pace: float, driver_eff_cons: float, track: Any, is_raining: bool) -> float:
        return 2.0
        
    def modify_consistency_penalty(self, penalty: float) -> float:
        return penalty * 1.5


class TireWhisperer(Perk):
    id = "Tire Whisperer"
    description = "Lastik aşınmasını %20 yavaşlatır."
    
    def modify_tire_wear(self, wear_amount: float) -> float:
        return wear_amount * 0.8


class BareCanvas(Perk):
    id = "Bare Canvas"
    description = "Lastikler aşındıkça (%50'nin altı) yaşanan tur süresi kaybını (degradation) belirgin oranda azaltır."
    # Etkisi RaceEngine içinde handle edilir. (Modeli OOP'ta direkt motora enjekte etmek şimdilik zor, kontrol motorun içinde)


class ExperienceMaster(Perk):
    id = "Experience Master"
    description = "Sürücü, geliştirmelerden %20 daha fazla XP kazanır."
    
    def apply_xp_modifier(self, base_xp: int) -> int:
        return int(base_xp * 1.2)


class MrSaturday(Perk):
    id = "Mr. Saturday"
    description = "Sıralama turlarında (Qualifying) pilot formuna +2 bonus sağlar."
    # Etkisi Qualifying motorunda uygulanır.


class SmoothOperator(Perk):
    id = "Smooth Operator"
    description = "Araç arıza yapma (mekanik DNF) riskini %30 oranında düşürür."
    
    def modify_reliability_penalty(self, penalty: float) -> float:
        return penalty * 0.7


class ClutchStart(Perk):
    id = "Clutch Start"
    description = "Yarışın başında grid pozisyonu dezavantajından minimum düzeyde etkilenir."
    
    def apply_grid_advantage_modifier(self, grid_multiplier: float) -> float:
        if grid_multiplier < 1.0:
            return 1.0 - ((1.0 - grid_multiplier) * 0.5)
        return grid_multiplier


class DefensiveMinister(Perk):
    id = "Defensive Minister"
    description = "Savunma yeteneğini temsil eder, arkadan gelenlerin geçiş ihtimalini zorlaştırır (Consistency'e +5 bonus)."
    
    def apply_stat_modifier(self, stat_name: str, base_val: float, track: Any, is_raining: bool) -> float:
        if stat_name == "consistency":
            return base_val + 5.0
        return base_val


class StreetFighter(Perk):
    id = "Street Fighter"
    description = "Dar sokak pistlerinde (Monaco, Baku, Singapore vs. yüksek grip isteyen) Pace +5 artar."
    
    def apply_stat_modifier(self, stat_name: str, base_val: float, track: Any, is_raining: bool) -> float:
        if stat_name == "pace" and track.req_grip >= 0.40:
            return base_val + 5.0
        return base_val


class HighSpeedJunkie(Perk):
    id = "High Speed Junkie"
    description = "Düzlüklerin uzun olduğu pistlerde (Monza, Spa vb. düşük grip yüksek top speed isteyen) Pace +5 artar."
    
    def apply_stat_modifier(self, stat_name: str, base_val: float, track: Any, is_raining: bool) -> float:
        if stat_name == "pace" and track.req_top_speed >= 0.40:
            return base_val + 5.0
        return base_val


class PressureCooker(Perk):
    id = "Pressure Cooker"
    description = "Hata yapma (Consistency) riskini hesaplarken kaza riskini %20 düşürür."
    
    def modify_consistency_penalty(self, penalty: float) -> float:
        return penalty * 0.8


# Perk İsimlerini (ID'lerini) Sınıf Objelerine Mapleme
PERK_CLASSES = {
    "Rainmaster": Rainmaster,
    "Divebomber": Divebomber,
    "Tire Whisperer": TireWhisperer,
    "Bare Canvas": BareCanvas,
    "Experience Master": ExperienceMaster,
    "Mr. Saturday": MrSaturday,
    "Smooth Operator": SmoothOperator,
    "Clutch Start": ClutchStart,
    "Defensive Minister": DefensiveMinister,
    "Street Fighter": StreetFighter,
    "High Speed Junkie": HighSpeedJunkie,
    "Pressure Cooker": PressureCooker
}

def get_all_perk_names() -> List[str]:
    return list(PERK_CLASSES.keys())

def get_perk_instance(perk_id: str) -> Perk:
    """Perk isminden (string) polimorfik Sınıf objesini döner."""
    return PERK_CLASSES.get(perk_id, Perk)()
