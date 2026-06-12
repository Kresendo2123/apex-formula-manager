"""
SUNUCU UÇTAN UCA TESTİ (Faz 1)
===============================
Gerçek bir uvicorn süreci başlatır (üretimle aynı: tüm bağlantılar TEK event
loop'ta) ve iki WebSocket istemcisiyle tam akışı sürer:

1) Oda kur + kodla katıl + takım seç + hazır + başlat (lobi akışı).
2) Yarış 1: iki oyuncu da aero/strateji/geliştirme gönderir; her iki istemci
   de AYNI race_result'ı (aynı seed, aynı klasman) alır.
3) Yarış 2: kimse göndermez — süre sayacı eksikleri otomatik doldurur
   (auto_filled) ve sezon kilitlenmeden sonuna kadar ilerler.
4) Hatalı girdiler doğru hata kodlarını döner.

Not: FastAPI TestClient bilinçli olarak KULLANILMAZ — her websocket bağlantısını
ayrı event loop thread'inde koşturduğundan oda kilidi (asyncio.Lock) çapraz
loop'ta askıda kalıyor; üretimdeki tek-loop davranışını uvicorn verir.

Çalıştırma: python test/server_smoke_test.py
"""
import os
import sys
import json
import time
import socket
import subprocess
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from websockets.sync.client import connect

RECV_TIMEOUT = 30   # tekil mesaj bekleme üst sınırı (sn)
GUARD = 300


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(port: int) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.app:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT)
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health",
                                        timeout=1) as r:
                if r.status == 200:
                    return proc
        except Exception:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("uvicorn 20 sn'de ayağa kalkmadı")


def recv_until(ws, ev):
    for _ in range(GUARD):
        m = json.loads(ws.recv(timeout=RECV_TIMEOUT))
        if m.get("ev") == ev:
            return m
        if m.get("ev") == "error":
            raise AssertionError(f"beklenmedik error: {m}")
    raise AssertionError(f"'{ev}' mesajı {GUARD} mesajda gelmedi")


def expect_error(ws, code):
    for _ in range(GUARD):
        m = json.loads(ws.recv(timeout=RECV_TIMEOUT))
        if m.get("ev") == "error":
            assert m["code"] == code, f"{code} beklendi, gelen: {m}"
            return
    raise AssertionError(f"error({code}) gelmedi")


def main():
    fails = 0
    port = free_port()
    proc = start_server(port)
    url = f"ws://127.0.0.1:{port}/ws"
    try:
        with connect(url) as w1, connect(url) as w2:
            send1 = lambda **m: w1.send(json.dumps(m))
            send2 = lambda **m: w2.send(json.dumps(m))
            assert recv_until(w1, "hello")["protocol_version"] == 1
            recv_until(w2, "hello")

            # --- lobi
            send1(op="create_room", name="Ayşe",
                  opts={"num_races": 2, "turn_seconds": 4, "seed": 123})
            code = recv_until(w1, "joined")["room"]["code"]
            send2(op="join_room", code=code, name="Bora")
            recv_until(w2, "joined")

            send2(op="start_game")                      # host değil
            expect_error(w2, "not_host")
            send1(op="pick_team", team_id="T_MCL")
            send2(op="pick_team", team_id="T_MCL")      # alınmış takım
            expect_error(w2, "team_taken")
            send2(op="pick_team", team_id="T_FER")
            send1(op="ready"); send2(op="ready")
            send1(op="start_game")

            sd = recv_until(w1, "static_data"); recv_until(w2, "static_data")
            mcl = sd["teams"]["T_MCL"]["drivers"]

            # --- yarış 1: aero
            ph = recv_until(w1, "phase"); recv_until(w2, "phase")
            assert ph["phase"] == "aero" and ph["race_no"] == 1
            assert ph.get("deadline_ts"), "karar fazında deadline_ts olmalı"

            send1(op="submit_strategy", choices={})     # yanlış faz
            expect_error(w1, "submit_rejected")

            send1(op="submit_aero", level=4)
            send2(op="submit_aero", level=2)
            recv_until(w1, "quali_result"); recv_until(w2, "quali_result")
            ph = recv_until(w1, "phase"); recv_until(w2, "phase")
            assert ph["phase"] == "strategy" and ph["options"]

            card = ph["options"][0]["id"]
            send1(op="submit_strategy", choices={
                mcl[0]: {"card_id": card, "style": "aggressive", "wall": "yüksek"},
                mcl[1]: {"style": "long_stint"}})
            send2(op="submit_strategy", choices={})
            r1a = recv_until(w1, "race_result")
            r1b = recv_until(w2, "race_result")
            if json.dumps(r1a, sort_keys=True) != json.dumps(r1b, sort_keys=True):
                print("❌ İki istemci farklı race_result aldı"); fails += 1
            if not r1a["result"].get("seed") or not r1a["result"]["events"]:
                print("❌ race_result içinde seed/events eksik"); fails += 1
            recv_until(w1, "standings"); recv_until(w2, "standings")
            ph = recv_until(w1, "phase"); recv_until(w2, "phase")
            assert ph["phase"] == "upgrade"

            send1(op="submit_upgrades",
                  spends=[{"kind": "driver", "driver_id": mcl[0], "stat": "pace"}],
                  facility="simulator")
            send2(op="submit_upgrades", spends=[])
            ph = recv_until(w1, "phase"); recv_until(w2, "phase")
            assert ph["phase"] == "aero" and ph["race_no"] == 2

            # --- yarış 2: AFK — sayaç (4 sn) doldurup ilerletmeli
            af = recv_until(w1, "auto_filled")
            assert set(af["teams"]) == {"T_FER", "T_MCL"}, f"auto_filled: {af}"
            recv_until(w1, "quali_result")
            assert recv_until(w1, "phase")["phase"] == "strategy"
            r2 = recv_until(w1, "race_result")          # strateji de zaman aşımıyla
            assert r2["race_no"] == 2
            ph = recv_until(w1, "phase")
            assert ph["phase"] == "season_end" and ph["final_standings"]["teams"]

            # w2 de aynı noktaya ulaşmalı
            recv_until(w2, "race_result")
            assert recv_until(w2, "phase")["phase"] == "season_end"
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    print("=" * 60)
    if fails == 0:
        print("✅ Sunucu: lobi, 2 oyunculu sezon, özdeş yayın, zaman aşımı "
              "auto-fill ve hata kodları TEMİZ.")
    else:
        print(f"❌ {fails} hata."); sys.exit(1)


if __name__ == "__main__":
    main()
