// Apex Formula Manager — Geliştirme ekranı (Faz 2, dilim 4).
//
// Yarışlar arası: sınırlı geliştirme hakkını (upgrades_per_race) araç/pilot
// statlarına dağıt + bir tesis geliştirmesi seç. Sunucuya submit_upgrades ile
// gider: spends=[{kind:"car",stat} | {kind:"driver",driver_id,stat}], facility.
using System.Collections.Generic;
using System.Linq;
using Apex.Net;
using Newtonsoft.Json.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Apex.UI
{
    public class UpgradeScreen : Screen
    {
        readonly JObject _phase;
        int _max, _used;
        string _facility;
        readonly List<JObject> _spends = new();
        readonly Dictionary<string, int> _count = new();
        readonly Dictionary<string, TMP_Text> _cnt = new();
        TMP_Text _budget, _status;

        public UpgradeScreen(AppRoot app, JObject phase) : base(app) { _phase = phase; }

        public override void Build(Transform parent)
        {
            int raceNo = (int?)_phase["race_no"] ?? 1;
            int total  = (int?)_phase["total_races"] ?? 1;
            var sd = App.StaticData;
            _max = (int?)sd?["upgrades_per_race"] ?? 2;

            JToken sheet = (_phase["teams"] != null && !string.IsNullOrEmpty(App.MyTeamId))
                ? _phase["teams"][App.MyTeamId] : null;

            UIFactory.Label(parent, $"Yarış {raceNo}/{total} — Geliştirme", 46,
                            TextAlignmentOptions.Center, UIFactory.Accent);
            _budget = UIFactory.Label(parent, "", 30, TextAlignmentOptions.Center);
            UIFactory.Label(parent, "Her stata istediğin kadar '+' bas (toplam hakkın kadar).",
                            22, TextAlignmentOptions.Center, new Color(0.72f, 0.72f, 0.72f));

            // araç
            string[] carStats = Strs(sd?["car_stats"]) ??
                new[] { "acceleration", "top_speed", "grip", "reliability", "tire_consumption" };
            var car = sheet?["car"] as JObject;
            UIFactory.Label(parent, "ARAÇ", 28, TextAlignmentOptions.Center, UIFactory.Accent);
            foreach (var st in carStats) StatRow(parent, "car", null, st, car);

            // pilotlar
            string[] drvStats = Strs(sd?["driver_stats"]) ??
                new[] { "pace", "consistency", "attack_defense", "tire_management" };
            if (sheet?["drivers"] is JObject drivers)
                foreach (var dp in drivers)
                {
                    string did = dp.Key;
                    string nm = (string)sd?["drivers"]?[did] ?? did;
                    UIFactory.Label(parent, "PİLOT — " + nm, 28,
                                    TextAlignmentOptions.Center, UIFactory.Accent);
                    foreach (var st in drvStats) StatRow(parent, "driver", did, st, dp.Value as JObject);
                }

            // tesis
            string[] facIds = Strs(sd?["facilities"]) ??
                new[] { "wind_tunnel", "simulator", "factory" };
            var facLabels = new List<string> { "(tesis geliştirme yok)" };
            facLabels.AddRange(facIds.Select(FacLabel));
            UIFactory.Cycler(parent, "Tesis geliştirme:", facLabels.ToArray(), 0,
                i => _facility = i == 0 ? null : facIds[i - 1]);

            _status = UIFactory.Label(parent, "", 26, TextAlignmentOptions.Center);

            UIFactory.Button(parent, "Sıfırla", () =>
            {
                _spends.Clear(); _used = 0;
                foreach (var k in _count.Keys.ToList()) _count[k] = 0;
                RefreshAll();
            });
            UIFactory.Button(parent, "Gönder", () =>
            {
                var arr = new JArray();
                foreach (var s in _spends) arr.Add(s);
                Net.Send(Protocol.OP_SUBMIT_UPGRADES, new
                {
                    spends = arr,
                    facility = _facility != null ? (JToken)_facility : JValue.CreateNull(),
                });
                _status.text = "Gönderiliyor…";
            }, color: UIFactory.Accent);

            Sub(Protocol.EV_SUBMIT_OK, _ => _status.text = "Gönderildi — diğer oyuncular bekleniyor…");
            Sub(Protocol.EV_AUTO_FILLED, _ => _status.text = "Süre doldu — otomatik dolduruldu.");
            Sub(Protocol.EV_ERROR, m => _status.text = "Hata: " +
                Protocol.FriendlyError((string)m["code"], (string)m["msg"]));

            RefreshAll();
        }

        void StatRow(Transform parent, string kind, string driverId, string stat, JObject stats)
        {
            string key = (driverId ?? "car") + ":" + stat;
            _count[key] = 0;
            double val = stats != null ? (double?)stats[stat] ?? 0 : 0;

            var row = new GameObject("row", typeof(HorizontalLayoutGroup), typeof(LayoutElement));
            row.transform.SetParent(parent, false);
            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.spacing = 10; h.childAlignment = TextAnchor.MiddleCenter;
            h.childControlWidth = true; h.childControlHeight = true;
            h.childForceExpandWidth = false; h.childForceExpandHeight = true;
            var le = row.GetComponent<LayoutElement>(); le.minHeight = 84; le.preferredHeight = 84;

            var lbl = UIFactory.Label(row.transform, $"{StatLabel(stat)}: {val:0.#}", 26);
            UIFactory.Flex(lbl.gameObject);
            var cnt = UIFactory.Label(row.transform, "", 26, TextAlignmentOptions.Center, UIFactory.Accent);
            UIFactory.Width(cnt.gameObject, 90); _cnt[key] = cnt;
            var add = UIFactory.Button(row.transform, "+", () =>
            {
                if (_used >= _max) { _status.text = $"Hakkın doldu ({_max})."; return; }
                _used++; _count[key]++;
                var sp = new JObject { ["kind"] = kind, ["stat"] = stat };
                if (driverId != null) sp["driver_id"] = driverId;
                _spends.Add(sp);
                RefreshAll();
            }, 80);
            UIFactory.Width(add.gameObject, 110);
        }

        void RefreshAll()
        {
            if (_budget) _budget.text = $"Geliştirme hakkı: {_used} / {_max}";
            foreach (var kv in _cnt)
                if (kv.Value) kv.Value.text = _count[kv.Key] > 0 ? "+" + _count[kv.Key] : "";
        }

        static string StatLabel(string id) => id switch
        {
            "acceleration" => "Hızlanma",
            "top_speed" => "Maks. hız",
            "grip" => "Tutuş",
            "reliability" => "Güvenilirlik",
            "tire_consumption" => "Lastik tüketimi",
            "pace" => "Hız",
            "consistency" => "İstikrar",
            "attack_defense" => "Hücum/Defans",
            "tire_management" => "Lastik yönetimi",
            _ => id,
        };

        static string FacLabel(string id) => id switch
        {
            "wind_tunnel" => "Rüzgar tüneli",
            "simulator" => "Simülatör",
            "factory" => "Fabrika",
            _ => id,
        };

        static string[] Strs(JToken t) =>
            t is JArray a ? a.Select(x => (string)x).ToArray() : null;
    }
}
