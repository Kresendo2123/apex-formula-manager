"""
APEX FORMULA MANAGER — ÇOK OYUNCULU TERMİNAL İSTEMCİSİ (Faz 1 test aracı)
==========================================================================
Sunucuya bağlanır; oda kur / kodla katıl, takım seç, sezonu oyna.
Unity istemcisi gelene kadar multiplayer'ı uçtan uca test etmenin yolu —
aynı zamanda Unity'nin konuşacağı protokolün çalışan referansı.

Kullanım:
    1. terminal:  uvicorn server.app:app
    2. terminal:  python play_online.py --name Ayşe
    3. terminal:  python play_online.py --name Bora     (koda katıl)

Aynı ağdaki başka makineden: python play_online.py --url ws://<ip>:8000/ws
Not: Karar fazlarında süre sayacı vardır (oda kurarken seçilir). Süre dolarsa
sunucu senin yerine makul varsayılanı oynar; oyun asla kilitlenmez.
"""
import os
import sys
import json
import time
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from websockets.sync.client import connect
from play_demo import build_replay_lines   # replay görselleştirme (aynı motor çıktısı)

PTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
STYLE_LABELS = {"normal": "Normal (dengeli)",
                "aggressive": "Agresif (tempo+atak; lastik/kaza riski)",
                "long_stint": "Lastik Koruma (temiz havada altın; trafikte ceza)"}
WALL_LABELS = [("kart", "Karttan (önerilen)"), ("düşük", "Güvenli"),
               ("orta", "Dengeli"), ("yüksek", "Cesur")]
STAT_TR = {"pace": "Hız", "consistency": "İstikrar", "attack_defense": "Atak/Savunma",
           "tire_management": "Lastik Yön.", "acceleration": "Hızlanma",
           "top_speed": "Son Sürat", "grip": "Yol Tutuş",
           "reliability": "Güvenilirlik", "tire_consumption": "Lastik Verimi"}


def ask_int(prompt, lo, hi, default=None):
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            v = int(raw)
            if lo <= v <= hi:
                return v
        except ValueError:
            pass
        print(f"  ({lo}-{hi} arası bir sayı gir)")


def hr(title=""):
    print("\n" + "=" * 66)
    if title:
        print(f" {title}")
        print("=" * 66)


