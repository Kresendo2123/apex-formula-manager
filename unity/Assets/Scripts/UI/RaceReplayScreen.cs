// Apex Formula Manager — 2D yarış replay (Faz 2, dilim 3).
//
// Yarış sunucuda tek seferde simüle edilir; bu ekran result.lap_positions
// (her turun sıralaması) + result.events akışını istemcide TEMPOLU oynatır.
// Yarış içi etkileşim YOK — sadece sunum: pist haritasında sıralamaya göre
// kayan noktalar + timing tower + olay şeridi. Bitince "Devam" ile bekleyen
// faza (geliştirme) geçilir.
using System.Collections.Generic;
using Apex.Net;
using Newtonsoft.Json.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Apex.UI
{
    public class RaceReplayScreen : Screen
    {
        readonly JObject _msg;

        // veri
        List<List<string>> _pos = new();     // _pos[L] = o turdaki sıralama
        List<JToken> _events = new();
        int _evIdx;
        int _total;                          // pisteki toplam araç (sabit aralık için)
        int _lapCount, _curLap = -1;
        Dictionary<string, string> _name = new();   // driver_id -> isim
        Dictionary<string, string> _team = new();   // driver_id -> team_id
        HashSet<string> _mine = new();

        // oynatma
        bool _playing = true, _finished, _ready;
        float _acc;
        readonly float[] _speeds = { 0.6f, 0.3f, 0.15f };
        int _speedIdx;

        // görsel
        RectTransform _map;
        readonly Dictionary<string, RectTransform> _dot = new();
        readonly Dictionary<string, TMP_Text> _num = new();
        readonly Dictionary<string, float> _ang = new();
        readonly Dictionary<string, float> _tgt = new();
        TMP_Text _lapLabel, _towerL, _towerR, _ticker, _results, _champ;
        Button _playBtn, _speedBtn;
        RectTransform _resultsPanel;
        readonly List<string> _tickLines = new();

        // sollama animasyonu (Adım 2)
        struct Pass { public string passer, passed; public bool drs; }
        readonly Queue<Pass> _cutQueue = new();
        bool _animOn = true, _cutActive;
        float _cutTime;
        Button _animBtn;
        RectTransform _cutPanel, _cutStrip, _carA, _carB;   // A = geçen, B = geçilen
        Image _carABody, _carBBody, _cutFlash;
        TMP_Text _cutCaption;
        readonly List<Image> _speedLines = new();
        bool _cutDrs;
        const float CUT_DUR = 1.8f, CUT_HOLD = 0.6f;
        const float STRIP_W = 1500f, STRIP_H = 250f;   // referans birimi (canvas ölçekler)

        public RaceReplayScreen(AppRoot app, JObject msg) : base(app) { _msg = msg; }

        public override bool Scroll => false;   // kaydırmasız, sabit yatay düzen

        public override void Build(Transform parent)
        {
            var result = (JObject)_msg["result"];
            foreach (JArray lap in result["lap_positions"])
            {
                var row = new List<string>();
                foreach (var d in lap) row.Add((string)d);
                _pos.Add(row);
            }
            foreach (var e in (JArray)result["events"]) _events.Add(e);
            _lapCount = _pos.Count - 1;
            _total = _pos.Count > 0 ? _pos[0].Count : 1;

            var sd = App.StaticData;
            if (sd?["drivers"] is JObject drv)
                foreach (var p in drv) _name[p.Key] = (string)p.Value;
            if (sd?["teams"] is JObject teams)
                foreach (var p in teams)
                {
                    var ds = p.Value?["drivers"] as JArray;
                    if (ds != null) foreach (var d in ds) _team[(string)d] = p.Key;
                }
            if (!string.IsNullOrEmpty(App.MyTeamId) && sd?["teams"]?[App.MyTeamId]?["drivers"] is JArray md)
                foreach (var d in md) _mine.Add((string)d);

            // ===== YATAY (LANDSCAPE) SABİT DÜZEN — kaydırma yok =====
            // Üst bar: başlık (sol) + tur (sağ)
            LabelAt(parent, 0.02f, 0.92f, 0.70f, 1.00f,
                    $"Yarış {_msg["race_no"]} — {_msg["track"]}", 38,
                    TextAlignmentOptions.Left, UIFactory.Accent);
            _lapLabel = LabelAt(parent, 0.70f, 0.92f, 0.98f, 1.00f, "Tur 0 / " + _lapCount,
                                34, TextAlignmentOptions.Right);

            // Sol: pist haritası
            _map = PanelAt(parent, 0.02f, 0.16f, 0.60f, 0.90f, new Color(0.07f, 0.09f, 0.12f));
            foreach (var id in _pos[0])
            {
                _dot[id] = MakeDot(id);
                _ang[id] = _tgt[id] = AngleForRank(_pos[0].IndexOf(id));
            }

            // Sağ üst: SIRALAMA (iki sütun: P1-11 | P12-22)
            LabelAt(parent, 0.62f, 0.84f, 0.98f, 0.90f, "SIRALAMA", 26,
                    TextAlignmentOptions.Left, UIFactory.Accent);
            PanelAt(parent, 0.62f, 0.46f, 0.98f, 0.84f, new Color(0.12f, 0.14f, 0.18f));
            _towerL = LabelAt(parent, 0.625f, 0.46f, 0.80f, 0.84f, "", 21, TextAlignmentOptions.TopLeft);
            _towerR = LabelAt(parent, 0.80f, 0.46f, 0.975f, 0.84f, "", 21, TextAlignmentOptions.TopLeft);

            // Sağ alt: OLAYLAR
            LabelAt(parent, 0.62f, 0.40f, 0.98f, 0.46f, "OLAYLAR", 26,
                    TextAlignmentOptions.Left, UIFactory.Accent);
            PanelAt(parent, 0.62f, 0.16f, 0.98f, 0.40f, new Color(0.12f, 0.14f, 0.18f));
            _ticker = LabelAt(parent, 0.62f, 0.16f, 0.98f, 0.40f, "", 20,
                              TextAlignmentOptions.TopLeft, new Color(0.82f, 0.82f, 0.85f));

            // Alt: kontroller
            var ctl = PanelAt(parent, 0.02f, 0.03f, 0.98f, 0.13f, new Color(0, 0, 0, 0));
            var h = ctl.gameObject.AddComponent<HorizontalLayoutGroup>();
            h.spacing = 14; h.childAlignment = TextAnchor.MiddleCenter;
            h.childControlWidth = true; h.childControlHeight = true;
            h.childForceExpandWidth = true; h.childForceExpandHeight = true;
            _playBtn  = UIFactory.Button(ctl, "Duraklat", () => { _playing = !_playing; RefreshControls(); });
            _speedBtn = UIFactory.Button(ctl, "Hiz 1x", CycleSpeed);
            _animBtn  = UIFactory.Button(ctl, "Anim: Acik", () =>
            {
                _animOn = !_animOn;
                if (!_animOn) _cutQueue.Clear();
                RefreshControls();
            });
            UIFactory.Button(ctl, "Sona atla", SkipToEnd);
            UIFactory.Button(ctl, "Devam", () => App.ProceedAfterReplay(), color: UIFactory.Accent);

            BuildCutscene(parent);

            // Sonuç paneli (bitince açılır; opak, iki sütun: sol SONUÇ, sağ ŞAMPİYONA)
            _resultsPanel = PanelAt(parent, 0.02f, 0.15f, 0.98f, 0.90f, new Color(0.06f, 0.07f, 0.10f, 1f));
            LabelAt(_resultsPanel, 0f, 0.90f, 1f, 1f, "YARIŞ SONUCU", 34,
                    TextAlignmentOptions.Center, UIFactory.Accent);
            _results = LabelAt(_resultsPanel, 0.03f, 0f, 0.50f, 0.90f, "", 24, TextAlignmentOptions.TopLeft);
            _champ   = LabelAt(_resultsPanel, 0.52f, 0f, 0.98f, 0.90f, "", 24, TextAlignmentOptions.TopLeft);
            _resultsPanel.gameObject.SetActive(false);

            GoToLap(0);
        }

        // --------------------------------------------------------- düzen yardımcıları

        static RectTransform PanelAt(Transform parent, float x0, float y0, float x1, float y1, Color bg)
        {
            var go = new GameObject("panel", typeof(Image));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = new Vector2(x0, y0); rt.anchorMax = new Vector2(x1, y1);
            rt.offsetMin = rt.offsetMax = Vector2.zero;
            go.GetComponent<Image>().color = bg;
            return rt;
        }

        static TMP_Text LabelAt(Transform parent, float x0, float y0, float x1, float y1,
                                string text, int size, TextAlignmentOptions align, Color? color = null)
        {
            var go = new GameObject("Label", typeof(TextMeshProUGUI));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = new Vector2(x0, y0); rt.anchorMax = new Vector2(x1, y1);
            rt.offsetMin = new Vector2(14, 8); rt.offsetMax = new Vector2(-14, -8);
            var t = go.GetComponent<TextMeshProUGUI>();
            t.text = text; t.fontSize = size; t.color = color ?? UIFactory.Text;
            t.alignment = align; t.textWrappingMode = TextWrappingModes.Normal;
            return t;
        }

        // --------------------------------------------------------- sollama animasyonu

        void BuildCutscene(Transform parent)
        {
            _cutPanel = PanelAt(parent, 0f, 0f, 1f, 1f, new Color(0f, 0f, 0f, 0.88f));
            _cutCaption = LabelAt(_cutPanel, 0.08f, 0.66f, 0.92f, 0.80f, "", 40,
                                  TextAlignmentOptions.Center, UIFactory.Accent);
            _cutStrip = PanelAt(_cutPanel, 0.08f, 0.36f, 0.92f, 0.60f, new Color(0.10f, 0.11f, 0.14f));
            // orta şerit çizgisi
            var line = PanelAt(_cutStrip, 0f, 0.48f, 1f, 0.52f, new Color(1, 1, 1, 0.12f));
            _ = line;
            // hız çizgileri (whoosh)
            for (int i = 0; i < 7; i++)
            {
                var s = new GameObject("speed", typeof(Image));
                var srt = s.GetComponent<RectTransform>();
                srt.SetParent(_cutStrip, false);
                srt.anchorMin = srt.anchorMax = srt.pivot = new Vector2(0.5f, 0.5f);
                srt.sizeDelta = new Vector2(150, 6);
                srt.anchoredPosition = new Vector2(0, Mathf.Lerp(-0.32f, 0.32f, i / 6f) * STRIP_H);
                var im = s.GetComponent<Image>(); im.color = new Color(1, 1, 1, 0f);
                _speedLines.Add(im);
            }
            _carB = MakeCar(_cutStrip, out _carBBody);   // geçilen (altta)
            _carA = MakeCar(_cutStrip, out _carABody);   // geçen (üstte, sonra eklenir)
            // geçiş anı beyaz flaş (en üstte)
            var f = new GameObject("flash", typeof(Image));
            var frt = f.GetComponent<RectTransform>();
            frt.SetParent(_cutPanel, false); UIFactory.Stretch(frt);
            _cutFlash = f.GetComponent<Image>();
            _cutFlash.color = new Color(1, 1, 1, 0f); _cutFlash.raycastTarget = false;
            _cutPanel.gameObject.SetActive(false);
        }

        RectTransform MakeCar(Transform parent, out Image body)
        {
            var go = new GameObject("car", typeof(RectTransform));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(150, 64);

            var b = new GameObject("body", typeof(Image));
            var brt = b.GetComponent<RectTransform>();
            brt.SetParent(go.transform, false); UIFactory.Stretch(brt);
            body = b.GetComponent<Image>(); body.sprite = UIFactory.Knob(); body.color = Color.white;

            var cp = new GameObject("cockpit", typeof(Image));
            var cprt = cp.GetComponent<RectTransform>();
            cprt.SetParent(go.transform, false);
            cprt.anchorMin = cprt.anchorMax = cprt.pivot = new Vector2(0.5f, 0.5f);
            cprt.sizeDelta = new Vector2(34, 34); cprt.anchoredPosition = new Vector2(12, 0);
            var ci = cp.GetComponent<Image>(); ci.sprite = UIFactory.Knob();
            ci.color = new Color(0, 0, 0, 0.55f);
            return rt;
        }

        void StartCutscene(Pass p)
        {
            _cutActive = true; _cutTime = 0f; _cutDrs = p.drs;
            _carABody.color = UIFactory.TeamColor(Team(p.passer));
            _carBBody.color = UIFactory.TeamColor(Team(p.passed));
            string pn = _name.GetValueOrDefault(p.passer, p.passer);
            string qn = _name.GetValueOrDefault(p.passed, p.passed);
            _cutCaption.text = $"{pn}, {qn}'i geçti!" + (p.drs ? "   (DRS)" : "");
            _cutCaption.rectTransform.localScale = Vector3.zero;   // pop için
            _cutStrip.localScale = Vector3.one;
            _cutFlash.color = new Color(1, 1, 1, 0f);
            _cutPanel.gameObject.SetActive(true);
            UpdateCutscene();
        }

        // geçiş anı (araçlar yan yana) yaklaşık t=0.5
        const float PASS_T = 0.5f;

        void UpdateCutscene()
        {
            float t = Mathf.Clamp01(_cutTime / CUT_DUR);
            float lane = 0.20f * STRIP_H;

            // geçilen araç: alt şeritte yavaşça öne süzülür
            _carB.anchoredPosition = new Vector2(Mathf.Lerp(-0.05f, 0.22f, t) * STRIP_W, -lane);
            // geçen araç: x ease-out (hızlı çıkış, yumuşak oturma), y şerit değişimi ease-out-back
            float ax = Mathf.Lerp(-0.48f, 0.42f, EaseOutCubic(t)) * STRIP_W;
            float ay = Mathf.Lerp(-lane, lane, EaseOutBack(Mathf.Clamp01(t / 0.5f)));
            _carA.anchoredPosition = new Vector2(ax, ay);

            // caption pop (overshoot, ilk 0.28 sn)
            _cutCaption.rectTransform.localScale =
                Vector3.one * EaseOutBack(Mathf.Clamp01(_cutTime / 0.28f));

            // geçiş anı: flaş + kamera punch
            float hit = Pulse(t, PASS_T, 0.16f);
            _cutFlash.color = new Color(1, 1, 1, 0.45f * Pulse(t, PASS_T, 0.06f));
            _cutStrip.localScale = Vector3.one * (1f + 0.06f * hit);

            // hız çizgileri: kaydır + geçiş anında belirginleş (DRS ise camgöbeği)
            Color lineCol = _cutDrs ? new Color(0.3f, 0.9f, 1f) : Color.white;
            float a = 0.55f * hit;
            for (int i = 0; i < _speedLines.Count; i++)
            {
                var rt = _speedLines[i].rectTransform;
                float x = Mathf.Repeat(-_cutTime * (1000f + i * 60f) + i * 230f, STRIP_W) - STRIP_W * 0.5f;
                rt.anchoredPosition = new Vector2(x, rt.anchoredPosition.y);
                _speedLines[i].color = new Color(lineCol.r, lineCol.g, lineCol.b, a);
            }
        }

        static float EaseOutCubic(float t) => 1f - Mathf.Pow(1f - t, 3f);
        static float EaseOutBack(float t)
        {
            const float c1 = 1.70158f, c3 = c1 + 1f;
            return 1f + c3 * Mathf.Pow(t - 1f, 3f) + c1 * Mathf.Pow(t - 1f, 2f);
        }
        static float Pulse(float t, float center, float width) =>
            Mathf.Exp(-((t - center) * (t - center)) / (width * width));

        // --------------------------------------------------------- oynatma

        public override void Tick(float dt)
        {
            if (!_ready)
            {
                if (_map == null || _map.rect.width < 2) return;   // düzen oturmadı
                LayoutTrack();
                _ready = true;
            }

            // sollama animasyonu: aktifse oynat, değilse kuyruktakini başlat
            if (_cutActive)
            {
                _cutTime += dt;
                UpdateCutscene();
                if (_cutTime >= CUT_DUR + CUT_HOLD)
                {
                    _cutActive = false;
                    _cutPanel.gameObject.SetActive(false);
                }
            }
            else if (_cutQueue.Count > 0 && !_finished)
            {
                StartCutscene(_cutQueue.Dequeue());
            }

            // noktaları hedef açıya doğru yumuşat
            float rx = _map.rect.width * 0.5f - 60f;
            float ry = _map.rect.height * 0.5f - 60f;
            float k = 1f - Mathf.Exp(-dt * 6f);
            foreach (var kv in _dot)
            {
                if (!_tgt.ContainsKey(kv.Key)) continue;
                _ang[kv.Key] = Mathf.LerpAngle(_ang[kv.Key], _tgt[kv.Key], k);
                float a = _ang[kv.Key] * Mathf.Deg2Rad;
                kv.Value.anchoredPosition = new Vector2(rx * Mathf.Cos(a), ry * Mathf.Sin(a));
            }

            if (_playing && !_finished && _ready && !_cutActive && _cutQueue.Count == 0)
            {
                _acc += dt;
                if (_acc >= _speeds[_speedIdx])
                {
                    _acc = 0f;
                    GoToLap(_curLap + 1, true);
                }
            }
        }

        void GoToLap(int L, bool allowCut = false)
        {
            L = Mathf.Clamp(L, 0, _lapCount);
            if (L == _curLap) { if (L >= _lapCount) Finish(); return; }
            _curLap = L;
            _lapLabel.text = $"Tur {L} / {_lapCount}";

            var order = _pos[L];
            var present = new HashSet<string>(order);

            // tower — koşanlar üstte (P1..Pn), DNF olanlar altta sabit "OUT";
            // toplam hep 22, iki sütuna 11+11 bölünür.
            var rows = new List<string>();
            for (int i = 0; i < order.Count; i++)
            {
                string id = order[i];
                string nm = _name.TryGetValue(id, out var n) ? n : id;
                string col = ColorUtility.ToHtmlStringRGB(UIFactory.TeamColor(Team(id)));
                string row = $"P{i + 1,2} <color=#{col}>{nm}</color>";
                if (_mine.Contains(id)) row = $"<b>{row} (SEN)</b>";
                rows.Add(row);
            }
            foreach (var id in _pos[0])   // başlangıç kadrosundan düşenler = DNF
            {
                if (present.Contains(id)) continue;
                string nm = _name.TryGetValue(id, out var n) ? n : id;
                string row = $"OUT <color=#777777>{nm}</color>";
                if (_mine.Contains(id)) row = $"<b>{row} (SEN)</b>";
                rows.Add(row);
            }
            var sbL = new System.Text.StringBuilder();
            var sbR = new System.Text.StringBuilder();
            for (int i = 0; i < rows.Count; i++)
                (i < 11 ? sbL : sbR).AppendLine(rows[i]);
            _towerL.text = sbL.ToString();
            _towerR.text = sbR.ToString();

            // nokta hedefleri + DNF gizleme
            foreach (var kv in _dot)
            {
                bool inRace = present.Contains(kv.Key);
                kv.Value.gameObject.SetActive(inRace);
                if (inRace)
                {
                    int rank = order.IndexOf(kv.Key);
                    _tgt[kv.Key] = AngleForRank(rank);
                    if (_num.TryGetValue(kv.Key, out var t)) t.text = (rank + 1).ToString();
                }
            }

            // olay şeridi: bu tura kadarki anlamlı olayları ekle
            while (_evIdx < _events.Count && (int?)_events[_evIdx]["lap"] <= L)
            {
                var e = _events[_evIdx]; _evIdx++;
                string type = (string)e["type"];
                if (Meaningful(type))
                {
                    _tickLines.Add($"T{(int?)e["lap"]:00} {Names(San((string)e["msg"]))}");
                    if (_tickLines.Count > 7) _tickLines.RemoveAt(0);
                }
                // sollama: oyuncunun pilotu karıştıysa animasyon kuyruğuna al
                if (type == "OVERTAKE" && allowCut && _animOn)
                {
                    string pr = (string)e["driver"], ps = (string)e["passed"];
                    if (_mine.Contains(pr) || _mine.Contains(ps))
                        _cutQueue.Enqueue(new Pass { passer = pr, passed = ps,
                                                     drs = (bool?)e["drs"] ?? false });
                }
            }
            _ticker.text = string.Join("\n", _tickLines);

            if (L >= _lapCount) Finish();
        }

        void Finish()
        {
            if (_finished) return;
            _finished = true; _playing = false; RefreshControls();
            if (_resultsPanel) _resultsPanel.gameObject.SetActive(true);

            // Sol sütun: yarış sonucu
            var sb = new System.Text.StringBuilder();
            foreach (var c in (JArray)((JObject)_msg["result"])["classification"])
            {
                string id = (string)c["driver_id"];
                string nm = _name.TryGetValue(id, out var n) ? n : id;
                string col = ColorUtility.ToHtmlStringRGB(UIFactory.TeamColor(Team(id)));
                string mark = _mine.Contains(id) ? " (SEN)" : "";
                string line = (string)c["status"] == "FIN"
                    ? $"P{c["position"],2} <color=#{col}>{nm}</color>{mark}"
                    : $"DNF <color=#{col}>{nm}</color> [{c["dnf_detail"] ?? c["dnf_cause"]}]{mark}";
                if (_mine.Contains(id)) line = $"<b>{line}</b>";
                sb.AppendLine(line);
            }
            _results.text = sb.ToString();

            // Sağ sütun: o anki şampiyona (takımlar)
            var cb = new System.Text.StringBuilder("ŞAMPİYONA (takımlar)\n\n");
            if (App.LastStandings?["teams"] is JArray teams)
            {
                var sd = App.StaticData;
                int pos = 1;
                foreach (var r in teams)
                {
                    string tid = (string)r[0];
                    string tn = (string)sd?["teams"]?[tid]?["name"] ?? tid;
                    string col = ColorUtility.ToHtmlStringRGB(UIFactory.TeamColor(tid));
                    string mk = tid == App.MyTeamId ? " (SEN)" : "";
                    string line = $"{pos,2}. <color=#{col}>{tn}</color> — {(int?)r[1] ?? 0}{mk}";
                    if (tid == App.MyTeamId) line = $"<b>{line}</b>";
                    cb.AppendLine(line);
                    pos++;
                }
            }
            if (_champ) _champ.text = cb.ToString();
        }

        void SkipToEnd()
        {
            _playing = false;
            _cutQueue.Clear();
            if (_cutActive) { _cutActive = false; _cutPanel.gameObject.SetActive(false); }
            GoToLap(_lapCount);
        }

        void CycleSpeed()
        {
            _speedIdx = (_speedIdx + 1) % _speeds.Length;
            RefreshControls();
        }

        void RefreshControls()
        {
            SetBtn(_playBtn, _finished ? "Bitti" : _playing ? "Duraklat" : "Oynat");
            SetBtn(_speedBtn, "Hiz " + (_speedIdx == 0 ? "1x" : _speedIdx == 1 ? "2x" : "4x"));
            SetBtn(_animBtn, _animOn ? "Anim: Acik" : "Anim: Kapali");
        }

        // --------------------------------------------------------- yardımcılar

        float AngleForRank(int rank) => 90f - rank * (360f / Mathf.Max(1, _total));

        string Team(string id) => _team.TryGetValue(id, out var t) ? t : null;

        static bool Meaningful(string type) =>
            type == "OVERTAKE" || type == "PIT" || type == "SLOW_PIT" || type == "DNF" ||
            type == "SC" || type == "VSC" || type == "RED_FLAG" || type == "LEAD" ||
            type == "DAMAGE" || type == "SPIN" || type == "RESTART";

        string Names(string msg)
        {
            if (string.IsNullOrEmpty(msg)) return msg;
            foreach (var kv in _name) msg = msg.Replace(kv.Key, kv.Value);
            return msg;
        }

        // Fontta olmayan tüm sembol/emoji'leri ayıkla; Türkçe harfler (<U+2000) kalır.
        static string San(string s)
        {
            if (string.IsNullOrEmpty(s)) return s;
            s = s.Replace("→", ">");
            var sb = new System.Text.StringBuilder(s.Length);
            foreach (char c in s)
                if (c == '\n' || (c >= ' ' && c <= '\u024F')) sb.Append(c);  // ASCII+Turkce
            return sb.ToString().Replace("  ", " ").Trim();
        }

        RectTransform MakeDot(string id)
        {
            bool player = _mine.Contains(id);
            float size = player ? 52 : 34;
            var go = new GameObject("dot_" + id, typeof(RectTransform));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(_map, false);
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(size, size);

            if (player)   // beyaz halka ile vurgula
            {
                var ol = new GameObject("ol", typeof(Image));
                var olrt = ol.GetComponent<RectTransform>();
                olrt.SetParent(go.transform, false);
                UIFactory.Stretch(olrt, -7);
                var oi = ol.GetComponent<Image>(); oi.sprite = UIFactory.Knob(); oi.color = Color.white;
            }
            var c = new GameObject("c", typeof(Image));
            var crt = c.GetComponent<RectTransform>();
            crt.SetParent(go.transform, false); UIFactory.Stretch(crt);
            var im = c.GetComponent<Image>(); im.sprite = UIFactory.Knob();
            im.color = UIFactory.TeamColor(Team(id));

            var lbl = new GameObject("n", typeof(TextMeshProUGUI));
            var lrt = lbl.GetComponent<RectTransform>();
            lrt.SetParent(go.transform, false); UIFactory.Stretch(lrt);
            var t = lbl.GetComponent<TextMeshProUGUI>();
            t.alignment = TextAlignmentOptions.Center; t.fontSize = player ? 24 : 18;
            t.color = Color.black; t.fontStyle = FontStyles.Bold; t.text = "";
            _num[id] = t;
            return rt;
        }

        // dekoratif pist halkası (bir kez, harita boyutu belli olunca)
        void LayoutTrack()
        {
            float rx = _map.rect.width * 0.5f - 60f;
            float ry = _map.rect.height * 0.5f - 60f;
            for (int i = 0; i < 48; i++)
            {
                float a = (i / 48f) * Mathf.PI * 2f;
                var g = new GameObject("path", typeof(Image));
                var grt = g.GetComponent<RectTransform>();
                grt.SetParent(_map, false);
                grt.SetAsFirstSibling();   // noktaların arkasında
                grt.anchorMin = grt.anchorMax = grt.pivot = new Vector2(0.5f, 0.5f);
                grt.sizeDelta = new Vector2(8, 8);
                grt.anchoredPosition = new Vector2(rx * Mathf.Cos(a), ry * Mathf.Sin(a));
                var im = g.GetComponent<Image>(); im.sprite = UIFactory.Knob();
                im.color = new Color(1, 1, 1, 0.12f);
            }
        }

        static void SetBtn(Button b, string text)
        {
            if (b) b.GetComponentInChildren<TMP_Text>().text = text;
        }
    }
}
