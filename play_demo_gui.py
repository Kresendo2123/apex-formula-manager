"""
APEX FORMULA MANAGER — OYNANABİLİR GUI DEMOSU (tkinter)
========================================================
Konsol demosunun (play_demo.py) birebir GUI karşılığı — aynı motor, aynı akış:
  YZ modu -> takım seçimi -> [aero -> sıralama -> strateji+stil -> yarış replay
  -> sonuç -> geliştirme] x24 -> sezon sonu raporu.

Ek bağımlılık yok: tkinter Python ile birlikte gelir.
Çalıştırma: python play_demo_gui.py
"""
import io
import os
import sys
import random
import contextlib
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.game_settings import GameSettings
from engine.qualifying import Qualifying
from engine.race_director import RaceDirector
from engine.race_engine import LapRaceEngine
from engine.championship import Championship
from engine.strategy import plan_strategies, build_strategy_options, apply_choice
from main import load_data, calculate_preseason_expectations
from play_demo import (PTS, DRIVER_STATS, CAR_STATS, FACILITIES, STYLES,
                       WALL_OPTIONS, WALL_RISK_MAP,
                       DRIVER_XP_PER_PRESS, CAR_XP_PER_PRESS,
                       FACILITY_PRESS_COST, FACILITY_DURATION, UPGRADES_PER_RACE,
                       ai_pick_aero, ai_pick_style, ai_pick_card, ai_spend_upgrades,
                       build_replay_lines, pit_report_lines, screen_season_end)

BG = "#16181d"
FG = "#f4f6f8"
ACCENT = "#e10600"     # F1 kırmızısı
HILITE = "#1f3a5f"     # oyuncu satırı vurgusu
SUBTLE = "#cdd3da"     # açıklama metinleri — okunabilirlik için açık ton
PANEL = "#262a31"      # kart/panel zemini


class DemoGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Apex Formula Manager — Demo")
        self.geometry("980x720")
        self.configure(bg=BG)
        self._style()

        # motor + veri
        self.s = GameSettings()
        self.drivers, self.cars, self.teams, self.tracks = load_data()
        # Yarış takvimi her sezon karıştırılır (hep aynı sırayla gitmesin)
        random.shuffle(self.tracks)
        self.director = RaceDirector(self.s)
        self.engine = LapRaceEngine(self.s)
        self.quali = Qualifying(self.s)
        self.champ = Championship()
        self.exp_drivers, self.exp_teams = calculate_preseason_expectations(
            self.drivers, self.cars, self.teams, self.tracks, self.director)
        self.name_of = {d_id: d.name for d_id, d in self.drivers.items()}

        # oyun durumu
        self.dynamic = True
        self.my_team = None
        self.my_ids = []
        self.race_no = 0
        self.history = []
        self.start_snapshot = {
            t_id: {"car": sum(getattr(self.cars[tm.car_id], st) for st, _ in CAR_STATS),
                   "drv": sum(getattr(self.drivers[d], st)
                              for d in (tm.lead_driver_id, tm.second_driver_id)
                              for st, _ in DRIVER_STATS)}
            for t_id, tm in self.teams.items()}

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True, padx=14, pady=12)
        self.screen_mode()

    # ------------------------------------------------------------- altyapı

    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("Treeview", background="#262a31", foreground=FG,
                     fieldbackground="#262a31", rowheight=26, font=("Segoe UI", 11))
        st.configure("Treeview.Heading", background="#2c2f37", foreground=FG,
                     font=("Segoe UI", 11, "bold"))
        # Tk 8.6.9 hatası: Treeview yazı/zemin rengi bazı sürümlerde stilden
        # uygulanmıyor (satırlar siyah görünüyor). Bilinen çözüm: varsayılan
        # durum eşlemesini temizle + her satıra açık tag rengi ver (aşağıda).
        def _fixed(option):
            return [e for e in st.map("Treeview", query_opt=option)
                    if e[:2] != ("!disabled", "!selected")]
        st.map("Treeview", foreground=_fixed("foreground"),
               background=[("selected", "#3a4b66")] + _fixed("background"))
        # Combobox: koyu temada varsayılan SİYAH yazı okunmuyordu — hepsi beyaz
        st.configure("TCombobox", fieldbackground="#262a31", background="#2c2f37",
                     foreground=FG, arrowcolor=FG, selectbackground="#262a31",
                     selectforeground=FG, bordercolor="#3a4b66")
        st.map("TCombobox",
               fieldbackground=[("readonly", "#262a31")],
               foreground=[("readonly", FG)],
               selectbackground=[("readonly", "#262a31")],
               selectforeground=[("readonly", FG)])
        # Combobox açılır listesi (Listbox) renkleri
        self.option_add("*TCombobox*Listbox.background", "#262a31")
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", "#3a4b66")
        self.option_add("*TCombobox*Listbox.selectForeground", FG)
        self.option_add("*TCombobox*Listbox.font", "{Segoe UI} 11")

    def clear(self):
        for w in self.content.winfo_children():
            w.destroy()

    def header(self, text, sub=None):
        tk.Label(self.content, text=text, bg=BG, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Frame(self.content, bg=ACCENT, height=3).pack(fill="x", pady=(2, 8))
        if sub:
            tk.Label(self.content, text=sub, bg=BG, fg=SUBTLE,
                     font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 6))

    def style_rows(self, tv):
        """Tablolara satır bazında AÇIK renk verir (Tk'nin stil hatasına karşı
        garantili yol): zebra deseni + oyuncu satırı vurgusu, hepsi beyaz yazı."""
        tv.tag_configure("row", background="#262a31", foreground=FG)
        tv.tag_configure("row2", background="#2e333c", foreground=FG)
        tv.tag_configure("me", background=HILITE, foreground="#ffffff")

    def big_button(self, parent, text, cmd):
        b = tk.Button(parent, text=text, command=cmd, bg=ACCENT, fg="white",
                      font=("Segoe UI", 11, "bold"), relief="flat",
                      activebackground="#b00500", activeforeground="white",
                      padx=18, pady=7, cursor="hand2")
        return b

    def label(self, parent, text, size=10, color=FG, bold=False, **pack):
        tk.Label(parent, text=text, bg=BG, fg=color,
                 font=("Segoe UI", size, "bold" if bold else "normal"),
                 justify="left").pack(**(pack or {"anchor": "w"}))

    # ------------------------------------------------------------- 1) YZ modu

    def screen_mode(self):
        self.clear()
        self.header("APEX FORMULA MANAGER", "Tek sezonluk menajer demosu — 24 yarış")
        self.label(self.content, "Rakip takımlar nasıl davransın?", 12, bold=True,
                   anchor="w", pady=(16, 8))
        mode = tk.IntVar(value=1)
        for val, title, desc in [
            (1, "DİNAMİK", "Strateji kartı oynar, stil seçer, araç/sürücü geliştirir, tesis"
                           " yatırımı yapar — her zaman en iyi hamleyi değil (varyanslı)."),
            (2, "SABİT", "Sezon boyunca hiçbir şey yapmazlar — saf güç karşılaştırması.")]:
            f = tk.Frame(self.content, bg="#262a31", padx=12, pady=10)
            f.pack(fill="x", pady=4)
            tk.Radiobutton(f, text=title, variable=mode, value=val, bg="#262a31", fg=FG,
                           selectcolor="#16181d", font=("Segoe UI", 11, "bold"),
                           activebackground="#262a31", activeforeground=FG).pack(anchor="w")
            tk.Label(f, text=desc, bg="#262a31", fg=SUBTLE, wraplength=820,
                     font=("Segoe UI", 11), justify="left").pack(anchor="w", padx=24)
        self.big_button(self.content, "Devam →",
                        lambda: self._set_mode(mode.get())).pack(anchor="e", pady=16)

    def _set_mode(self, m):
        self.dynamic = (m == 1)
        self.screen_team()

    # ------------------------------------------------------------- 2) takım seçimi

    def screen_team(self):
        self.clear()
        self.header("TAKIM SEÇİMİ", "Sezon öncesi tahmini sıralamalar (kusursuz sezon simülasyonu)")
        tv = ttk.Treeview(self.content, columns=("tahmin", "takim", "pilotlar", "arac"),
                          show="headings", height=11)
        for c, w, t in [("tahmin", 70, "Tahmin"), ("takim", 160, "Takım"),
                        ("pilotlar", 260, "Pilotlar"), ("arac", 380, "Araç özeti")]:
            tv.heading(c, text=t); tv.column(c, width=w, anchor="w")
        self.style_rows(tv)
        listed = [t_id for t_id, _ in self.exp_teams]
        for pos, t_id in enumerate(listed, 1):
            t = self.teams[t_id]
            d1, d2 = self.drivers[t.lead_driver_id], self.drivers[t.second_driver_id]
            car = self.cars[t.car_id]
            ozet = " ".join(f"{lbl[:3]}{getattr(car, st):.0f}" for st, lbl in CAR_STATS)
            tv.insert("", "end", iid=t_id,
                      values=(f"P{pos}", t.name, f"{d1.name} & {d2.name}", ozet),
                      tags=("row" if pos % 2 else "row2",))
        tv.pack(fill="both", expand=True)

        def secim():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo("Takım seç", "Listeden bir takım seçmelisin.")
                return
            self._set_team(sel[0])
        self.big_button(self.content, "Bu takımı yönet →", secim).pack(anchor="e", pady=12)

    def _set_team(self, t_id):
        self.my_team = t_id
        t = self.teams[t_id]
        self.my_ids = [t.lead_driver_id, t.second_driver_id]
        self.race_no = 0
        self.next_race()

    # ------------------------------------------------------------- yarış hafta sonu

    def next_race(self):
        self.race_no += 1
        if self.race_no > len(self.tracks):
            self.screen_season_end()
            return
        self.track = self.tracks[self.race_no - 1]
        self.num_laps = self.track.num_laps or self.s.DEFAULT_RACE_LAPS
        self.fc = self.engine.make_forecast(self.track, self.num_laps)
        self.conditions = self.engine.roll_race_conditions()
        self.screen_aero()

    # --- 3a) aero ---

    def screen_aero(self):
        self.clear()
        t = self.track
        self.header(f"YARIŞ {self.race_no}/{len(self.tracks)} — {t.name}",
                    f"{self.num_laps} tur")
        # Mühendis önerisi (ideal kademe) oyuncuya GÖSTERİLMEZ — pist karakterini
        # okuyup doğru kanadı bulmak oyuncunun işi (öğrenilebilir derinlik).
        ideal = RaceDirector.ideal_aero(t, self.s)
        if ideal <= 2.2: karakter = "DÜZLÜK ağırlıklı — uzun düzlükler, az viraj"
        elif ideal >= 3.8: karakter = "VİRAJ ağırlıklı — yavaş/teknik bölümler çok"
        else: karakter = "DENGELİ pist"
        info = tk.Frame(self.content, bg="#262a31", padx=14, pady=10)
        info.pack(fill="x", pady=6)
        for txt in (f"Pist karakteri: {karakter}",
                    f"Hava tahmini: {self.fc['label']}"):
            tk.Label(info, text=txt, bg="#262a31", fg=FG,
                     font=("Segoe UI", 11)).pack(anchor="w", pady=1)

        self.label(self.content, "\nARAÇ AYARI — düz hız ile yol tutuşu arasındaki denge. "
                                 "Sıralamayı VE yarışı etkiler; piste uymayan ayar lastiği de yer.",
                   12, bold=True)
        self.aero_var = tk.IntVar(value=3)
        row = tk.Frame(self.content, bg=BG); row.pack(pady=10)
        for lvl, lbl in [(1, "1\nMAKS HIZ\n(basık araç)"), (2, "2\nhız\nağırlıklı"),
                         (3, "3\ndengeli"), (4, "4\ntutuş\nağırlıklı"),
                         (5, "5\nMAKS TUTUŞ\n(viraj canavarı)")]:
            tk.Radiobutton(row, text=lbl, variable=self.aero_var, value=lvl,
                           indicatoron=0, width=13, height=3, bg="#262a31", fg=FG,
                           selectcolor=ACCENT, font=("Segoe UI", 11),
                           activebackground="#2c2f37", activeforeground=FG,
                           cursor="hand2").pack(side="left", padx=4)
        self.big_button(self.content, "Sıralama turlarına git →",
                        self.run_quali).pack(anchor="e", pady=14)

    def run_quali(self):
        self.my_aero = self.aero_var.get()
        self.aero_lv = {}
        for d_id, dr in self.drivers.items():
            self.aero_lv[d_id] = (self.my_aero if dr.team_id == self.my_team
                                  else ai_pick_aero(self.s, self.track, self.dynamic))
        self.form = {d: random.gauss(0, self.s.RACE_FORM_SIGMA) for d in self.drivers}
        is_q_rain = random.random() < self.track.weather_volatility
        self.grid, self.q3 = self.quali.simulate_qualifying(
            self.drivers, self.cars, self.teams, self.track, is_q_rain,
            form=self.form, aero_levels=self.aero_lv)
        self.screen_quali(is_q_rain)

    # --- 3b) sıralama sonucu ---

    def screen_quali(self, is_rain):
        self.clear()
        self.header(f"SIRALAMA SONUÇLARI — {self.track.name}"
                    + ("  [💧 ıslak]" if is_rain else ""))
        # Buton ve özet ÖNCE alta sabitlenir; tablo kalan alanı doldurur
        # (aksi halde 22 satırlık tablo butonu pencere dışına itiyordu).
        self.big_button(self.content, "Strateji ekranına →",
                        self.screen_strategy).pack(side="bottom", anchor="e", pady=8)
        my_pos = [self.grid.index(d) + 1 for d in self.my_ids]
        self.label(self.content, f"Pilotların: P{my_pos[0]} ve P{my_pos[1]}",
                   12, bold=True, side="bottom", anchor="w", pady=4)
        tv = ttk.Treeview(self.content, columns=("pos", "pilot", "takim"),
                          show="headings")
        for c, w, t in [("pos", 60, "Grid"), ("pilot", 220, "Pilot"), ("takim", 220, "Takım")]:
            tv.heading(c, text=t); tv.column(c, width=w, anchor="w")
        self.style_rows(tv)
        for pos, d_id in enumerate(self.grid, 1):
            d = self.drivers[d_id]
            tag = "me" if d_id in self.my_ids else ("row" if pos % 2 else "row2")
            tv.insert("", "end", values=(f"P{pos}", d.name, self.teams[d.team_id].name),
                      tags=(tag,))
        sb = ttk.Scrollbar(self.content, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)

    # --- 3c) strateji + stil ---

    def screen_strategy(self):
        self.clear()
        self.header("YARIŞ ÖNCESİ STRATEJİ",
                    "Pilot başına ayrı pit kartı ve sürüş stili seçebilirsin")
        # Hava tahmini (yağmurun beklendiği TUR dahil) strateji kararının girdisidir
        self.label(self.content, f"🌦 Hava tahmini: {self.fc['label']}",
                   12, "#7ec8ff", True, anchor="w", pady=(0, 4))
        if self.conditions["wear_day_mult"] > 1.05:
            self.label(self.content, "☀️ Pist bugün SICAK — aşınma normalden yüksek!",
                       11, "#ffb44c", True)
        elif self.conditions["wear_day_mult"] < 0.95:
            self.label(self.content, "🌥️ Pist bugün SERİN — lastikler uzun dayanır.",
                       11, "#7ec8ff", True)

        # Kartlar PİSTE ÖZEL üretilir; etikette tahmini süre farkı var (yayın grafiği gibi)
        self.options = build_strategy_options(self.fc, self.num_laps, self.s, track=self.track)
        card_labels = [o["label"] for o in self.options]
        style_labels = [f"{n} — {d}" for _, n, d in STYLES]

        def plan_txt(o):
            stints = "  ".join(f"{st['compound'][:1].upper()}{st['laps']}" for st in o["plan"])
            return f"Plan: {stints}   [risk: {o['risk']}]\n{o['desc']}"

        self.choice_vars = {}
        for d_id in self.my_ids:
            lf = tk.LabelFrame(self.content, text=f"  {self.name_of[d_id]}  ",
                               bg=PANEL, fg=FG, font=("Segoe UI", 12, "bold"),
                               padx=10, pady=8)
            lf.pack(fill="x", pady=6)
            cv = tk.StringVar(value=card_labels[0])
            sv = tk.StringVar(value=style_labels[0])
            tk.Label(lf, text="Pit stratejisi:", bg=PANEL, fg=FG,
                     font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w", pady=2)
            cb = ttk.Combobox(lf, textvariable=cv, values=card_labels,
                              state="readonly", width=58, font=("Segoe UI", 11))
            cb.grid(row=0, column=1, sticky="w", padx=8)
            desc = tk.Label(lf, text=plan_txt(self.options[0]), bg=PANEL, fg=SUBTLE,
                            wraplength=780, justify="left", font=("Segoe UI", 11))
            desc.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 4))

            def upd(_e, v=cv, lab=desc):
                o = next(o for o in self.options if o["label"] == v.get())
                lab.config(text=plan_txt(o))
            cb.bind("<<ComboboxSelected>>", upd)
            tk.Label(lf, text="Sürüş stili:", bg=PANEL, fg=FG,
                     font=("Segoe UI", 11)).grid(row=2, column=0, sticky="w", pady=2)
            ttk.Combobox(lf, textvariable=sv, values=style_labels, state="readonly",
                         width=58, font=("Segoe UI", 11)).grid(row=2, column=1,
                                                               sticky="w", padx=8)
            # Pit duvarı talimatı: yarış içi dinamik kararların (SC fırsatı,
            # pencere esnetme, yağmur kumarı) risk iştahı. "Karttan" = kartın
            # kendi risk etiketi kullanılır.
            wv = tk.StringVar(value=WALL_OPTIONS[0])
            tk.Label(lf, text="Pit duvarı talimatı:", bg=PANEL, fg=FG,
                     font=("Segoe UI", 11)).grid(row=3, column=0, sticky="w", pady=2)
            ttk.Combobox(lf, textvariable=wv, values=WALL_OPTIONS, state="readonly",
                         width=58, font=("Segoe UI", 11)).grid(row=3, column=1,
                                                               sticky="w", padx=8)
            self.choice_vars[d_id] = (cv, sv, wv)
        self.big_button(self.content, "🏁 YARIŞI BAŞLAT",
                        self.run_race).pack(side="bottom", anchor="e", pady=10)

    def run_race(self):
        strat = plan_strategies(self.grid, self.fc, self.num_laps, self.s, track=self.track)
        styles = {}
        self.my_choices = {}
        for d_id, dr in self.drivers.items():
            if dr.team_id == self.my_team:
                cv, sv, wv = self.choice_vars[d_id]
                card = next(o for o in self.options if o["label"] == cv.get())
                style_id = STYLES[[f"{n} — {d}" for _, n, d in STYLES].index(sv.get())][0]
                apply_choice(strat, d_id, card)
                # Pit duvarı talimatı kartın risk etiketini ezebilir
                wall_risk = WALL_RISK_MAP.get(wv.get())
                if wall_risk is not None:
                    strat[d_id]["risk"] = wall_risk
                styles[d_id] = style_id
                self.my_choices[d_id] = (card, style_id)
            else:
                card = ai_pick_card(self.options, self.dynamic)
                if card is not None:
                    apply_choice(strat, d_id, card)
                styles[d_id] = ai_pick_style(self.dynamic)

        profiles = {d: self.director.build_profile(
            dr, self.cars[self.teams[dr.team_id].car_id], self.track,
            self.aero_lv[d], styles[d], False)
            for d, dr in self.drivers.items()}
        self.res = self.engine.simulate_race(
            self.grid, profiles, self.track, form=self.form, strategies=strat,
            forecast=self.fc, conditions=self.conditions)
        self.screen_replay()

    # --- 3d) yarış replay ---

    def screen_replay(self):
        self.clear()
        self.header(f"YARIŞ — {self.track.name}",
                    "Pilotlarının olaylı turları (▶) + global olaylar (🌐) + pozisyon raporu (📊)")
        self.big_button(self.content, "Yarış sonucu →",
                        self.screen_result).pack(side="bottom", anchor="e", pady=8)
        txt = ScrolledText(self.content, bg="#101216", fg=FG, font=("Consolas", 11),
                           relief="flat", wrap="word")
        txt.pack(fill="both", expand=True, pady=4)
        txt.tag_configure("global", foreground="#7ec8ff")
        txt.tag_configure("mine", foreground="#ffd166")
        txt.tag_configure("pit", foreground="#6ee7a8")   # pilotlarının pitleri yeşil
        txt.tag_configure("wall", foreground="#c89bff")  # pit duvarı kararları mor
        txt.tag_configure("pos", foreground=SUBTLE)
        lines = build_replay_lines(self.res, self.my_ids, self.name_of, self.num_laps)
        if not lines:
            txt.insert("end", "(Sakin bir yarış — kayda değer olay yok)\n")
        for _, kind, line in lines:
            txt.insert("end", line + "\n", kind)
        txt.config(state="disabled")

    # --- 3e) sonuç + puan durumu ---

    def screen_result(self):
        self.clear()
        self.header(f"YARIŞ SONUCU — {self.track.name}")
        tv = ttk.Treeview(self.content, columns=("pos", "pilot", "takim", "puan"),
                          show="headings")
        for c, w, t in [("pos", 70, "Sıra"), ("pilot", 200, "Pilot"),
                        ("takim", 200, "Takım"), ("puan", 120, "Puan / Durum")]:
            tv.heading(c, text=t); tv.column(c, width=w, anchor="w")
        self.style_rows(tv)
        my_points = 0
        for i, row in enumerate(self.res["classification"], 1):
            d_id = row["driver_id"]
            pts = PTS.get(row.get("position"), 0)
            if row["status"] == "FIN":
                vals = (f"P{row['position']}", self.name_of[d_id],
                        self.teams[row["team_id"]].name, f"+{pts}" if pts else "")
            else:
                detay = row.get("dnf_detail") or row.get("dnf_cause") or "?"
                vals = ("DNF", self.name_of[d_id],
                        self.teams[row["team_id"]].name, detay)
            tag = "me" if d_id in self.my_ids else ("row" if i % 2 else "row2")
            tv.insert("", "end", values=vals, tags=(tag,))
            if d_id in self.my_ids:
                my_points += pts
        self.champ.process_race_result(self.res["classification"])

        # geçmişe yaz
        fin_txt, grid_txt = [], []
        for d_id in self.my_ids:
            row = next(c for c in self.res["classification"] if c["driver_id"] == d_id)
            fin_txt.append(f"P{row['position']}" if row["status"] == "FIN" else "DNF")
            grid_txt.append(f"P{self.grid.index(d_id) + 1}")
        self.history.append({
            "track": self.track.name, "grid": "/".join(grid_txt),
            "finish": "/".join(fin_txt), "pts": my_points,
            "secim": f"aero{self.my_aero}, " + "+".join(
                f"{self.my_choices[d][0]['id'][:9]}|{self.my_choices[d][1][:6]}"
                for d in self.my_ids)})

        # Buton + özet alta sabit, tablo kalan alanı doldurur (taşma olmasın)
        order = sorted(self.teams, key=lambda t: -self.champ.team_standings.get(t, 0))
        my_rank = order.index(self.my_team) + 1
        nxt = ("Geliştirme ekranına →" if self.race_no < len(self.tracks)
               else "Sezon sonu raporu →")
        self.big_button(self.content, nxt,
                        self.screen_upgrade if self.race_no < len(self.tracks)
                        else self.screen_season_end).pack(side="bottom", anchor="e", pady=6)
        self.label(self.content,
                   f"Bu yarıştan {my_points} puan  |  Markalar şampiyonasında P{my_rank} "
                   f"({self.champ.team_standings.get(self.my_team, 0)} puan)",
                   12, bold=True, side="bottom", anchor="w", pady=6)
        # PİT RAPORU: pilot başına planlanan strateji vs gerçekleşen stintler
        # (tur aralıkları + her pitin sebebi: plan / hava / SC / VSC / kırmızı)
        rapor = tk.Frame(self.content, bg="#262a31", padx=10, pady=6)
        rapor.pack(side="bottom", fill="x", pady=(4, 2))
        tk.Label(rapor, text="PİT RAPORU — plan vs gerçekleşen", bg="#262a31",
                 fg="#6ee7a8", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        for line in pit_report_lines(self.res, self.my_ids, self.my_choices, self.name_of):
            tk.Label(rapor, text=line, bg="#262a31", fg=FG,
                     font=("Consolas", 11)).pack(anchor="w")
        sb = ttk.Scrollbar(self.content, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)

    # --- 3f) geliştirme ---

    def screen_upgrade(self):
        self.clear()
        t = self.teams[self.my_team]
        car = self.cars[t.car_id]
        d1, d2 = self.drivers[self.my_ids[0]], self.drivers[self.my_ids[1]]
        self.header(f"GELİŞTİRME — yarış {self.race_no} sonrası",
                    f"{UPGRADES_PER_RACE} hakkın var — tesis geliştirmesi BEDAVA (hak yemez)")
        self.presses = tk.IntVar(value=UPGRADES_PER_RACE)
        top = tk.Frame(self.content, bg=BG); top.pack(fill="x")
        tk.Label(top, textvariable=self.presses, bg=BG, fg=ACCENT,
                 font=("Segoe UI", 22, "bold")).pack(side="left")
        tk.Label(top, text=" hak kaldı", bg=BG, fg=FG,
                 font=("Segoe UI", 12)).pack(side="left")

        self.big_button(self.content, "Sonraki yarışa →",
                        self.finish_upgrades).pack(side="bottom", anchor="e", pady=8)
        body = tk.Frame(self.content, bg=BG); body.pack(fill="both", expand=True, pady=6)
        self._upg_section(body, d1.name, d1, DRIVER_STATS, "driver", 0)
        self._upg_section(body, d2.name, d2, DRIVER_STATS, "driver", 1)
        self._upg_section(body, "ARAÇ", car, CAR_STATS, "car", 2)
        self._facility_section(body, t, 3)

    @staticmethod
    def _stat_text(obj, st, lbl):
        """Stat + sonraki seviyeye ilerleme yüzdesi: 'Hız 85 (%42)'"""
        req = obj.get_required_xp_for_stat(st)
        pct = getattr(obj, f"{st}_xp") / max(1, req) * 100
        return f"{lbl} {getattr(obj, st):.0f}  (%{pct:.0f})"

    def _upg_section(self, parent, title, obj, stats, kind, col):
        t = self.teams[self.my_team]
        lf = tk.LabelFrame(parent, text=f" {title} ", bg="#262a31", fg=FG,
                           font=("Segoe UI", 10, "bold"), padx=8, pady=6)
        lf.grid(row=0, column=col, sticky="nsew", padx=4)
        parent.grid_columnconfigure(col, weight=1)
        for st, lbl in stats:
            row = tk.Frame(lf, bg="#262a31"); row.pack(fill="x", pady=2)
            val = tk.Label(row, text=self._stat_text(obj, st, lbl),
                           bg="#262a31", fg=FG, width=20, anchor="w",
                           font=("Segoe UI", 10))
            val.pack(side="left")

            def press(o=obj, s_=st, k=kind, v=val, l=lbl):
                if self.presses.get() <= 0:
                    return
                if k == "driver":
                    mult = t.get_facility_multiplier("simulator")
                    o.add_xp_to_stat(s_, int(DRIVER_XP_PER_PRESS * mult))
                else:
                    mult = t.get_facility_multiplier(
                        "wind_tunnel" if s_ in ("grip", "acceleration") else "factory")
                    o.add_xp_to_stat(s_, int(CAR_XP_PER_PRESS * mult))
                self.presses.set(self.presses.get() - 1)
                v.config(text=self._stat_text(o, s_, l))
            tk.Button(row, text="Geliştir", command=press, bg="#3a4b66", fg=FG,
                      relief="flat", cursor="hand2", padx=6).pack(side="right")

    def _facility_section(self, parent, t, col):
        lf = tk.LabelFrame(parent, text=" TESİSLER ", bg="#262a31", fg=FG,
                           font=("Segoe UI", 10, "bold"), padx=8, pady=6)
        lf.grid(row=0, column=col, sticky="nsew", padx=4)
        if t.active_facility_upgrade:
            tk.Label(lf, text=f"Devam eden: {t.active_facility_upgrade}\n"
                              f"({t.facility_upgrade_remaining_races} yarış kaldı)",
                     bg="#262a31", fg="#ffb44c", justify="left").pack(anchor="w")
            return
        for f, n, desc in FACILITIES:
            row = tk.Frame(lf, bg="#262a31"); row.pack(fill="x", pady=2)
            lv = t.facilities.get(f, 1)
            tk.Label(row, text=f"{n} sv{lv}", bg="#262a31", fg=FG,
                     width=15, anchor="w").pack(side="left")
            if lv < 3:
                def start(f_=f, n_=n):
                    t.start_facility_upgrade(f_, FACILITY_DURATION)
                    messagebox.showinfo("Başladı",
                                        f"{n_} geliştirmesi başladı ({FACILITY_DURATION} yarış)."
                                        " Hak harcanmadı — tesisler bedava.")
                    self.screen_upgrade_refresh_facilities(lf, t)
                tk.Button(row, text="Başlat (bedava)", command=start,
                          bg="#3a4b66", fg=FG, relief="flat", cursor="hand2",
                          padx=6).pack(side="right")
            else:
                tk.Label(row, text="MAX", bg="#262a31", fg=SUBTLE).pack(side="right")

    def screen_upgrade_refresh_facilities(self, lf, t):
        for w in lf.winfo_children():
            w.destroy()
        tk.Label(lf, text=f"Devam eden: {t.active_facility_upgrade}\n"
                          f"({t.facility_upgrade_remaining_races} yarış kaldı)",
                 bg="#262a31", fg="#ffb44c", justify="left").pack(anchor="w")

    def finish_upgrades(self):
        # YZ geliştirmeleri + tesis ilerlemeleri (konsol sürümüyle aynı mantık)
        ai_logs = []
        for t_id, team in self.teams.items():
            if t_id == self.my_team:
                continue
            ai_spend_upgrades(team, self.cars[team.car_id],
                              self.drivers[team.lead_driver_id],
                              self.drivers[team.second_driver_id],
                              self.dynamic, ai_logs)
        for t_id, team in self.teams.items():
            was = team.active_facility_upgrade
            team.process_facility_upgrade()
            if t_id == self.my_team and was and team.active_facility_upgrade is None:
                fname = dict((f, n) for f, n, _ in FACILITIES)[was]
                messagebox.showinfo("Tesis hazır! 🏗️",
                                    f"{fname} geliştirmesi tamamlandı — yeni seviye: "
                                    f"{team.facilities[was]}")
        self.next_race()

    # ------------------------------------------------------------- 4) sezon sonu

    def screen_season_end(self):
        self.clear()
        self.header("SEZON SONU RAPORU")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            screen_season_end(self.my_team, self.teams, self.drivers, self.cars,
                              self.champ, self.history, self.exp_drivers,
                              self.exp_teams, self.start_snapshot, self.dynamic)
        self.big_button(self.content, "Demoyu kapat",
                        self.destroy).pack(side="bottom", anchor="e", pady=8)
        txt = ScrolledText(self.content, bg="#101216", fg=FG, font=("Consolas", 11),
                           relief="flat", wrap="none")
        txt.pack(fill="both", expand=True, pady=4)
        txt.insert("end", buf.getvalue())
        txt.config(state="disabled")


if __name__ == "__main__":
    DemoGUI().mainloop()
