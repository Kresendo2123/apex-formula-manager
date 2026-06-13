// Apex Formula Manager — Sezon sonu klasmanı (Faz 2, dilim 5).
//
// phase season_end ile gelen final_standings'i gösterir:
// {drivers: [[id, puan], ...], teams: [[id, puan], ...]} (puana göre sıralı).
// İsimler static_data'dan çözülür; oyuncunun takımı/pilotları vurgulanır.
using System.Collections.Generic;
using System.Linq;
using Apex.Net;
using Newtonsoft.Json.Linq;
using TMPro;
using UnityEngine;

namespace Apex.UI
{
    public class StandingsScreen : Screen
    {
        readonly JObject _phase;

        public StandingsScreen(AppRoot app, JObject phase) : base(app) { _phase = phase; }

        public override void Build(Transform parent)
        {
            var fs = _phase["final_standings"] as JObject ?? _phase;
            var sd = App.StaticData;

            // isim çözücüler
            string DriverName(string id) => (string)sd?["drivers"]?[id] ?? id;
            string TeamName(string id) => (string)sd?["teams"]?[id]?["name"] ?? id;

            // oyuncunun pilotları (vurgu için)
            var mine = new HashSet<string>();
            if (!string.IsNullOrEmpty(App.MyTeamId) && sd?["teams"]?[App.MyTeamId]?["drivers"] is JArray md)
                foreach (var d in md) mine.Add((string)d);

            UIFactory.Label(parent, "SEZON SONU", 50, TextAlignmentOptions.Center, UIFactory.Accent);
            UIFactory.Label(parent, "Şampiyona klasmanı", 28, TextAlignmentOptions.Center);

            UIFactory.Label(parent, "TAKIMLAR", 30, TextAlignmentOptions.Center, UIFactory.Accent);
            Table(parent, fs["teams"] as JArray, TeamName,
                  id => id == App.MyTeamId, id => UIFactory.TeamColor(id));

            UIFactory.Label(parent, "PİLOTLAR", 30, TextAlignmentOptions.Center, UIFactory.Accent);
            Table(parent, fs["drivers"] as JArray, DriverName,
                  id => mine.Contains(id), TeamColorOfDriver);

            UIFactory.Label(parent, "Sezon tamamlandı. (Yeni sezon için sunucuyu yeniden başlat / yeni oda kur.)",
                            22, TextAlignmentOptions.Center, new Color(0.72f, 0.72f, 0.72f));
        }

        Color TeamColorOfDriver(string driverId)
        {
            var teams = App.StaticData?["teams"] as JObject;
            if (teams != null)
                foreach (var t in teams)
                    if (t.Value?["drivers"] is JArray ds && ds.Any(x => (string)x == driverId))
                        return UIFactory.TeamColor(t.Key);
            return UIFactory.Text;
        }

        // [[id, puan], ...] -> sıralı, renkli, oyuncuyu vurgulayan tablo
        static void Table(Transform parent, JArray rows, System.Func<string, string> nameOf,
                          System.Func<string, bool> isMine, System.Func<string, Color> colorOf)
        {
            if (rows == null) return;
            var sb = new System.Text.StringBuilder();
            int pos = 1;
            foreach (var r in rows)
            {
                string id = (string)r[0];
                int pts = (int?)r[1] ?? 0;
                string col = ColorUtility.ToHtmlStringRGB(colorOf(id));
                string line = $"{pos,2}.  <color=#{col}>{nameOf(id)}</color>  —  {pts} puan";
                if (isMine(id)) line = $"<b>{line}  (SEN)</b>";
                sb.AppendLine(line);
                pos++;
            }
            UIFactory.Label(parent, sb.ToString(), 26, TextAlignmentOptions.Left);
        }
    }
}
