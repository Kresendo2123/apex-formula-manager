import random
from typing import List, Dict, Any


class Simulator:
    # Bulunulan sıraya göre Kazanma Ağırlığı Çarpanları
    POSITION_MULTIPLIERS = [
        1.85, 1.55, 1.25, 1.10, 1.05, 1.02, 1.00, 0.98, 0.95, 0.90,
        0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40,
        0.35, 0.30  # YENİ: 21. ve 22. Sıra Çarpanları
    ]

    # RADİKAL ÇÖZÜM: Favori Katsayısı (Exponential Factor)
    # Bu sayı büyüdükçe sürpriz ihtimali düşer, güçlü olan her zaman kazanır.
    # 4 veya 5 değeri F1 g erçekliğine en uygun makası yaratır.
    FAVORITE_FACTOR= 3.5

    def __init__(self):
        pass

    def simulate_race(self, race_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        dnf_list = []
        survivors = []

        # 1. Aşama: DNF (Yarış Dışı) Kontrolü
        for entry in race_entries:
            dnf_roll = random.uniform(0, 1000)
            if dnf_roll < entry["crash_risk"]:
                dnf_list.append(entry)
            else:
                survivors.append(entry)

        # 2. Aşama: Iterative Weighted Roulette Wheel
        current_position = 1

        while survivors:
            # Hayatta kalanları o anki ham güçlerine göre büyükten küçüğe sırala
            survivors.sort(key=lambda x: x["raw_power"], reverse=True)

            weights = []
            for idx, survivor in enumerate(survivors):
                mult_index = min(idx, len(self.POSITION_MULTIPLIERS) - 1)
                multiplier = self.POSITION_MULTIPLIERS[mult_index]

                # Doğrusal hesaplama (Base Weight)
                base_weight = survivor["raw_power"] * multiplier

                # Üstel hesaplama: Puan farklarını uçuruma dönüştür
                weight = base_weight ** self.FAVORITE_FACTOR
                weights.append(weight)

            # Ağırlıklı rastgele seçim
            chosen_survivor = random.choices(survivors, weights=weights, k=1)[0]

            chosen_survivor["position"] = current_position
            results.append(chosen_survivor)
            survivors.remove(chosen_survivor)

            current_position += 1

        # 3. Aşama: DNF Olanları Klasmanın Sonuna Ekle
        for dnf in dnf_list:
            dnf["position"] = current_position
            dnf["status"] = "DNF"
            results.append(dnf)
            current_position += 1

        return {
            "classification": results,
            "dnf_count": len(dnf_list)
        }