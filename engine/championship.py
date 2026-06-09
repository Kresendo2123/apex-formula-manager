from typing import List, Dict, Any


class Championship:
    # FIA bazlı standart ilk 10 puan sistemi
    POINT_SYSTEM = {
        1: 25, 2: 18, 3: 15, 4: 12, 5: 10,
        6: 8, 7: 6, 8: 4, 9: 2, 10: 1
    }

    # POINT_SYSTEM = {
    #     1: 10, 2: 9, 3: 8, 4: 7, 5: 6,
    #     6: 5, 7: 4, 8: 3, 9: 2, 10: 1
    # }

    def __init__(self):
        # Gerçek veritabanı (PostgreSQL) bağlanana kadar anlık state (durum) tutucu
        self.driver_standings = {}
        self.team_standings = {}

    def process_race_result(self, classification: List[Dict[str, Any]]):
        """
        Yarış sonucunu alır, sırasıyla pilot ve takım puanlarını günceller.
        classification: simulator.simulate_race() modülünden dönen nihai liste.
        """
        self._update_driver_standings(classification)
        self._update_team_standings(classification)

    def _update_driver_standings(self, classification: List[Dict[str, Any]]):
        """
        İlk 10'a giren pilotlara puanlarını ekler.
        """
        for entry in classification:
            pos = entry.get("position")
            driver_id = entry.get("driver_id")

            # Pilot sözlükte yoksa 0 puanla başlat
            if driver_id not in self.driver_standings:
                self.driver_standings[driver_id] = 0

            # Eğer pilot puan alan bir pozisyondaysa puanını ekle
            if pos in self.POINT_SYSTEM:
                self.driver_standings[driver_id] += self.POINT_SYSTEM[pos]

    def _update_team_standings(self, classification: List[Dict[str, Any]]):
        """
        İlk 10'a giren pilotların takımlarına puanlarını ekler.
        (Her takımın 2 pilotu olduğu için puanlar kümülatif toplanır)
        """
        for entry in classification:
            pos = entry.get("position")
            team_id = entry.get("team_id")

            # Sadece puan alan pozisyonlar için işlem yap
            if pos in self.POINT_SYSTEM:
                # Takım sözlükte yoksa 0 puanla başlat
                if team_id not in self.team_standings:
                    self.team_standings[team_id] = 0

                self.team_standings[team_id] += self.POINT_SYSTEM[pos]