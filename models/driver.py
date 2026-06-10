from pydantic import BaseModel, Field
from typing import ClassVar, List, Optional


class Driver(BaseModel):
    id: str
    team_id: Optional[str] = None  # Many2One -> Team
    name: str

    # Statlar (0-130 arası: 100 üstü "efsane bölge" — OSM tarzı sezon içi büyüme)
    pace: float = Field(..., ge=0, le=130)
    consistency: float = Field(..., ge=0, le=130)
    attack_defense: float = Field(..., ge=0, le=130)
    tire_management: float = Field(..., ge=0, le=130)
    potential: float = Field(..., ge=0, le=100)

    STAT_CAP: ClassVar[int] = 130

    # Her bir stat için XP takibi
    pace_xp: int = 0
    consistency_xp: int = 0
    attack_defense_xp: int = 0
    tire_management_xp: int = 0

    # Gelişim ve Özel Yetenekler
    perks: List[str] = Field(default_factory=list, max_length=2)
    
    # Kullanıcının aktif olarak geliştirmeyi seçtiği stat (ör: "pace", "consistency")
    focus_stat: Optional[str] = None

    def add_perk(self, perk_name: str) -> bool:
        """
        Sürücüye belirtilen perk'ü ekler.
        Eğer maksimum perk sayısına ulaşıldıysa veya perk zaten varsa False döner.
        """
        if len(self.perks) < 2 and perk_name not in self.perks:
            self.perks.append(perk_name)
            return True
        return False

    def get_effective_stat(self, stat_name: str) -> float:
        """
        Geçici etkiler vs. varsa statın efektif halini döndürür.
        Şu an için direk kendi statını döndürüyor.
        """
        return getattr(self, stat_name)

    def get_required_xp_for_stat(self, stat_name: str) -> int:
        """
        Belirtilen statın bir sonraki seviyeye geçmesi için gereken XP'yi hesaplar.
        Stat seviyesi arttıkça gereken XP üstel olarak artar.
        """
        # Kuartik eğri (stat^4): düşük seviyeler hızlı gelişir (OSM temposu),
        # 100+ "efsane bölge"ye doğru maliyet sertçe tırmanır. Bölen 1600,
        # 80 seviyesindeki maliyeti eski kübik eğriyle eşitleyecek şekilde seçildi.
        stat_value = getattr(self, stat_name)
        return int(100 + (stat_value ** 4) / 1600.0)

    def add_xp_to_stat(self, stat_name: str, base_xp_amount: int):
        """
        Belirtilen stata XP ekler ve yeterli XP varsa statı 1 arttırır.
        """
        if stat_name == "potential":
            raise ValueError("Potential statı geliştirilemez.")
            
        if not hasattr(self, stat_name) or not hasattr(self, f"{stat_name}_xp"):
            raise ValueError(f"Geçersiz veya geliştirilemez stat: {stat_name}")

        current_stat = getattr(self, stat_name)
        if current_stat >= self.STAT_CAP:
            return  # Stat maksimuma ulaşmışsa işlem yapma

        # Potansiyel Katsayısı Hesaplama
        potential_multiplier = self.potential / 50.0

        current_xp = getattr(self, f"{stat_name}_xp")
        # Yumuşak potansiyel tavanı: potansiyelin ÜSTÜNDEKİ her puan, seviye
        # atlamayı %3 zorlaştırır (96 potansiyelli pilotu 97 yapmak %3, 98 yapmak
        # %6 daha zor...). Eski %15/puan ceza fazla sertti, gelişimi öldürüyordu.
        def _soft_cap(stat_val):
            diff = max(0.0, stat_val - self.potential)
            return 1.0 / (1.0 + 0.03 * diff)

        current_xp += int(base_xp_amount * potential_multiplier * _soft_cap(current_stat))

        required_xp = self.get_required_xp_for_stat(stat_name)

        # XP barı dolduğu sürece seviye atlat
        while current_xp >= required_xp and current_stat < self.STAT_CAP:
            current_xp -= required_xp
            current_stat += 1
            setattr(self, stat_name, current_stat)
            required_xp = self.get_required_xp_for_stat(stat_name)

        # Kalan XP'yi kaydet
        setattr(self, f"{stat_name}_xp", current_xp)

    def train_focus_stat(self, xp_amount: int):
        """
        Odaklanılan stata XP verir.
        """
        if self.focus_stat:
            self.add_xp_to_stat(self.focus_stat, xp_amount)
