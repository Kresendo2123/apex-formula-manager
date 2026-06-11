import random
import re
import pandas as pd
import copy
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.championship import Championship
from engine.strategy import plan_strategies, apply_qualifying_tire_rule
from engine.perks import get_all_perk_names
from main import load_data
from models.game_universe import calculate_initial_power_rankings

settings = GameSettings()
drivers, cars, teams, tracks = load_data()


def _tag(d_id):
    drv = drivers[d_id]
    return f"{drv.name} ({teams[drv.team_id].name[:3].upper()})"


def _resolve(ev):
    """Olay mesajındaki ham driver_id'leri okunabilir isimlere çevirir."""
    msg = ev["msg"]
    for key in ("driver", "passed"):
        if key in ev and ev[key] in drivers:
            msg = msg.replace(ev[key], _tag(ev[key]))
    return msg


def _safe_sheet(idx, name):
    # Excel sayfa adı en fazla 31 karakter, bazı karakterler yasak
    clean = re.sub(r'[:\\/?*\[\]]', "", name)
    return f"{idx:02d} {clean}"[:31]


def format_time(total_seconds: float) -> str:
    """Saniyeyi saat:dakika:saniye.salise formatına çevirir."""
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

def run_season(seed=79 , filename="f1_season_races_report.xlsx"):
    random.seed(seed)
    
    # Baslangic statlarini kaydet
    initial_driver_stats = {d_id: {s: getattr(d, s) for s in ["pace", "consistency", "attack_defense", "tire_management", "potential"]} for d_id, d in drivers.items()}
    initial_car_stats = {c_id: {s: getattr(c, s) for s in ["acceleration", "top_speed", "grip", "reliability", "tire_consumption"]} for c_id, c in cars.items()}
    
    driver_stats = ["pace", "consistency", "attack_defense", "tire_management"] # Potential'ı çıkardık
    car_stats = ["acceleration", "top_speed", "grip", "reliability", "tire_consumption"]
    
    # Tüm perk isimleri
    available_perks = get_all_perk_names()
    
    # --- SEZON ÖNCESİ GÜÇ SIRALAMASINI (BEKLENEN SIRALAMA) HESAPLA ---
    expected_drv_std, expected_team_std = calculate_initial_power_rankings(drivers, cars, teams, tracks)

    # Geliştirme loglarını tutmak için yapı
    upgrade_history = {
        team_id: {"drivers": {}, "car": {s: 0 for s in car_stats}}
        for team_id in teams
    }
    
    for t_id, team in teams.items():
        team_drivers = [d for d in drivers.values() if d.team_id == t_id]
        for d in team_drivers:
             upgrade_history[t_id]["drivers"][d.id] = {s: 0 for s in driver_stats}
             upgrade_history[t_id]["drivers"][d.id]["perk_gained"] = 0

    # Takım geliştirme stratejilerini belirle (Sürücü odaklı, Araç odaklı, Dengeli)
    team_strategies = {}
    for t_id in teams:
        strategy_type = random.choice(["driver_focused", "car_focused", "balanced"])
        
        if strategy_type == "driver_focused":
            weights = {"driver1": 0.40, "driver2": 0.40, "car": 0.20}
        elif strategy_type == "car_focused":
            weights = {"driver1": 0.15, "driver2": 0.15, "car": 0.70}
        else: # balanced
            weights = {"driver1": 0.25, "driver2": 0.25, "car": 0.50}
            
        team_strategies[t_id] = weights
    
    director = RaceDirector(settings)
    engine = LapRaceEngine(settings)
    quali = Qualifying(settings)
    champ = Championship()

    overview_rows = []
    race_pages = []   # (sheet_name, events_df, result_df)

    print(f"🏁 Sezon simüle ediliyor (seed={seed})...")
    for race_no, track in enumerate(tracks, 1):
        
        # Her yarış öncesi tesis durumlarını güncelle
        for t_id, team in teams.items():
            if team.active_facility_upgrade:
                team.process_facility_upgrade()
            else:
                # Rastgele bir tesis geliştirme başlat (Eğer boşta ise ve hepsi max değilse)
                facilities = ["wind_tunnel", "simulator", "factory"]
                random.shuffle(facilities)
                for f in facilities:
                    if team.facilities.get(f, 1) < 3:
                        # HATA BURADAYDI, DÜZELTİLDİ:
                        team.start_facility_upgrade(f, settings.FACILITY_UPGRADE_TIME)
                        break
        
        UPGRADES_PER_RACE = settings.UPGRADES_PER_RACE
        DRIVER_XP = settings.DRIVER_XP_PER_UPGRADE
        CAR_XP = settings.CAR_XP_PER_UPGRADE
        
        for t_id, team in teams.items():
            team_drivers = [d for d in drivers.values() if d.team_id == t_id]
            car = cars[team.car_id]
            weights = team_strategies[t_id]
            
            for _ in range(UPGRADES_PER_RACE):
                rand_val = random.random()
                if rand_val < weights["driver1"] and len(team_drivers) > 0:
                    choice = "driver1"
                elif rand_val < (weights["driver1"] + weights["driver2"]) and len(team_drivers) > 1:
                    choice = "driver2"
                else:
                    choice = "car"
                
                if choice == "driver1" or choice == "driver2":
                    drv = team_drivers[0] if choice == "driver1" else team_drivers[1]
                    
                    # %10 ihtimalle sürücü XP yerine yeni bir Perk öğrenmeyi dener
                    if random.random() < settings.PERK_LEARN_CHANCE and len(drv.perks) < settings.MAX_PERKS_PER_DRIVER:
                        potential_new_perks = [p for p in available_perks if p not in drv.perks]
                        if potential_new_perks:
                            new_perk = random.choice(potential_new_perks)
                            drv.add_perk(new_perk)
                            upgrade_history[t_id]["drivers"][drv.id]["perk_gained"] += 1
                            continue # XP verme, hak perk kazanmaya gitti
                    
                    # Perk kazanmadıysa normal XP ver
                    stat = random.choice(driver_stats)
                    # Sürücü geliştirmeleri Simülatörden etkilenir
                    multiplier = team.get_facility_multiplier("simulator")
                    
                    exp_bonus = 1.0
                    from engine.perks import get_perk_instance
                    for p_id in drv.perks:
                        perk_obj = get_perk_instance(p_id)
                        exp_bonus = perk_obj.apply_xp_modifier(exp_bonus)
                        
                    drv.add_xp_to_stat(stat, int(DRIVER_XP * multiplier * exp_bonus))
                    upgrade_history[t_id]["drivers"][drv.id][stat] += 1
                    
                else:
                    stat = random.choice(car_stats)
                    if stat in ["grip", "acceleration"]:
                        multiplier = team.get_facility_multiplier("wind_tunnel")
                    else:
                        multiplier = team.get_facility_multiplier("factory")
                    
                    car.add_xp_to_stat(stat, int(CAR_XP * multiplier))
                    upgrade_history[t_id]["car"][stat] += 1

        # Hafta sonu formu (sıralama + yarışta aynı)
        form = {d_id: random.gauss(0, settings.RACE_FORM_SIGMA) for d_id in drivers}

        is_quali_raining = random.random() < track.weather_volatility
        # Qualifying.simulate_qualifying artık iki değer dönüyor (grid, compounds)
        grid, q3_tire_choices = quali.simulate_qualifying(drivers, cars, teams, track, is_quali_raining, form=form)

        profiles = {
            d_id: director.build_profile(drv, cars[teams[drv.team_id].car_id], track, 3, "normal", is_raining=False)
            for d_id, drv in drivers.items()
        }
        
        # Yarış içi yağmur tahmini ve strateji belirleme
        num_laps = track.num_laps or settings.DEFAULT_RACE_LAPS
        forecast = engine.make_forecast(track, num_laps)
        strategies = plan_strategies(grid, forecast, num_laps, settings, track=track)
        
        apply_qualifying_tire_rule(strategies, q3_tire_choices, forecast)

        # Simüle edilecek yarış esnasında yağmur yağıyorsa profil yeniden hesaplanır
        result = engine.simulate_race(grid, profiles, track, form=form,
                                      strategies=strategies, forecast=forecast)
        champ.process_race_result(result["classification"])

        grid_pos = {d_id: i + 1 for i, d_id in enumerate(grid)}
        cls = result["classification"]
        winner = next(e["driver_id"] for e in cls if e["position"] == 1)
        ev_types = {e["type"] for e in result["events"]}

        # --- Olaylar sayfası verisi ---
        ev_rows = []
        for ev in result["events"]:
            ev_rows.append({
                "Tur": "-" if ev["lap"] == 0 else ev["lap"],
                "Tip": ev["type"],
                "Açıklama": _resolve(ev),
            })
        events_df = pd.DataFrame(ev_rows)

        # --- Sonuç tablosu verisi (YENİ SÜRE FORMATI) ---
        res_rows = []
        
        winner_time = None
        winner_laps = 0
        for e in cls:
            if e["position"] == 1 and e["status"] == "FIN":
                winner_time = e["total_time"]
                winner_laps = e["laps_completed"]
                break
                
        for i, e in enumerate(cls):
            d_id = e["driver_id"]
            delta = grid_pos[d_id] - e["position"]
            if e["status"] == "DNF":
                durum = f"DNF ({e.get('dnf_cause', 'crash')})"
            else:
                if e["position"] == 1:
                    durum = format_time(e["total_time"])
                else:
                    lap_diff = winner_laps - e["laps_completed"]
                    if lap_diff > 0:
                        durum = f"+{lap_diff} LAP"
                    else:
                        prev_time = cls[i-1]["total_time"]
                        time_diff = e["total_time"] - prev_time
                        sec = int(time_diff)
                        ms = int(round((time_diff - sec) * 1000))
                        durum = f"+{sec}.{ms:03d}"
                        
            res_rows.append({
                "Sıra": e["position"],
                "Pilot": drivers[d_id].name,
                "Takım": teams[e["team_id"]].name,
                "Grid": grid_pos[d_id],
                "Δ": (f"+{delta}" if delta > 0 else (str(delta) if delta < 0 else "·")),
                "Pit": e["pits"],
                "Son Lastik": e["final_compound"],
                "Durum (Fark)": durum,
            })
        result_df = pd.DataFrame(res_rows)

        race_pages.append((_safe_sheet(race_no, track.name), events_df, result_df))

        overview_rows.append({
            "No": race_no,
            "Pist": track.name,
            "Pole": drivers[grid[0]].name,
            "Kazanan": drivers[winner].name,
            "Yağış Tah.": f"%{forecast['rain_prob'] * 100:.0f}",
            "Gerçek Yağış": "Evet" if result["rained"] else "Hayır",
            "En Yüksek Islaklık": result["weather_peak"],
            "Güvenlik Aracı": "Evet" if (ev_types & {"SC", "RED_FLAG"}) else ("VSC" if "VSC" in ev_types else "Hayır"),
            "DNF": result["dnf_count"],
        })

    overview_df = pd.DataFrame(overview_rows)

    # --- Şampiyona Puan Durumu ve Beklenen ile Karşılaştırma ---
    # Gerçek pilot sıralamasını (dict) elde et: {driver_id: rank}
    sorted_drv_standings = sorted(
        drivers.items(), 
        key=lambda item: champ.driver_standings.get(item[0], 0), 
        reverse=True
    )
    actual_drv_rank = {d_id: idx + 1 for idx, (d_id, _) in enumerate(sorted_drv_standings)}
    
    drv_rows = []
    for d_id, drv in sorted_drv_standings:
        exp_pos = expected_drv_std[d_id]
        act_pos = actual_drv_rank[d_id]
        change = exp_pos - act_pos
        change_str = f"+{change}" if change > 0 else (str(change) if change < 0 else "·")
        
        drv_rows.append({
            "Pilot": drv.name,
            "Takım": teams[drv.team_id].name,
            "Puan": champ.driver_standings.get(d_id, 0),
            "Beklenen Sıra": exp_pos,
            "Gerçekleşen Sıra": act_pos,
            "Değişim": change_str,
            "Perkler": ", ".join(drv.perks) if drv.perks else "Yok"
        })
    drivers_std = pd.DataFrame(drv_rows)
    drivers_std.index += 1

    # Gerçek takım sıralamasını (dict) elde et
    sorted_team_standings = sorted(
        teams.items(),
        key=lambda item: champ.team_standings.get(item[0], 0),
        reverse=True
    )
    actual_team_rank = {t_id: idx + 1 for idx, (t_id, _) in enumerate(sorted_team_standings)}
    
    team_rows = []
    for t_id, tm in sorted_team_standings:
        exp_pos = expected_team_std[t_id]
        act_pos = actual_team_rank[t_id]
        change = exp_pos - act_pos
        change_str = f"+{change}" if change > 0 else (str(change) if change < 0 else "·")
        
        team_rows.append({
            "Takım": tm.name, 
            "Puan": champ.team_standings.get(t_id, 0),
            "Beklenen Sıra": exp_pos,
            "Gerçekleşen Sıra": act_pos,
            "Değişim": change_str,
            "Rüzgar Tüneli": tm.facilities.get('wind_tunnel', 1),
            "Simülatör": tm.facilities.get('simulator', 1),
            "Fabrika": tm.facilities.get('factory', 1)
        })
    teams_std = pd.DataFrame(team_rows)
    teams_std.index += 1
    
    # --- Geliştirme Raporu (Stat Değişimleri) ---
    upgrade_rows = []
    for t_id, team in teams.items():
        # Takım stratejisini rapora ekle
        strategy = ""
        w = team_strategies[t_id]
        if w["car"] > 0.6:
            strategy = "Araç Odaklı"
        elif w["driver1"] > 0.3:
            strategy = "Sürücü Odaklı"
        else:
            strategy = "Dengeli"
            
        # Sürücüler
        team_drivers = [d for d in drivers.values() if d.team_id == t_id]
        for drv in team_drivers:
            row = {"Takım": team.name, "Strateji": strategy, "Tip": "Sürücü", "İsim": drv.name}
            for stat in driver_stats:
                initial = initial_driver_stats[drv.id][stat]
                final = getattr(drv, stat)
                times_upgraded = upgrade_history[t_id]["drivers"][drv.id][stat]
                row[f"{stat} (İlk)"] = initial
                row[f"{stat} (Gelişim sayısı)"] = times_upgraded
                row[f"{stat} (Son)"] = final
            # Ek olarak öğrenilen perk sayısını da yaz
            row["Kazanılan Perk Sayısı"] = upgrade_history[t_id]["drivers"][drv.id]["perk_gained"]
            upgrade_rows.append(row)
            
        # Araç
        car = cars[team.car_id]
        row = {"Takım": team.name, "Strateji": strategy, "Tip": "Araç", "İsim": car.id}
        for stat in car_stats:
             initial = initial_car_stats[car.id][stat]
             final = getattr(car, stat)
             times_upgraded = upgrade_history[t_id]["car"][stat]
             row[f"{stat} (İlk)"] = initial
             row[f"{stat} (Gelişim sayısı)"] = times_upgraded
             row[f"{stat} (Son)"] = final
        row["Kazanılan Perk Sayısı"] = "-"
        upgrade_rows.append(row)
        
    upgrade_df = pd.DataFrame(upgrade_rows)


    # --- Excel'e yaz ---
    filepath = os.path.join(os.path.dirname(__file__), '..', filename)
    with pd.ExcelWriter(filepath, engine="openpyxl") as w:
        overview_df.to_excel(w, sheet_name="Özet", index=False)

        drivers_std.to_excel(w, sheet_name="Şampiyona", index_label="Sıra", startrow=1)
        teams_std.to_excel(w, sheet_name="Şampiyona", index_label="Sıra", startrow=len(drivers_std) + 5)
        ws = w.sheets["Şampiyona"]
        ws.cell(row=1, column=1, value="PİLOTLAR ŞAMPİYONASI")
        ws.cell(row=len(drivers_std) + 5, column=1, value="MARKALAR ŞAMPİYONASI")
        
        # Geliştirme Raporu
        upgrade_df.to_excel(w, sheet_name="Geliştirme Raporu", index=False)

        for sheet, ev_df, res_df in race_pages:
            ev_df.to_excel(w, sheet_name=sheet, index=False, startrow=1)
            res_start = 1 + len(ev_df) + 3
            res_df.to_excel(w, sheet_name=sheet, index=False, startrow=res_start)
            ws = w.sheets[sheet]
            ws.cell(row=1, column=1, value="KRİTİK ANLAR")
            ws.cell(row=res_start, column=1, value="SONUÇ")

    print(f"\n✅ Sezon tamamlandı. {len(tracks)} yarış + Özet + Şampiyona + Geliştirme sayfaları yazıldı.")
    print(f"📊 '{filepath}' — şampiyon: {drivers_std.iloc[0]['Pilot']} ({drivers_std.iloc[0]['Puan']} puan)")


if __name__ == "__main__":
    run_season()
