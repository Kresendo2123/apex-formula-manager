import tkinter as tk
from tkinter import ttk, messagebox
import pprint
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.game_settings import GameSettings

class SettingsEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Apex Formula Manager - Oyun Ayarları (Game Settings) Düzenleyici")
        self.geometry("900x700")
        
        self.settings_instance = GameSettings()
        # Class özelliklerini (büyük harfle başlayanları) çek
        self.settings_dict = {}
        for attr in dir(GameSettings):
            if not attr.startswith("__") and attr.isupper() and not callable(getattr(GameSettings, attr)):
                self.settings_dict[attr] = getattr(GameSettings, attr)
                
        self.build_ui()
        self.refresh_tree()
        
    def build_ui(self):
        top_frame = tk.Frame(self, bg="#E67E22")
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        lbl = tk.Label(top_frame, text="GameSettings.py Düzenleyici (Düzenlemek için çift tıklayın)", font=("Arial", 14, "bold"), bg="#E67E22", fg="white")
        lbl.pack(side=tk.LEFT, padx=15, pady=10)
        
        btn_save = tk.Button(top_frame, text="Değişiklikleri Kaydet", font=("Arial", 11, "bold"), bg="#2C3E50", fg="white", command=self.save_to_file)
        btn_save.pack(side=tk.RIGHT, padx=15, pady=10)
        
        main_frame = tk.Frame(self)
        main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        scroll = ttk.Scrollbar(main_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree = ttk.Treeview(main_frame, columns=("Ayar İsmi", "Değeri (Türü)"), show="headings", yscrollcommand=scroll.set)
        self.tree.heading("Ayar İsmi", text="Ayar İsmi")
        self.tree.heading("Değeri (Türü)", text="Değeri (Türü)")
        self.tree.column("Ayar İsmi", width=300, anchor=tk.W)
        self.tree.column("Değeri (Türü)", width=500, anchor=tk.W)
        
        self.tree.pack(expand=True, fill=tk.BOTH)
        scroll.config(command=self.tree.yview)
        
        self.tree.bind("<Double-1>", self.on_double_click)
        
    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for key, val in self.settings_dict.items():
            val_str = pprint.pformat(val, width=100)
            # Eğer string çok uzunsa kırp
            if len(val_str) > 80:
                val_str = val_str[:77] + "..."
            self.tree.insert("", tk.END, iid=key, values=(key, f"{val_str} ({type(val).__name__})"))

    def on_double_click(self, event):
        item_id = self.tree.selection()[0]
        current_val = self.settings_dict[item_id]
        val_type = type(current_val)
        
        # Liste ve Dictionary düzenleme basit popup ile çok zor olduğundan uyarı verelim
        if val_type in [list, dict]:
            messagebox.showwarning("Desteklenmiyor", "Liste (list) veya Sözlük (dict) tipindeki ayarları şimdilik bu arayüzden düzenleyemezsiniz. Lütfen doğrudan game_settings.py dosyasını kullanın.")
            return
            
        edit_win = tk.Toplevel(self)
        edit_win.title(f"Ayar Düzenle: {item_id}")
        edit_win.geometry("400x150")
        
        tk.Label(edit_win, text=f"{item_id} (Mevcut Tip: {val_type.__name__})", font=("Arial", 11, "bold")).pack(pady=10)
        ent = tk.Entry(edit_win, width=40)
        ent.insert(0, str(current_val))
        ent.pack()
        
        def on_save():
            try:
                new_val_str = ent.get()
                if val_type == int:
                    new_val = int(new_val_str)
                elif val_type == float:
                    new_val = float(new_val_str)
                elif val_type == str:
                    new_val = str(new_val_str)
                elif val_type == bool:
                    new_val = new_val_str.lower() in ['true', '1', 't', 'y', 'yes']
                else:
                    new_val = new_val_str
                    
                self.settings_dict[item_id] = new_val
                self.refresh_tree()
                edit_win.destroy()
            except ValueError:
                messagebox.showerror("Hata", f"Lütfen geçerli bir {val_type.__name__} değeri girin!")
                
        tk.Button(edit_win, text="Kaydet", command=on_save, bg="#27AE60", fg="white").pack(pady=15)

    def save_to_file(self):
        filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', "config", "game_settings.py"))
        
        # Dosyayı okuyup regex ile veya satır satır değiştirmek yerine, 
        # class yapısını tamamen yeniden yazan bir format üretiyoruz
        # Liste ve Dict olan değişkenleri olduğu gibi formatla
        
        lines = []
        lines.append("class GameSettings:")
        
        for key, val in self.settings_dict.items():
            formatted_val = pprint.pformat(val, sort_dicts=False, width=120)
            # İndentasyon ekle
            formatted_val = formatted_val.replace('\n', '\n    ')
            lines.append(f"    {key} = {formatted_val}")
            lines.append("") # Boşluk
            
        lines.append("""
    @classmethod
    def calculate_required_xp(cls, current_level: int) -> int:
        return int(cls.XP_BASE_COST * (cls.XP_GROWTH_FACTOR ** current_level))
""")
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("Başarılı", f"Ayarlar başarıyla kaydedildi:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydederken hata oluştu: {str(e)}")

if __name__ == "__main__":
    app = SettingsEditorApp()
    app.mainloop()