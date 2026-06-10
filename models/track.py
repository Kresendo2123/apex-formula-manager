from pydantic import BaseModel, Field
from typing import Optional


class Track(BaseModel):
    id: str
    name: str

    # Pist Karakteristiği (Çarpanlar)
    req_top_speed: float = Field(..., description="Pistin Top Speed ağırlığı")
    req_acceleration: float = Field(..., description="Pistin Hızlanma ağırlığı")
    req_grip: float = Field(..., description="Pistin Yol Tutuş ağırlığı")
    req_driver_skill: float = Field(..., description="Pistin Pilot yeteneğine dayandığı oran")
    weather_volatility: float = Field(..., description="Hava koşullarının değişme ihtimali")

    # Tur tabanlı motor için opsiyonel alanlar (verilmezse motor mantıklı varsayılan üretir)
    num_laps: Optional[int] = Field(default=None, description="Yarış tur sayısı")
    base_lap_time: Optional[float] = Field(default=None, description="Pistin referans tur süresi (saniye)")
    pit_loss: Optional[float] = Field(default=None, description="Bu pistteki pit stop'un net süre kaybı (saniye)")
    overtaking_difficulty: Optional[float] = Field(
        default=None, ge=0, le=1, description="0=kolay sollama (Monza), 1=imkansız (Monako)"
    )
    tyre_severity: Optional[float] = Field(
        default=None, gt=0,
        description="Lastik aşınma şiddeti (verilmezse req_grip'ten türetilir). "
                    "Yavaş sokak pistleri (Monako) grip istese de lastiği AZ yer — "
                    "formül bunu bilemediği için açık değer verilebilir."
    )