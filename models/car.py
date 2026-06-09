from pydantic import BaseModel, Field
from typing import Optional


class Car(BaseModel):
    id: str
    team_id: Optional[str] = None  # Many2One -> Team

    # Araç Statları (0-100 arası validasyon)
    acceleration: float = Field(..., ge=0, le=100)
    top_speed: float = Field(..., ge=0, le=100)
    grip: float = Field(..., ge=0, le=100)
    reliability: float = Field(..., ge=0, le=100)
    tire_consumption: float = Field(..., ge=0, le=100)

    # Her bir stat için XP/Gelişim takibi
    acceleration_xp: int = 0
    top_speed_xp: int = 0
    grip_xp: int = 0
    reliability_xp: int = 0
    tire_consumption_xp: int = 0

    # Kullanıcının aktif olarak geliştirmeyi seçtiği stat (ör: "top_speed", "grip")
    focus_stat: Optional[str] = None

    def get_required_xp_for_stat(self, stat_name: str) -> int:
        """
        Belirtilen araç statının bir sonraki seviyeye geçmesi için gereken geliştirme puanını (XP) hesaplar.
        Stat seviyesi arttıkça gereken XP (çok daha dik bir eğriyle) artar.
        (Örn: 70 olan bir stat için daha az, 90 olan bir stat için çok daha fazla XP gerekir.)
        """
        stat_value = getattr(self, stat_name)
        # Formül: 500 baz XP + (Stat^4) / 700.0
        # Araçların üst seviyelere gelmesini çok daha maliyetli yapmak için 4. kuvveti (kuartik) aldık.
        # Örneğin:
        # stat 70 -> 500 + (24,010,000 / 700) = ~34,800 XP
        # stat 80 -> 500 + (40,960,000 / 700) = ~59,014 XP
        # stat 90 -> 500 + (65,610,000 / 700) = ~94,228 XP
        # stat 99 -> 500 + (96,059,601 / 700) = ~137,728 XP
        return int(500 + (stat_value ** 4) / 700.0)

    def add_xp_to_stat(self, stat_name: str, xp_amount: int):
        """
        Belirtilen stata geliştirme puanı ekler ve yeterliyse statı 1 arttırır.
        """
        if not hasattr(self, stat_name) or not hasattr(self, f"{stat_name}_xp"):
            raise ValueError(f"Geçersiz veya geliştirilemez stat: {stat_name}")

        current_stat = getattr(self, stat_name)
        if current_stat >= 100:
            return  # Stat maksimuma ulaşmışsa işlem yapma

        current_xp = getattr(self, f"{stat_name}_xp")
        current_xp += xp_amount

        required_xp = self.get_required_xp_for_stat(stat_name)

        # XP barı dolduğu sürece seviye atlat
        while current_xp >= required_xp and current_stat < 100:
            current_xp -= required_xp
            current_stat += 1
            setattr(self, stat_name, current_stat)
            # Stat arttığı için yeni gereken XP miktarını tekrar hesapla
            required_xp = self.get_required_xp_for_stat(stat_name)

        # Kalan XP'yi kaydet
        setattr(self, f"{stat_name}_xp", current_xp)

    def upgrade_focus_stat(self, xp_amount: int):
        """
        Odaklanılan stata XP verir.
        """
        if self.focus_stat:
            self.add_xp_to_stat(self.focus_stat, xp_amount)
