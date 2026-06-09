from pydantic import BaseModel, Field
from typing import Optional, Dict


class Team(BaseModel):
    id: str
    name: str

    # İlişkiler (Many2One)
    lead_driver_id: Optional[str] = None
    second_driver_id: Optional[str] = None
    car_id: Optional[str] = None
    
    # Ar-Ge Tesisleri (Seviye 1, 2, 3)
    # Seviyeler: 1 -> 1.0x, 2 -> 1.5x, 3 -> 2.2x
    facilities: Dict[str, int] = Field(default_factory=lambda: {
        "wind_tunnel": 1,   # Etkisi: Araç Grip ve Acceleration
        "simulator": 1,     # Etkisi: Sürücü Pace ve Consistency
        "factory": 1        # Etkisi: Araç Reliability, Top Speed ve Tire Consumption
    })
    
    # Devam eden tesis geliştirmesi
    active_facility_upgrade: Optional[str] = None
    facility_upgrade_remaining_races: int = 0
    
    # Takım içi dinamik: Geliştirme adaletsizliği
    # Her takıma yapılan sürücü geliştirmelerini sayar. Fark açıldıkça moral düşer.
    upgrades_done_driver1: int = 0
    upgrades_done_driver2: int = 0

    def start_facility_upgrade(self, facility_name: str, duration: int):
        """Bir tesisin geliştirmesini başlatır."""
        if self.active_facility_upgrade is not None:
            raise ValueError(f"{self.name} zaten {self.active_facility_upgrade} tesisini geliştiriyor.")
        if self.facilities.get(facility_name, 3) >= 3:
            return # Zaten maksimum seviyede
        
        self.active_facility_upgrade = facility_name
        self.facility_upgrade_remaining_races = duration
        
    def process_facility_upgrade(self):
        """Yarış sonrası geliştirme süresini azaltır. Bitince seviye atlatır."""
        if self.active_facility_upgrade:
            self.facility_upgrade_remaining_races -= 1
            if self.facility_upgrade_remaining_races <= 0:
                self.facilities[self.active_facility_upgrade] += 1
                self.active_facility_upgrade = None
                
    def get_facility_multiplier(self, facility_name: str) -> float:
        """Tesis seviyesine göre XP çarpanını döndürür."""
        level = self.facilities.get(facility_name, 1)
        if level == 1:
            return 1.0
        elif level == 2:
            return 1.5
        elif level >= 3:
            return 2.2
        return 1.0
