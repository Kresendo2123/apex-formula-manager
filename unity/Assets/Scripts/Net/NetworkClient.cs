// Apex Formula Manager — WebSocket istemcisi (Faz 2, dilim 1).
//
// Sahnedeki tek bir kalıcı nesnedir (DontDestroyOnLoad). Sunucuya bağlanır,
// gelen JSON mesajlarını "ev" alanına göre ana thread'de olaylara dağıtır,
// "op" mesajlarını gönderir. Yarış içi etkileşim yok: bu katman yalnız lobi +
// faz mesajlarının taşıyıcısıdır.
//
// Bağımlılıklar:
//   - NativeWebSocket  (git: https://github.com/endel/NativeWebSocket.git#upm)
//   - Newtonsoft.Json  (Package Manager: com.unity.nuget.newtonsoft-json)
//
// Kullanım:
//   NetworkClient.Instance.On(Protocol.EV_ROOM, OnRoom);
//   await NetworkClient.Instance.Connect("ws://127.0.0.1:8000/ws");
//   NetworkClient.Instance.Send(Protocol.OP_CREATE_ROOM,
//       new { name = "Ayşe", opts = new { num_races = 5, turn_seconds = 90 } });
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using NativeWebSocket;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Apex.Net
{
    public class NetworkClient : MonoBehaviour
    {
        public static NetworkClient Instance { get; private set; }

        WebSocket _ws;
        readonly Dictionary<string, Action<JObject>> _handlers = new();

        // joined olayında doldurulur — yeniden bağlanma/kolaylık için.
        public string PlayerId    { get; private set; }
        public string RejoinToken { get; private set; }
        public string RoomCode    { get; private set; }

        public bool IsConnected => _ws != null && _ws.State == WebSocketState.Open;

        // Bağlantı yaşam döngüsü olayları (hepsi ana thread'de tetiklenir).
        public event Action OnConnected;
        public event Action<string> OnClosed;     // kapanış sebebi/kodu
        public event Action<string> OnNetError;   // taşıma hatası metni
        public event Action<JObject> OnAnyMessage; // her gelen mesaj (log/teşhis)

        void Awake()
        {
            if (Instance != null && Instance != this) { Destroy(gameObject); return; }
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }

        // ---- abonelik. ev tipine göre işleyici tak/çıkar (ileri uyumlu: bilinmeyen ev yok sayılır).
        public void On(string ev, Action<JObject> handler)
        {
            _handlers.TryGetValue(ev, out var cur);
            _handlers[ev] = cur + handler;
        }

        public void Off(string ev, Action<JObject> handler)
        {
            if (_handlers.TryGetValue(ev, out var cur))
                _handlers[ev] = cur - handler;
        }

        // ---- bağlan
        public async Task Connect(string url)
        {
            if (_ws != null) { await Close(); }

            _ws = new WebSocket(url);
            _ws.OnOpen    += () => OnConnected?.Invoke();
            _ws.OnError   += (e) => OnNetError?.Invoke(e);
            _ws.OnClose   += (c) => OnClosed?.Invoke(c.ToString());
            _ws.OnMessage += OnRawMessage;

            // Bloklamaz; bağlantı OnOpen ile haber verir.
            _ = _ws.Connect();
        }

        public async Task Close()
        {
            if (_ws != null)
            {
                try { await _ws.Close(); } catch { /* zaten kapalı olabilir */ }
                _ws = null;
            }
        }

        // ---- gönder
        public void Send(string op) => Send(op, null);

        public void Send(string op, object payload)
        {
            if (!IsConnected)
            {
                Debug.LogWarning($"[Net] bağlı değilken gönderim denendi: {op}");
                return;
            }
            JObject msg = payload == null ? new JObject() : JObject.FromObject(payload);
            msg["op"] = op;
            _ws.SendText(msg.ToString(Formatting.None));
        }

        // ---- gelen mesaj (NativeWebSocket bunu DispatchMessageQueue içinde, ana thread'de çağırır)
        void OnRawMessage(byte[] bytes)
        {
            JObject msg;
            try
            {
                string text = System.Text.Encoding.UTF8.GetString(bytes);
                msg = JObject.Parse(text);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[Net] çözülemeyen mesaj: {e.Message}");
                return;
            }

            string ev = (string)msg["ev"];
            if (ev == Protocol.EV_JOINED)
            {
                PlayerId    = (string)msg["player_id"];
                RejoinToken = (string)msg["rejoin_token"];
                RoomCode    = (string)msg["room"]?["code"];
            }

            OnAnyMessage?.Invoke(msg);
            if (ev != null && _handlers.TryGetValue(ev, out var cb))
                cb?.Invoke(msg);
        }

        void Update()
        {
#if !UNITY_WEBGL || UNITY_EDITOR
            _ws?.DispatchMessageQueue();
#endif
        }

        async void OnApplicationQuit() => await Close();
        async void OnDestroy()         { if (Instance == this) await Close(); }
    }
}
