import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pprint
import os
import sys

# Üst dizini sys.path'e ekle ki ana modüllerden import yapılabilsin
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.seed_data import SEED_TEAMS, SEED_DRIVERS, SEED_CARS, SEED_TRACKS

class DataEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Apex Formula Manager - Veri Düzenleyici (Seed Data)")
        self.geometry("1000x600")
        
        # Orijinal verileri yükle
        self.teams = SEED_TEAMS.copy()
        self.drivers = SEED_DRIVERS.copy()
        self.cars = SEED_CARS.copy()
        self.tracks = SEED_TRACKS.copy()
        
        self.build_ui()
        self.refresh_trees()
        
    def build_ui(self):
        top_frame = tk.Frame(self, bg="#8E44AD")
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        lbl = tk.Label(top_frame, text="Veritabanı Düzenleyici (Düzenlemek için çift tıklayın)", font=("Arial", 14, "bold"), bg="#8E44AD", fg="white")
        lbl.pack(side=tk.LEFT, padx=15, pady=10)
        
        btn_save = tk.Button(top_frame, text="Değişiklikleri Kaydet (seed_data.py)", font=("Arial", 11, "bold"), bg="#27AE60", fg="white", command=self.save_to_file)
        btn_save.pack(side=tk.RIGHT, padx=15, pady=10)
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        self.tab_drivers = ttk.Frame(self.notebook)
        self.tab_cars = ttk.Frame(self.notebook)
        self.tab_tracks = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_drivers, text="🏎️ Pilotlar")
        self.notebook.add(self.tab_cars, text="🚗 Araçlar")
        self.notebook.add(self.tab_tracks, text="🛣️ Pistler")
        
        self.tree_drv = self.create_tree(self.tab_drivers, ["id", "team_id", "name", "pace", "consistency", "attack_defense", "tire_management", "potential"], self.on_double_click_driver)
        self.tree_car = self.create_tree(self.tab_cars, ["id", "team_id", "acceleration", "top_speed", "grip", "reliability", "tire_consumption"], self.on_double_click_car)
        self.tree_trk = self.create_tree(self.tab_tracks, ["id", "name", "req_top_speed", "req_acceleration", "req_grip", "req_driver_skill", "weather_volatility", "num_laps"], self.on_double_click_track)
        
    def create_tree(self, parent, columns, double_click_cb):
        scroll = ttk.Scrollbar(parent)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree = ttk.Treeview(parent, columns=columns, show="headings", yscrollcommand=scroll.set)
        tree.pack(expand=True, fill=tk.BOTH)
        scroll.config(command=tree.yview)
        
        for col in columns:
            tree.heading(col, text=col.upper())
            tree.column(col, width=100, anchor=tk.CENTER)
            
        tree.bind("<Double-1>", double_click_cb)
        return tree
        
    def refresh_trees(self):
        for t in [self.tree_drv, self.tree_car, self.tree_trk]:
            t.delete(*t.get_children())
            
        for idx, drv in enumerate(self.drivers):
            self.tree_drv.insert("", tk.END, iid=f"drv_{idx}", values=list(drv.values()))
            
        for idx, car in enumerate(self.cars):
            self.tree_car.insert("", tk.END, iid=f"car_{idx}", values=list(car.values()))
            
        for idx, trk in enumerate(self.tracks):
            self.tree_trk.insert("", tk.END, iid=f"trk_{idx}", values=list(trk.values()))

    def edit_item(self, tree, item_id, item_dict, list_ref):
        # Tree üzerinde çift tıklanan öğeyi bulur ve popup form açar.
        col_names = tree["columns"]
        vals = tree.item(item_id, "values")
        
        edit_win = tk.Toplevel(self)
        edit_win.title("Düzenle")
        edit_win.geometry("300x400")
        
        entries = {}
        for i, col in enumerate(col_names):
            tk.Label(edit_win, text=col).pack(pady=(5,0))
            ent = tk.Entry(edit_win)
            ent.insert(0, str(vals[i]))
            ent.pack()
            if col == "id" or col == "team_id":
                ent.config(state="readonly") # ID'leri bozdurmamak için
            entries[col] = ent
            
        def on_save():
            try:
                for col in col_names:
                    if col in ["id", "team_id", "name"]:
                        item_dict[col] = entries[col].get()
                    elif col in ["req_top_speed", "req_acceleration", "req_grip", "req_driver_skill", "weather_volatility"]:
                        item_dict[col] = float(entries[col].get())
                    else:
                        item_dict[col] = int(entries[col].get())
                
                # Listeyi güncelle ve arayüzü yenile
                idx = int(item_id.split("_")[1])
                list_ref[idx] = item_dict
                self.refresh_trees()
                edit_win.destroy()
            except ValueError:
                messagebox.showerror("Hata", "Lütfen sayısal alanlara sadece sayı giriniz!")
                
        tk.Button(edit_win, text="Değiştir", command=on_save, bg="#2980B9", fg="white").pack(pady=15)
            
    def on_double_click_driver(self, event):
        item_id = self.tree_drv.selection()[0]
        idx = int(item_id.split("_")[1])
        self.edit_item(self.tree_drv, item_id, self.drivers[idx].copy(), self.drivers)

    def on_double_click_car(self, event):
        item_id = self.tree_car.selection()[0]
        idx = int(item_id.split("_")[1])
        self.edit_item(self.tree_car, item_id, self.cars[idx].copy(), self.cars)

    def on_double_click_track(self, event):
        item_id = self.tree_trk.selection()[0]
        idx = int(item_id.split("_")[1])
        self.edit_item(self.tree_trk, item_id, self.tracks[idx].copy(), self.tracks)

    def save_to_file(self):
        # Kaydedilecek dizini kök dizindeki data/ içine ayarla
        filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', "data", "seed_data.py"))
        
        # Pprint kullanarak sözlükleri güzel görünümlü koda çeviriyoruz
        teams_str = pprint.pformat(self.teams, sort_dicts=False, width=150)
        drivers_str = pprint.pformat(self.drivers, sort_dicts=False, width=150)
        cars_str = pprint.pformat(self.cars, sort_dicts=False, width=150)
        tracks_str = pprint.pformat(self.tracks, sort_dicts=False, width=150)
        
        content = f"""# data/seed_data.py

SEED_TEAMS = {teams_str}

SEED_DRIVERS = {drivers_str}

SEED_CARS = {cars_str}

# Dinamik motoru test etmek için 24 farklı karakteristiğe sahip pist. Gerçekçi tur (num_laps) eklendi.
SEED_TRACKS = {tracks_str}
"""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Başarılı", f"Veriler başarıyla kaydedildi:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydederken hata oluştu: {str(e)}")


if __name__ == "__main__":
    app = DataEditorApp()
    app.mainloop()