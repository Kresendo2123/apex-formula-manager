// Apex Formula Manager — kod-güdümlü uygulama kökü + ekran yönlendirici (Faz 2, dilim 2).
//
// Boş bir GameObject'e SADECE bu bileşeni ekle ve Play'e bas. Geri kalan her şeyi
// (NetworkClient, Canvas, EventSystem, ekranlar) kod kurar. Sürükle-bırak yok.
//
// Akış: LobbyScreen -> (oyun başlar) -> phase mesajına göre ekran değişir:
//   aero -> AeroScreen ;  strategy/upgrade/season_end -> InfoScreen (sonraki dilimler).
// quali_result/race_result/standings InfoScreen'de özet olarak günlüğe düşer.
using System;
using System.Collections.Generic;
using System.Linq;
using Apex.Net;
using Newtonsoft.Json.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Apex.UI
{
    public class AppRoot : MonoBehaviour
    {
        public string defaultUrl = "ws://127.0.0.1:8000/ws";

        Canvas _canvas;
        Screen _screen;
        bool _inReplay;
        JObject _pendingPhase;     // replay izlenirken gelen faz buraya beklenir
        public NetworkClient Net { get; private set; }
        public JObject StaticData { get; private set; }
        public string MyName = "Oyuncu";    // lobide belirlenir
        public string MyTeamId;             // lobide takım seçilince ayarlanır
        public JObject LastStandings;       // her yarış sonrası gelen klasman

        void Start()
        {
            // 0) Yatay (landscape) mod — oyun yatay tasarlandı.
            UnityEngine.Screen.orientation = ScreenOrientation.LandscapeLeft;

            // 1) Ağ istemcisi (singleton). Yoksa kendimize ekleriz.
            Net = NetworkClient.Instance ?? gameObject.AddComponent<NetworkClient>();

            // 2) EventSystem (dokunma/tık girişi). Sahnede yoksa kur.
            if (FindAnyObjectByType<EventSystem>() == null)
            {
                var es = new GameObject("EventSystem", typeof(EventSystem));
                // Proje hangi giriş sistemindeyse uygun modül eklenir.
#if ENABLE_INPUT_SYSTEM && !ENABLE_LEGACY_INPUT_MANAGER
                es.AddComponent<UnityEngine.InputSystem.UI.InputSystemUIInputModule>();
#else
                es.AddComponent<StandaloneInputModule>();
#endif
            }

            // 3) Canvas
            _canvas = UIFactory.CreateCanvas();

            // 4) Genel olay yönlendirmesi
            Net.On(Protocol.EV_STATIC_DATA, m => StaticData = m);
            Net.On(Protocol.EV_STANDINGS, m => LastStandings = m);
            Net.On(Protocol.EV_RACE_RESULT, OnRaceResult);
            Net.On(Protocol.EV_PHASE, OnPhase);

            // 5) İlk ekran
            SetScreen(new LobbyScreen(this));
        }

        void Update() => _screen?.Tick(Time.deltaTime);

        void OnRaceResult(JObject m)
        {
            // Yarış sonucu geldi: replay'e geç. Hemen ardından gelecek faz
            // (geliştirme) replay bitene kadar beklesin.
            _inReplay = true;
            SetScreen(new RaceReplayScreen(this, m));
        }

        // Replay ekranı "Devam" deyince çağrılır: bekleyen faza geç.
        public void ProceedAfterReplay()
        {
            _inReplay = false;
            var p = _pendingPhase; _pendingPhase = null;
            if (p != null) OnPhase(p);
        }

        void OnPhase(JObject m)
        {
            if (_inReplay) { _pendingPhase = m; return; }   // replay bitsin, sonra
            string phase = (string)m["phase"];
            switch (phase)
            {
                case "aero":       SetScreen(new AeroScreen(this, m)); break;
                case "strategy":   SetScreen(new StrategyScreen(this, m)); break;
                case "upgrade":    SetScreen(new UpgradeScreen(this, m)); break;
                case "season_end": SetScreen(new StandingsScreen(this, m)); break;
            }
        }

        public void SetScreen(Screen next)
        {
            _screen?.Dispose();
            for (int i = _canvas.transform.childCount - 1; i >= 0; i--)
                Destroy(_canvas.transform.GetChild(i).gameObject);
            _screen = next;
            RectTransform root = _screen.Scroll
                ? UIFactory.ScrollColumn(_canvas.transform)
                : UIFactory.FullRect(_canvas.transform);
            _screen.Build(root);
        }
    }

    // ----------------------------------------------------------------- ekran tabanı

    public abstract class Screen
    {
        protected readonly AppRoot App;
        protected NetworkClient Net => App.Net;
        readonly List<(string ev, Action<JObject> cb)> _subs = new();

        protected Screen(AppRoot app) { App = app; }

        protected void Sub(string ev, Action<JObject> cb)
        {
            Net.On(ev, cb);
            _subs.Add((ev, cb));
        }

        public abstract void Build(Transform parent);

        // true: dikey kaydırmalı menü kökü; false: tam ekran sabit (yarış gibi).
        public virtual bool Scroll => true;

        public virtual void Tick(float dt) { }

        public virtual void Dispose()
        {
            foreach (var (ev, cb) in _subs) Net.Off(ev, cb);
            _subs.Clear();
        }
    }

    // ----------------------------------------------------------------- LOBİ

    public class LobbyScreen : Screen
    {
        Transform _root;
        TMP_Text _status;
        TMP_InputField _url, _name, _code;
        JObject _room;
        JArray _teams;
        bool _ready;
        string _myName = "Oyuncu";

        public LobbyScreen(AppRoot app) : base(app) { }

        public override void Build(Transform parent)
        {
            _root = parent;
            _url  = null; _name = null; _code = null;

            Sub(Protocol.EV_HELLO, _ => { });
            Sub(Protocol.EV_JOINED, OnJoined);
            Sub(Protocol.EV_ROOM, m => { _room = m; Rebuild(); });
            Sub(Protocol.EV_TEAM_CATALOG, m => { _teams = (JArray)m["teams"]; Rebuild(); });
            Sub(Protocol.EV_ERROR, m => SetStatus("Hata: " +
                Protocol.FriendlyError((string)m["code"], (string)m["msg"])));

            Net.OnConnected += OnConnected;
            Net.OnClosed    += OnClosed;
            Net.OnNetError  += OnNetErr;

            Rebuild();
        }

        public override void Dispose()
        {
            base.Dispose();
            Net.OnConnected -= OnConnected;
            Net.OnClosed    -= OnClosed;
            Net.OnNetError  -= OnNetErr;
        }

        void OnConnected() { SetStatus("Bağlandı."); Rebuild(); }
        void OnClosed(string _) { SetStatus("Bağlantı kapandı."); _room = null; Rebuild(); }
        void OnNetErr(string e) => SetStatus("Ağ hatası: " + e);

        void OnJoined(JObject m)
        {
            _room = (JObject)m["room"];
            Net.Send(Protocol.OP_LIST_TEAMS);     // takım kataloğunu çek
            SetStatus("Odaya girdin: " + (string)_room["code"]);
            Rebuild();
        }

        void Rebuild()
        {
            for (int i = _root.childCount - 1; i >= 0; i--)
                UnityEngine.Object.Destroy(_root.GetChild(i).gameObject);

            UIFactory.Label(_root, "APEX FORMULA — Lobi", 48,
                            TextAlignmentOptions.Center, UIFactory.Accent);
            _status = UIFactory.Label(_root, "", 28, TextAlignmentOptions.Center);

            if (!Net.IsConnected)        BuildConnect();
            else if (_room == null)      BuildRoomEntry();
            else                          BuildInRoom();
        }

        void BuildConnect()
        {
            _url  = UIFactory.Input(_root, "Sunucu adresi", App.defaultUrl);
            _name = UIFactory.Input(_root, "Adın", _myName);
            UIFactory.Button(_root, "Bağlan", async () =>
            {
                _myName = NameOr();
                SetStatus("Bağlanılıyor…");
                await Net.Connect(_url.text.Trim());
            }, color: UIFactory.Accent);
        }

        void BuildRoomEntry()
        {
            _name = UIFactory.Input(_root, "Adın", _myName);
            UIFactory.Button(_root, "Yeni Oda Kur", () =>
            {
                _myName = NameOr();
                Net.Send(Protocol.OP_CREATE_ROOM, new {
                    name = _myName, opts = new { num_races = 5, turn_seconds = 90 } });
            }, color: UIFactory.Accent);

            _code = UIFactory.Input(_root, "Oda kodu (4 harf)");
            UIFactory.Button(_root, "Koda Katıl", () =>
            {
                _myName = NameOr();
                string code = _code.text.Trim().ToUpper();
                if (code.Length < 4) { SetStatus("4 harfli kod gir."); return; }
                Net.Send(Protocol.OP_JOIN_ROOM, new { code, name = _myName });
            });
        }

        void BuildInRoom()
        {
            string host = (string)_room["host"];
            bool isHost = host == _myName;
            App.MyName = _myName;
            App.MyTeamId = MyTeam();    // strateji/geliştirme ekranları bunu kullanır
            UIFactory.Label(_root, $"Oda: {_room["code"]}   (sahip: {host})", 34,
                            TextAlignmentOptions.Center);

            // oyuncular
            var taken = new HashSet<string>();
            var sb = new System.Text.StringBuilder();
            foreach (var p in (JArray)_room["players"])
            {
                string nm = (string)p["name"], tid = (string)p["team_id"];
                if (!string.IsNullOrEmpty(tid)) taken.Add(tid);
                bool rdy = (bool?)p["ready"] ?? false;
                sb.AppendLine($"{nm}  [{(string.IsNullOrEmpty(tid) ? "—" : tid)}]  {(rdy ? "HAZIR" : "...")}");
            }
            UIFactory.Label(_root, sb.ToString(), 26, TextAlignmentOptions.Center);

            // takım seçici
            UIFactory.Label(_root, "Takımını seç:", 30, TextAlignmentOptions.Center);
            if (_teams == null) { Net.Send(Protocol.OP_LIST_TEAMS); }
            else
            {
                string myTeam = MyTeam();
                foreach (var t in _teams)
                {
                    string id = (string)t["id"], name = (string)t["name"];
                    bool mine = id == myTeam;
                    bool busy = taken.Contains(id) && !mine;
                    string drv = string.Join(", ", t["drivers"].ToObject<string[]>());
                    var col = mine ? UIFactory.Accent : busy ? new Color(0.3f,0.3f,0.3f) : UIFactory.Btn;
                    UIFactory.Button(_root, $"{name}  ({drv}){(busy ? "  — dolu" : "")}",
                        busy ? (Action)null : () => Net.Send(Protocol.OP_PICK_TEAM, new { team_id = id }),
                        height: 76, color: col);
                }
            }

            // hazır + başlat
            UIFactory.Button(_root, _ready ? "Hazırım (iptal)" : "Hazır Ol", () =>
            {
                _ready = !_ready;
                Net.Send(Protocol.OP_READY, new { ready = _ready });
            }, color: _ready ? new Color(0.2f, 0.6f, 0.3f) : UIFactory.Btn);
            if (isHost)
                UIFactory.Button(_root, "BASLAT", () => Net.Send(Protocol.OP_START_GAME),
                                 color: UIFactory.Accent);
        }

        string MyTeam()
        {
            foreach (var p in (JArray)_room["players"])
                if ((string)p["name"] == _myName) return (string)p["team_id"];
            return null;
        }

        string NameOr() { var n = _name ? _name.text.Trim() : ""; return string.IsNullOrEmpty(n) ? "Oyuncu" : n; }
        void SetStatus(string s) { if (_status) _status.text = s; Debug.Log("[Lobby] " + s); }
    }

    // ----------------------------------------------------------------- AERO

    public class AeroScreen : Screen
    {
        readonly JObject _phase;
        int _level = 3;

        public AeroScreen(AppRoot app, JObject phase) : base(app) { _phase = phase; }

        public override void Build(Transform parent)
        {
            int raceNo = (int?)_phase["race_no"] ?? 1;
            int total  = (int?)_phase["total_races"] ?? 1;
            var track   = _phase["track"];
            var fc      = _phase["forecast"];
            var cond    = _phase["conditions"];

            UIFactory.Label(parent, $"Yarış {raceNo}/{total} — Aero Ayarı", 46,
                            TextAlignmentOptions.Center, UIFactory.Accent);

            if (track != null)
                UIFactory.Label(parent,
                    $"Pist: {track["name"]}  ·  {track["num_laps"]} tur  ·  karakter: {track["character"]}",
                    30, TextAlignmentOptions.Center);

            if (cond != null)
                UIFactory.Label(parent, $"Lastik aşınması: {cond["hint"]}", 28,
                                TextAlignmentOptions.Center);

            if (fc != null && fc.Type != JTokenType.Null)
            {
                string label = (string)fc["label"];
                if (string.IsNullOrEmpty(label))
                {
                    double rain = (double?)fc["rain_prob"] ?? 0;
                    label = $"Yağmur ihtimali: %{Mathf.RoundToInt((float)rain * 100)}";
                }
                UIFactory.Label(parent, "Hava: " + label, 26, TextAlignmentOptions.Center);
            }

            UIFactory.Label(parent,
                "Düşük aero = düz hızda iyi, virajda zayıf. Yüksek aero tersi.",
                24, TextAlignmentOptions.Center, new Color(0.7f,0.7f,0.7f));

            UIFactory.Stepper(parent, "Aero seviyesi (1-5):", 1, 5, _level, v => _level = v);

            UIFactory.Button(parent, "Gönder", () =>
            {
                Net.Send(Protocol.OP_SUBMIT_AERO, new { level = _level });
            }, color: UIFactory.Accent);

            var status = UIFactory.Label(parent, "", 26, TextAlignmentOptions.Center);
            Sub(Protocol.EV_SUBMIT_OK, _ => status.text = "Gönderildi — diğer oyuncular bekleniyor…");
            Sub(Protocol.EV_PLAYER_SUBMITTED, m => Debug.Log($"[Aero] gönderen: {m["team_id"]}"));
            Sub(Protocol.EV_AUTO_FILLED, _ => status.text = "Süre doldu — eksikler otomatik dolduruldu.");
            Sub(Protocol.EV_QUALI_RESULT, _ => status.text = "Sıralama turu koştu, strateji fazına geçiliyor…");
            Sub(Protocol.EV_ERROR, m => status.text = "Hata: " +
                Protocol.FriendlyError((string)m["code"], (string)m["msg"]));
        }
    }

    // ----------------------------------------------------------------- STRATEJİ

    public class StrategyScreen : Screen
    {
        readonly JObject _phase;
        class Choice { public string cardId; public string style = "normal"; public string wall; }
        readonly Dictionary<string, Choice> _ch = new();

        public StrategyScreen(AppRoot app, JObject phase) : base(app) { _phase = phase; }

        public override void Build(Transform parent)
        {
            int raceNo = (int?)_phase["race_no"] ?? 1;
            int total  = (int?)_phase["total_races"] ?? 1;
            var grid    = _phase["grid"] as JArray;
            var options = _phase["options"] as JArray;
            var sd = App.StaticData;

            UIFactory.Label(parent, $"Yarış {raceNo}/{total} — Strateji", 46,
                            TextAlignmentOptions.Center, UIFactory.Accent);

            // stil ve pit-duvarı seçenekleri (static_data'dan, yedeği sabit)
            string[] styleIds = Strs(sd?["styles"]) ?? new[] { "normal", "aggressive", "long_stint" };
            string[] styleLabels = styleIds.Select(StyleLabel).ToArray();
            string[] wallIds = Strs(sd?["wall_risks"]) ?? new[] { "kart", "düşük", "orta", "yüksek" };

            // strateji kartları — başa "(otomatik)" eklenir (card_id = null)
            var cardIds   = new List<string> { null };
            var cardLabels = new List<string> { "(otomatik — yapay zeka seçsin)" };
            var cardDescs  = new List<string> { "Stratejiyi motora bırak." };
            if (options != null)
                foreach (var o in options)
                {
                    cardIds.Add((string)o["id"]);
                    cardLabels.Add(San((string)o["label"]));
                    cardDescs.Add(San((string)o["desc"]));
                }

            JToken teamTok = (sd?["teams"] != null && !string.IsNullOrEmpty(App.MyTeamId))
                ? sd["teams"][App.MyTeamId] : null;
            string[] myDrivers = Strs(teamTok?["drivers"]) ?? Array.Empty<string>();
            if (myDrivers.Length == 0)
                UIFactory.Label(parent, "(Pilot listesi alınamadı — yine de gönderebilirsin.)",
                                24, TextAlignmentOptions.Center, new Color(0.8f, 0.5f, 0.5f));

            foreach (var drvId in myDrivers)
            {
                string drv = drvId;                      // closure için
                _ch[drv] = new Choice();
                string name = (string)sd["drivers"]?[drv] ?? drv;
                int gp = grid != null ? grid.ToObject<string[]>().ToList().IndexOf(drv) + 1 : 0;

                UIFactory.Label(parent, $"{(gp > 0 ? $"P{gp}  " : "")}{name}", 36,
                                TextAlignmentOptions.Center, UIFactory.Accent);

                var dsc = UIFactory.Label(parent, "", 22, TextAlignmentOptions.Center,
                                          new Color(0.72f, 0.72f, 0.72f));
                UIFactory.Cycler(parent, "Strateji kartı:", cardLabels.ToArray(), 0,
                    i => { _ch[drv].cardId = cardIds[i]; dsc.text = cardDescs[i]; });
                UIFactory.Cycler(parent, "Sürüş stili:", styleLabels, 0,
                    i => _ch[drv].style = styleIds[i]);
                UIFactory.Cycler(parent, "Pit duvarı riski:", wallIds, 0,
                    i => _ch[drv].wall = wallIds[i] == "kart" ? null : wallIds[i]);
            }

            var status = UIFactory.Label(parent, "", 26, TextAlignmentOptions.Center);
            UIFactory.Button(parent, "Gönder", () =>
            {
                var choices = new JObject();
                foreach (var kv in _ch)
                {
                    var o = new JObject
                    {
                        ["card_id"] = kv.Value.cardId != null ? (JToken)kv.Value.cardId : JValue.CreateNull(),
                        ["style"]   = kv.Value.style,
                        ["wall"]    = kv.Value.wall != null ? (JToken)kv.Value.wall : JValue.CreateNull(),
                    };
                    choices[kv.Key] = o;
                }
                Net.Send(Protocol.OP_SUBMIT_STRATEGY, new { choices });
                status.text = "Gönderiliyor…";
            }, color: UIFactory.Accent);

            Sub(Protocol.EV_SUBMIT_OK, _ => status.text = "Gönderildi — diğer oyuncular bekleniyor…");
            Sub(Protocol.EV_AUTO_FILLED, _ => status.text = "Süre doldu — eksikler otomatik dolduruldu.");
            Sub(Protocol.EV_RACE_RESULT, _ => status.text = "Yarış koşuluyor…");
            Sub(Protocol.EV_ERROR, m => status.text = "Hata: " +
                Protocol.FriendlyError((string)m["code"], (string)m["msg"]));
        }

        static string StyleLabel(string id) => id switch
        {
            "normal"      => "Normal",
            "aggressive"  => "Agresif",
            "long_stint"  => "Uzun stint",
            _             => id,
        };

        // Fontta olmayan simgeleri sadeleştir (→ 🌧 vb.).
        static string San(string s) => string.IsNullOrEmpty(s) ? s :
            s.Replace("→", ">").Replace("🌧", "(yağmur)").Replace("🏁", "");

        static string[] Strs(JToken t) =>
            t is JArray a ? a.Select(x => (string)x).ToArray() : null;
    }

    // ----------------------------------------------------------------- BİLGİ (geçici)
    // Henüz tam ekranı yapılmamış fazlar için: bağlamı + gelen sonuçları gösterir.

    public class InfoScreen : Screen
    {
        readonly string _title;
        readonly JObject _phase;
        TMP_Text _log;
        readonly System.Text.StringBuilder _sb = new();

        public InfoScreen(AppRoot app, string title, JObject phase) : base(app)
        { _title = title; _phase = phase; }

        public override void Build(Transform parent)
        {
            UIFactory.Label(parent, _title, 46, TextAlignmentOptions.Center, UIFactory.Accent);
            UIFactory.Label(parent, "(Bu ekranın tam hali sonraki dilimde gelecek.)",
                            24, TextAlignmentOptions.Center, new Color(0.7f,0.7f,0.7f));

            int raceNo = (int?)_phase["race_no"] ?? 0;
            UIFactory.Label(parent, $"Yarış: {raceNo}   Faz: {_phase["phase"]}", 30,
                            TextAlignmentOptions.Center);

            _log = UIFactory.Label(parent, "", 24, TextAlignmentOptions.Left);

            Sub(Protocol.EV_QUALI_RESULT, m =>
                AddLine($"Sıralama (yarış {m["race_no"]}): grid hazır" +
                        ((bool?)m["is_rain"] == true ? " (yağmurlu)" : "")));
            Sub(Protocol.EV_RACE_RESULT, m =>
                AddLine($"Yarış {m["race_no"]} bitti — {m["track"]}. Olay sayısı: " +
                        $"{(m["result"]?["events"] as JArray)?.Count ?? 0}"));
            Sub(Protocol.EV_STANDINGS, m => AddLine("Klasman güncellendi."));
            Sub(Protocol.EV_AUTO_FILLED, m => AddLine($"Süre doldu, dolduruldu: {m["phase"]}"));

            // Strateji/geliştirme fazında oyunu kilitlememek için boş gönderip geçelim.
            string phase = (string)_phase["phase"];
            if (phase == "strategy")
                UIFactory.Button(parent, "Boş strateji gönder (geç)", () =>
                    Net.Send(Protocol.OP_SUBMIT_STRATEGY, new { choices = new JObject() }),
                    color: UIFactory.Accent);
            else if (phase == "upgrade")
                UIFactory.Button(parent, "Geliştirme yapmadan geç", () =>
                    Net.Send(Protocol.OP_SUBMIT_UPGRADES, new { spends = new JArray() }),
                    color: UIFactory.Accent);
            else if (phase == "season_end")
                AddLine("Sezon tamamlandi!");
        }

        void AddLine(string s) { _sb.AppendLine(s); if (_log) _log.text = _sb.ToString(); Debug.Log("[Info] " + s); }
    }
}
