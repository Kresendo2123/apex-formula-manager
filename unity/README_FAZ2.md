# Faz 2 — Unity İstemci (kod-güdümlü, "B yöntemi")

Arayüzün tamamı **çalışırken koddan** kurulur. Editörde sürükle-bırak / slot
doldurma **yoktur**: boş bir nesneye tek bir bileşen ekler, Play'e basarsın.
Yeni ekran = `Assets`'e yeni bir `.cs` dosyası kopyalamak.

Şu an kapsanan akış:
- **Lobi**: bağlan → oda kur / kodla katıl → **gerçek takım seçici** → hazır → başlat
- **Aero ekranı**: pist/hava bilgisi + 1-5 aero seviyesi + gönder
- Strateji / geliştirme / sezon sonu: geçici **bilgi ekranı** (sonuçları günlükler,
  oyunu kilitlememek için "boş gönder/geç" düğmesi). Tam halleri sonraki dilimlerde.

Hedef: **Unity 6 (6000.x)**.

---

## 1) Paketler (bir kez)

**Window ▸ Package Manager**:
- **+** ▸ *Add package by name* → `com.unity.nuget.newtonsoft-json` → Add
- **+** ▸ *Add package from git URL* → `https://github.com/endel/NativeWebSocket.git#upm` → Add

İlk TMP bileşeninde Unity *Import TMP Essentials* derse → **Import**.

## 2) Scriptleri kopyala

Bu repodaki `unity/Assets/Scripts/` klasörünü Unity projenin `Assets/` altına
kopyala. Dosyalar:
- `Net/Protocol.cs` — sunucu sözleşmesi sabitleri
- `Net/NetworkClient.cs` — WebSocket taşıma katmanı (singleton)
- `UI/UIFactory.cs` — koddan UI üreten yardımcılar
- `UI/AppRoot.cs` — uygulama kökü + ekran yönlendirici + lobi/aero/bilgi ekranları

> Eski `UI/LobbyController.cs` artık YOK (silindi). Daha önce dilim 1'i
> kurduysan, sahnedeki **Canvas**, **Network** ve eski `LobbyController`
> nesnelerini **sil**. (EventSystem kalabilir; yoksa AppRoot kendi kurar.)

## 3) Sahne kurulumu (tek adım!)

1. Hierarchy ▸ sağ tık ▸ **Create Empty** → adı `App`.
2. `App` seçiliyken **Add Component** → `AppRoot` → ekle.
3. (İsteğe bağlı) Inspector'da `Default Url` alanını değiştirebilirsin
   (varsayılan `ws://127.0.0.1:8000/ws`).

Başka hiçbir şey kurmana gerek yok — Canvas/UI/EventSystem hepsi kodla doğuyor.

## 4) Sunucuyu çalıştır

Repo kökünde:
```bash
cd /Users/bilgehan/Desktop/Formula_find_the_formula
.venv312/bin/uvicorn server.app:app          # ws://127.0.0.1:8000/ws
```
Terminali açık bırak.

## 5) Test

- Unity ▸ **Play** → "Bağlan" → "Yeni Oda Kur" → oda kodu çıkar.
- İkinci oyuncu: ayrı terminalde `.venv312/bin/python play_online.py --name Bora`
  (ya da ikinci bir Unity örneği) → aynı koda katıl.
- İki taraf da listeden **takım** seçer (dolu takımlar gri/kapalı), "Hazır" olur.
- **Host** "▶ Başlat" → ekran **Aero**'ya geçer. Aero seviyesini ‹/› ile seç,
  "Gönder". İki taraf da gönderince → sıralama koşar → **Strateji** bilgi ekranı.
- Strateji'de "Boş strateji gönder", geliştir'de "Geliştirme yapmadan geç" ile
  sezonu sonuna kadar ilerletebilirsin; yarış sonuçları günlüğe düşer.

> **Cihazda test:** telefon/WebGL `127.0.0.1`'e ulaşamaz. Sunucuyu
> `uvicorn server.app:app --host 0.0.0.0` ile çalıştır, istemcide makinenin LAN
> IP'sini kullan (`ws://192.168.x.x:8000/ws`).

## Notlar / sonraki dilimler

- Görsel cila (yerleşim/font/renk) bilinçli olarak ertelendi: önce tüm akış
  işlevsel olsun, sonra güzelleştirme dilimi.
- Sıradaki tam ekranlar: **strateji** (kart + sürüş stili + pitwall) → **yarış
  replay** (2D timing tower + pist haritası, `result.events` akışından) →
  **geliştirme** → **klasman/sezon sonu**. Hepsi `docs/EVENT_SCHEMA.md`'den beslenir.
- ✓ gibi bazı simgeler varsayılan fontta olmayabilir (zararsız uyarı).
