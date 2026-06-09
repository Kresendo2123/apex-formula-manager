import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import sys
import os

# Üst dizini sys.path'e ekle ki ana modüllerden import yapılabilsin
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.game_settings import GameSettings
from models.game_universe import GameUniverse

class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Apex Formula Manager - Admin Kontrol Paneli")
        self.geometry("1100x700")
        
        # --- Oyun Evrenini Başlat ---
        self.settings = GameSettings()
        self.universe = GameUniverse(self.settings)
        self.universe.setup_season()
        
        self.build_ui()
        self.update_ui()
        
    def build_ui(self):
        # Üst Bilgi Barı
        top_frame = tk.Frame(self, bg="#2C3E50")
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        self.race_lbl = tk.Label(top_frame, text="Sezon Başlamadı (0/24)", font=("Arial", 16, "bold"), bg="#2C3E50", fg="white")
        self.race_lbl.pack(side=tk.LEFT, padx=15, pady=15)
        
        self.btn_next = tk.Button(top_frame, text="İlerle (Sonraki Yarışı Simüle Et) ⏭", font=("Arial", 12, "bold"), bg="#27AE60", fg="white", command=self.simulate_next_race)
        self.btn_next.pack(side=tk.RIGHT, padx=15, pady=15)
        
        # Sekmeler (Tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        self.tab_standings = ttk.Frame(self.notebook)
        self.tab_stats = ttk.Frame(self.notebook)
        self.tab_upgrades = ttk.Frame(self.notebook)
        self.tab_race = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_standings, text="🏆 Şampiyona Puan Durumu")
        self.notebook.add(self.tab_stats, text="📊 Pilot & Tesis Durumları")
        self.notebook.add(self.tab_upgrades, text="🛠️ Son Yarış Arası Geliştirmeler")
        self.notebook.add(self.tab_race, text="🏁 Son Yarış Sonucu")
        
        # Şampiyona Ağaçları (Tables)
        frame_drv_std = tk.Frame(self.tab_standings)
        frame_drv_std.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5, pady=5)
        frame_tm_std = tk.Frame(self.tab_standings)
        frame_tm_std.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        self.tree_drv_std = self.create_tree(frame_drv_std, "Pilotlar Şampiyonası")
        self.tree_team_std = self.create_tree(frame_tm_std, "Markalar Şampiyonası")
        
        # Statlar
        frame_drv_stats = tk.Frame(self.tab_stats)
        frame_drv_stats.pack(side=tk.TOP, expand=True, fill=tk.BOTH, padx=5, pady=5)
        frame_fac_stats = tk.Frame(self.tab_stats)
        frame_fac_stats.pack(side=tk.BOTTOM, expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        self.tree_stats = self.create_tree(frame_drv_stats, "Pilot Statları ve Kazanılan Perkler")
        self.tree_fac = self.create_tree(frame_fac_stats, "Takım Ar-Ge Tesisleri")
        
        # Geliştirmeler ve Sonuç
        self.tree_upgrades = self.create_tree(self.tab_upgrades, "Yarış Öncesi Yapılan Yatırımlar")
        self.tree_race = self.create_tree(self.tab_race, "Yarış Klasmanı")
        
    def create_tree(self, parent, title):
        lbl = tk.Label(parent, text=title, font=("Arial", 11, "bold"), fg="#34495E")
        lbl.pack(anchor=tk.W, pady=(5,0))
        
        scroll = ttk.Scrollbar(parent)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree = ttk.Treeview(parent, yscrollcommand=scroll.set, show="headings")
        tree.pack(expand=True, fill=tk.BOTH)
        scroll.config(command=tree.yview)
        
        style = ttk.Style()
        style.configure("Treeview.Heading", font=('Arial', 10, 'bold'))
        style.configure("Treeview", font=('Arial', 9))
        
        return tree
        
    def update_tree(self, tree, df):
        tree.delete(*tree.get_children())
        
        if df.empty:
            tree["columns"] = ("Mesaj",)
            tree.heading("Mesaj", text="Veri yok")
            tree.column("Mesaj", width=500, anchor=tk.CENTER)
            return
            
        tree["columns"] = list(df.columns)
        for col in df.columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor=tk.CENTER)
            
        for _, row in df.iterrows():
            tree.insert("", tk.END, values=list(row))
            
    def update_ui(self):
        u = self.universe
        
        # Başlık Güncellemesi
        if not u.season_finished:
            nxt_track = u.tracks[u.current_race_idx].name
            self.race_lbl.config(text=f"Şu anki Durum: {u.current_race_idx} / {len(u.tracks)} Yarış Tamamlandı (Sıradaki: {nxt_track})")
        else:
            self.race_lbl.config(text=f"Şampiyona Tamamlandı ({len(u.tracks)}/{len(u.tracks)})")
            self.btn_next.config(state=tk.DISABLED, text="Sezon Bitti")
        
        # Puan Durumu: Pilotlar
        drv_rows = []
        for d_id, drv in u.drivers.items():
            pts = u.champ.driver_standings.get(d_id, 0)
            drv_rows.append({
                "Pilot": drv.name, 
                "Takım": u.teams[drv.team_id].name, 
                "Puan": pts, 
                "Sezon Başı Beklenti": u.exp_drv.get(d_id, "-")
            })
        df_drv = pd.DataFrame(drv_rows).sort_values("Puan", ascending=False).reset_index(drop=True)
        df_drv.index += 1
        df_drv.insert(0, "Sıra", df_drv.index)
        self.update_tree(self.tree_drv_std, df_drv)
        
        # Puan Durumu: Markalar
        team_rows = []
        for t_id, tm in u.teams.items():
            pts = u.champ.team_standings.get(t_id, 0)
            team_rows.append({
                "Takım": tm.name, 
                "Puan": pts, 
                "Beklenen Sıra": u.exp_team.get(t_id, "-")
            })
        df_tm = pd.DataFrame(team_rows).sort_values("Puan", ascending=False).reset_index(drop=True)
        df_tm.index += 1
        df_tm.insert(0, "Sıra", df_tm.index)
        self.update_tree(self.tree_team_std, df_tm)
        
        # Statlar ve Perkler
        stat_rows = []
        for d_id, drv in u.drivers.items():
            stat_rows.append({
                "Pilot": drv.name,
                "Takım": u.teams[drv.team_id].name,
                "Pace": drv.pace,
                "Consistency": drv.consistency,
                "Att/Def": drv.attack_defense,
                "Tire Mgt": drv.tire_management,
                "Potansiyel": drv.potential,
                "Kazanılan Perkler": ", ".join(drv.perks) if drv.perks else "Yok"
            })
        self.update_tree(self.tree_stats, pd.DataFrame(stat_rows))
        
        # Arge Tesisleri
        fac_rows = []
        for t_id, tm in u.teams.items():
            fac_rows.append({
                "Takım": tm.name,
                "Rüzgar Tüneli Lvl": tm.facilities.get("wind_tunnel", 1),
                "Simülatör Lvl": tm.facilities.get("simulator", 1),
                "Fabrika Lvl": tm.facilities.get("factory", 1),
                "Mevcut İnşaat": f"{tm.active_facility_upgrade} (Kalan: {tm.facility_upgrade_remaining_races} Yarış)" if tm.active_facility_upgrade else "Boşta"
            })
        self.update_tree(self.tree_fac, pd.DataFrame(fac_rows))
        
        # Son Geliştirmeler ve Yarış
        self.update_tree(self.tree_upgrades, pd.DataFrame(u.latest_upgrades))
        self.update_tree(self.tree_race, pd.DataFrame(u.latest_race_result))
        
    def simulate_next_race(self):
        self.universe.simulate_next_race()
        self.update_ui()
        self.notebook.select(self.tab_race)

if __name__ == "__main__":
    app = AdminApp()
    app.mainloop()