class Client:
    def __init__(self, url, name):
        self.url, self.name = url, name
        self.ws = None
        self.room = None
        self.my_team = None
        self.static = None          # static_data: takım/pilot isimleri vs.
        self.name_of = {}
        self.my_drivers = []
        self.last_phase = None
        self.num_laps = 0

    # ------------------------------------------------------------- iletişim

    def send(self, **msg):
        self.ws.send(json.dumps(msg))

    def recv(self):
        return json.loads(self.ws.recv())

    def recv_until(self, *evs):
        """İstenen mesaj gelene dek okur; aradaki bilgi mesajlarını basar."""
        while True:
            m = self.recv()
            ev = m.get("ev")
            if ev in evs:
                return m
            if ev == "error":
                print(f"  ⚠️  sunucu: {m.get('msg')} [{m.get('code')}]")
                if "hata_da_don" in evs:
                    return m
            elif ev == "room":
                self.room = m
                self.print_room()
            elif ev == "player_submitted":
                t = self.team_name(m.get("team_id"))
                print(f"  ✔ {t} seçimini gönderdi ({m.get('phase')})")
            elif ev == "auto_filled":
                names = ", ".join(self.team_name(t) for t in m.get("teams", []))
                print(f"  ⏱ Süre doldu — otomatik seçim: {names}")

    # ------------------------------------------------------------- yardımcılar

    def team_name(self, t_id):
        if self.static and t_id in self.static["teams"]:
            return self.static["teams"][t_id]["name"]
        return t_id or "?"

    def print_room(self):
        r = self.room
        if not r:
            return
        slots = ", ".join(
            f"{p['name']}{'(host)' if p['name'] == r.get('host') else ''}"
            f"[{p['team_id'] or '—'}{' ✔' if p['ready'] else ''}]"
            for p in r["players"])
        print(f"  ODA {r['code']} | tur süresi {r['turn_seconds']}s | {slots}")

    # ------------------------------------------------------------- lobi

    def lobby(self):
        hr("APEX FORMULA MANAGER — ÇEVRİMİÇİ")
        m = self.recv_until("hello")
        print(f"Sunucuya bağlandı (protokol v{m['protocol_version']}).")
        sec = ask_int("1) Oda kur   2) Odaya katıl  [1]: ", 1, 2, 1)
        if sec == 1:
            races = ask_int("Kaç yarışlık sezon? (1-24) [6]: ", 1, 24, 6)
            turn = ask_int("Karar süresi saniye? (15-600) [120]: ", 15, 600, 120)
            self.send(op="create_room", name=self.name,
                      opts={"num_races": races, "turn_seconds": turn})
        else:
            code = input("Oda kodu: ").strip().upper()
            self.send(op="join_room", code=code, name=self.name)
        j = self.recv_until("joined")
        self.room = j["room"]
        print(f"\n>>> ODA KODU: {j['room']['code']}  (arkadaşların bununla katılır)")
        self.print_room()

        # takım seçimi (isimler için seed verisinden — sunucuyla aynı evren)
        from data.seed_data import SEED_TEAMS
        print("\nTAKIMLAR:")
        for i, t in enumerate(SEED_TEAMS, 1):
            print(f"  {i:2d}) {t['name']}")
        while self.my_team is None:
            k = ask_int("Takımını seç: ", 1, len(SEED_TEAMS))
            t_id = SEED_TEAMS[k - 1]["id"]
            self.send(op="pick_team", team_id=t_id)
            # Seçimin İŞLENDİĞİ yayını bekle: kuyrukta katılımlardan kalma eski
            # "room" yayınları olabilir; takımımız görünene ya da hata gelene
            # dek okumaya devam (guard: 20 mesaj).
            for _ in range(20):
                m = self.recv_until("room", "hata_da_don")
                if m.get("ev") == "error":
                    print("  (takım alınmış, başka seç)")
                    break
                self.room = m
                me = next((p for p in m["players"] if p["name"] == self.name), None)
                if me and me["team_id"] == t_id:
                    self.my_team = t_id
                    break
        self.send(op="ready")
        host = self.room.get("host") == self.name
        if host:
            input("\nHerkes katılıp hazır olunca [Enter] = OYUNU BAŞLAT ")
            self.send(op="start_game")
        else:
            print("\nHost'un oyunu başlatması bekleniyor...")
        sd = self.recv_until("static_data")
        self.static = sd
        self.name_of = sd["drivers"]
        self.my_drivers = sd["teams"][self.my_team]["drivers"]
        print(f"\nSezon başladı! Takımın: {self.team_name(self.my_team)} "
              f"({' & '.join(self.name_of[d] for d in self.my_drivers)})")

    # ------------------------------------------------------------- fazlar

    def deadline_left(self, ph):
        dl = ph.get("deadline_ts")
        return f" (süre: {max(0, int(dl - time.time()))}s)" if dl else ""

    def phase_aero(self, ph):
        t = ph["track"]
        self.num_laps = t["num_laps"]
        hr(f"YARIŞ {ph['race_no']}/{ph['total_races']} — {t['name']} "
           f"({t['num_laps']} tur){self.deadline_left(ph)}")
        print(f"Pist karakteri : {t['character'].upper()}")
        print(f"Hava tahmini   : {ph['forecast']['label']}")
        print(f"Pist koşulu    : {ph['conditions']['hint']}")
        print("\nARAÇ AYARI — 1=MAKS HIZ ... 3=dengeli ... 5=MAKS TUTUŞ")
        lvl = ask_int("Aero seviyesi [3]: ", 1, 5, 3)
        self.send(op="submit_aero", level=lvl)

    def show_quali(self, q):
        hr(f"SIRALAMA SONUÇLARI{' [💧 ıslak]' if q['is_rain'] else ''}")
        for pos, d in enumerate(q["grid"], 1):
            me = " ◀" if d in self.my_drivers else ""
            print(f"  P{pos:2d} {self.name_of.get(d, d)}{me}")

    def phase_strategy(self, ph):
        hr(f"YARIŞ ÖNCESİ STRATEJİ{self.deadline_left(ph)}")
        opts = ph["options"]
        print("STRATEJİ KARTLARI:")
        for i, o in enumerate(opts, 1):
            stints = " ".join(f"{s['compound'][:1].upper()}{s['laps']}"
                              for s in o["plan"])
            print(f"  {i}) {o['label']}\n     {stints} [risk: {o['risk']}] — {o['desc']}")
        choices = {}
        for d in self.my_drivers:
            print(f"\n— {self.name_of[d]} —")
            c = ask_int(f"  Kart (1-{len(opts)}) [1]: ", 1, len(opts), 1)
            for i, (sid, lbl) in enumerate(STYLE_LABELS.items(), 1):
                print(f"  {i}) {lbl}")
            st = ask_int("  Sürüş stili [1]: ", 1, 3, 1)
            for i, (_, lbl) in enumerate(WALL_LABELS, 1):
                print(f"  {i}) {lbl}")
            w = ask_int("  Pit duvarı talimatı [1]: ", 1, 4, 1)
            choices[d] = {"card_id": opts[c - 1]["id"],
                          "style": list(STYLE_LABELS)[st - 1],
                          "wall": None if w == 1 else WALL_LABELS[w - 1][0]}
        self.send(op="submit_strategy", choices=choices)
        print("\nDiğer takımlar bekleniyor — yarış birazdan başlıyor...")

    def show_race(self, rr):
        hr(f"YARIŞ — {rr['track']}")
        res = rr["result"]
        lines = build_replay_lines(res, self.my_drivers, self.name_of,
                                   self.num_laps or 50)
        if not lines:
            print("(Sakin bir yarış — kayda değer olay yok)")
        for _, _, line in lines:
            print(" " + line)
        hr("YARIŞ SONUCU")
        grid_pos = {d: i + 1 for i, d in enumerate(rr["grid"])}
        my_pts = 0
        for row in res["classification"]:
            d = row["driver_id"]
            pts = PTS.get(row.get("position"), 0) if row["status"] == "FIN" else 0
            me = " ◀" if d in self.my_drivers else ""
            if d in self.my_drivers:
                my_pts += pts
            durum = (f"P{row['position']:2d}" if row["status"] == "FIN"
                     else "DNF")
            extra = f" +{pts}p" if pts else ""
            delta = grid_pos.get(d, 0) - row["position"]
            ok = f" ({'+' if delta > 0 else ''}{delta})" if row["status"] == "FIN" else ""
            print(f"  {durum} {self.name_of.get(d, d):14s} "
                  f"{self.team_name(row['team_id']):14s}{extra}{ok}{me}")
        print(f"\nBu yarıştan puanın: {my_pts}")

    def show_standings(self, st):
        print("\nMARKALAR ŞAMPİYONASI:")
        for i, (t_id, p) in enumerate(st["teams"][:6], 1):
            me = " ◀" if t_id == self.my_team else ""
            print(f"  {i}. {self.team_name(t_id):16s} {p:4d}p{me}")

    def phase_upgrade(self, ph):
        hr(f"GELİŞTİRME{self.deadline_left(ph)}")
        sheet = ph["teams"][self.my_team]
        rights = self.static["upgrades_per_race"]
        targets = []          # (etiket, spend-dict)
        for d_id, stats in sheet["drivers"].items():
            for st, v in stats.items():
                targets.append((f"{self.name_of[d_id][:12]:12s} {STAT_TR[st]:12s} {v:5.0f}",
                                {"kind": "driver", "driver_id": d_id, "stat": st}))
        for st, v in sheet["car"].items():
            targets.append((f"{'ARAÇ':12s} {STAT_TR[st]:12s} {v:5.0f}",
                            {"kind": "car", "stat": st}))
        for i, (lbl, _) in enumerate(targets, 1):
            print(f"  {i:2d}) {lbl}")
        spends = []
        while len(spends) < rights:
            k = ask_int(f"Hak {len(spends)+1}/{rights} — hedef no (0=bitir): ",
                        0, len(targets))
            if k == 0:
                break
            spends.append(targets[k - 1][1])
        facility = None
        if sheet["active_facility_upgrade"]:
            print(f"Devam eden tesis inşaatı: {sheet['active_facility_upgrade']}")
        else:
            facs = [f for f in self.static["facilities"]
                    if sheet["facilities"].get(f, 3) < 3]
            if facs:
                print("TESİS (bedava, sadece zaman alır): 0) geç " +
                      " ".join(f"{i}) {f} sv{sheet['facilities'].get(f,1)}"
                               for i, f in enumerate(facs, 1)))
                k = ask_int("Tesis başlat? [0]: ", 0, len(facs), 0)
                if k:
                    facility = facs[k - 1]
        self.send(op="submit_upgrades", spends=spends, facility=facility)
        print("Diğer takımlar bekleniyor...")

    def season_end(self, ph):
        hr("SEZON SONU")
        st = ph["final_standings"]
        print("PİLOTLAR:")
        for i, (d, p) in enumerate(st["drivers"][:10], 1):
            me = " ◀" if d in self.my_drivers else ""
            print(f"  {i:2d}. {self.name_of.get(d, d):16s} {p:4d}p{me}")
        self.show_standings({"teams": st["teams"]})
        order = [t for t, _ in st["teams"]]
        my_rank = order.index(self.my_team) + 1 if self.my_team in order else "?"
        print(f"\nSezonu P{my_rank} bitirdin. Teşekkürler! 🏁")

    # ------------------------------------------------------------- ana döngü

    def run(self):
        with connect(self.url) as ws:
            self.ws = ws
            self.lobby()
            while True:
                m = self.recv_until("phase", "quali_result", "race_result",
                                    "standings")
                ev = m["ev"]
                if ev == "quali_result":
                    self.show_quali(m)
                elif ev == "race_result":
                    self.show_race(m)
                elif ev == "standings":
                    self.show_standings(m)
                elif ev == "phase":
                    if m["phase"] == "aero":
                        self.phase_aero(m)
                    elif m["phase"] == "strategy":
                        self.phase_strategy(m)
                    elif m["phase"] == "upgrade":
                        self.phase_upgrade(m)
                    elif m["phase"] == "season_end":
                        self.season_end(m)
                        return


def main():
    ap = argparse.ArgumentParser(description="Apex Formula Manager çevrimiçi istemci")
    ap.add_argument("--url", default="ws://127.0.0.1:8000/ws")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    name = a.name or input("Adın: ").strip() or "Oyuncu"
    try:
        Client(a.url, name).run()
    except KeyboardInterrupt:
        print("\n(çıkıldı)")
    except ConnectionRefusedError:
        print(f"Sunucuya bağlanılamadı: {a.url}\n"
              f"Önce sunucuyu başlat:  uvicorn server.app:app")


if __name__ == "__main__":
    main()
