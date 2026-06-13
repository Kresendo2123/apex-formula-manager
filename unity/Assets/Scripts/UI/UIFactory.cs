// Apex Formula Manager — kod-güdümlü UI fabrikası (Faz 2, dilim 2).
//
// Tüm arayüzü çalışırken koddan kurar; editörde sürükle-bırak YOK. Ekranlar
// (LobbyScreen, AeroScreen, ...) bu yardımcılarla widget üretir. Görsel cila
// sonraki bir dilime bırakıldı — burada amaç işlevsel, sade bir arayüz.
using System;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Apex.UI
{
    public static class UIFactory
    {
        public static readonly Color Bg     = new Color(0.10f, 0.12f, 0.16f);
        public static readonly Color Panel  = new Color(0.16f, 0.19f, 0.24f);
        public static readonly Color Accent = new Color(0.20f, 0.55f, 0.90f);
        public static readonly Color Btn    = new Color(0.22f, 0.25f, 0.31f);
        public static readonly Color Text   = Color.white;

        // Ekran-uzayı bir Canvas + (gerekirse) EventSystem üretir.
        public static Canvas CreateCanvas(string name = "UICanvas")
        {
            var go = new GameObject(name, typeof(Canvas), typeof(CanvasScaler),
                                    typeof(GraphicRaycaster));
            var canvas = go.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = go.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);   // yatay/mobil
            scaler.matchWidthOrHeight = 1f;   // yüksekliğe göre ölçekle
            return canvas;
        }

        // Tüm yüzeyi kaplayan, dikey dizen bir panel (ekran kökü).
        public static RectTransform Column(Transform parent, Color? color = null,
                                           int padding = 40, float spacing = 16)
        {
            var go = new GameObject("Column", typeof(Image), typeof(VerticalLayoutGroup),
                                    typeof(ContentSizeFitter));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            Stretch(rt);
            go.GetComponent<Image>().color = color ?? Bg;
            var v = go.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(padding, padding, padding, padding);
            v.spacing = spacing;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true; v.childControlHeight = true;
            v.childForceExpandWidth = true; v.childForceExpandHeight = false;
            go.GetComponent<ContentSizeFitter>().enabled = false;
            return rt;
        }

        // Kaydırılabilir dikey içerik alanı (ekran kökü). İçerik taşınca dikey kayar
        // — uzun listeler (11 takım) + alttaki düğmeler hep erişilebilir kalır.
        public static RectTransform ScrollColumn(Transform parent, Color? bg = null,
                                                 int padding = 40, float spacing = 16)
        {
            var scrollGO = new GameObject("Scroll", typeof(Image), typeof(ScrollRect));
            var scrollRT = scrollGO.GetComponent<RectTransform>();
            scrollRT.SetParent(parent, false);
            Stretch(scrollRT);
            scrollGO.GetComponent<Image>().color = bg ?? Bg;
            var scroll = scrollGO.GetComponent<ScrollRect>();
            scroll.horizontal = false; scroll.vertical = true;
            scroll.movementType = ScrollRect.MovementType.Clamped;
            scroll.scrollSensitivity = 40;

            var vpGO = new GameObject("Viewport", typeof(RectMask2D));
            var vpRT = vpGO.GetComponent<RectTransform>();
            vpRT.SetParent(scrollGO.transform, false);
            Stretch(vpRT);
            scroll.viewport = vpRT;

            var contentGO = new GameObject("Content", typeof(VerticalLayoutGroup),
                                           typeof(ContentSizeFitter));
            var rt = contentGO.GetComponent<RectTransform>();
            rt.SetParent(vpGO.transform, false);
            rt.anchorMin = new Vector2(0, 1); rt.anchorMax = new Vector2(1, 1);
            rt.pivot = new Vector2(0.5f, 1);
            rt.offsetMin = Vector2.zero; rt.offsetMax = Vector2.zero;
            var v = contentGO.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(padding, padding, padding, padding);
            v.spacing = spacing;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true; v.childControlHeight = true;
            v.childForceExpandWidth = true; v.childForceExpandHeight = false;
            contentGO.GetComponent<ContentSizeFitter>().verticalFit =
                ContentSizeFitter.FitMode.PreferredSize;
            scroll.content = rt;
            return rt;
        }

        // Kaydırmasız tam ekran kök (yarış gibi sabit düzenli ekranlar için).
        public static RectTransform FullRect(Transform parent, Color? bg = null)
        {
            var go = new GameObject("Screen", typeof(Image));
            var rt = go.GetComponent<RectTransform>();
            rt.SetParent(parent, false);
            Stretch(rt);
            go.GetComponent<Image>().color = bg ?? Bg;
            return rt;
        }

        public static TMP_Text Label(Transform parent, string text, int size = 32,
                                     TextAlignmentOptions align = TextAlignmentOptions.Left,
                                     Color? color = null)
        {
            var go = new GameObject("Label", typeof(TextMeshProUGUI));
            go.transform.SetParent(parent, false);
            var t = go.GetComponent<TextMeshProUGUI>();
            t.text = text; t.fontSize = size; t.color = color ?? Text;
            t.alignment = align; t.textWrappingMode = TextWrappingModes.Normal;
            // Yükseklik içeriğe göre: minHeight bir satır, preferredHeight=-1 ile
            // dikey düzen TMP'nin gerçek (çok satırlı) yüksekliğini kullanır —
            // böylece uzun listeler alttaki öğelerle çakışmaz.
            var le = go.GetComponent<LayoutElement>() ?? go.AddComponent<LayoutElement>();
            le.minHeight = size + 12; le.preferredHeight = -1; le.flexibleHeight = 0;
            return t;
        }

        public static Button Button(Transform parent, string label, Action onClick,
                                    int height = 90, Color? color = null)
        {
            var go = new GameObject("Button", typeof(Image), typeof(Button));
            go.transform.SetParent(parent, false);
            go.GetComponent<Image>().color = color ?? Btn;
            var b = go.GetComponent<Button>();
            if (onClick != null) b.onClick.AddListener(() => onClick());
            var t = Label(go.transform, label, 34, TextAlignmentOptions.Center);
            Stretch(t.rectTransform);
            Pref(go, minH: height);
            return b;
        }

        public static TMP_InputField Input(Transform parent, string placeholder,
                                           string value = "", int height = 80)
        {
            var go = new GameObject("Input", typeof(Image), typeof(TMP_InputField));
            go.transform.SetParent(parent, false);
            go.GetComponent<Image>().color = Color.white;
            var field = go.GetComponent<TMP_InputField>();

            var area = new GameObject("TextArea", typeof(RectMask2D));
            area.transform.SetParent(go.transform, false);
            Stretch(area.GetComponent<RectTransform>(), 12);

            var ph = Label(area.transform, placeholder, 30, TextAlignmentOptions.Left,
                           new Color(0, 0, 0, 0.4f));
            Stretch(ph.rectTransform);
            var txt = Label(area.transform, "", 30, TextAlignmentOptions.Left, Color.black);
            Stretch(txt.rectTransform);

            field.textViewport = area.GetComponent<RectTransform>();
            field.textComponent = txt;
            field.placeholder = ph;
            field.text = value;
            Pref(go, minH: height);
            return field;
        }

        // 1..max tam sayı seçici: "‹  değer  ›" — slider'dan dokunmatikte daha güvenli.
        public static TMP_Text Stepper(Transform parent, string title, int min, int max,
                                       int value, Action<int> onChange)
        {
            int cur = Mathf.Clamp(value, min, max);
            var row = new GameObject("Stepper", typeof(HorizontalLayoutGroup));
            row.transform.SetParent(parent, false);
            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.spacing = 16; h.childAlignment = TextAnchor.MiddleCenter;
            h.childControlWidth = true; h.childControlHeight = true;
            h.childForceExpandWidth = false; h.childForceExpandHeight = true;
            Pref(row, minH: 100);

            TMP_Text val = null;
            void Refresh() { if (val) val.text = cur.ToString(); onChange?.Invoke(cur); }

            var lbl = Label(row.transform, title, 32, TextAlignmentOptions.MidlineRight);
            Flex(lbl.gameObject);
            var minus = Button(row.transform, "-", () => { cur = Mathf.Max(min, cur - 1); Refresh(); }, 90);
            Width(minus.gameObject, 110);
            val = Label(row.transform, cur.ToString(), 44, TextAlignmentOptions.Center, Accent);
            Width(val.gameObject, 120);
            var plus = Button(row.transform, "+", () => { cur = Mathf.Min(max, cur + 1); Refresh(); }, 90);
            Width(plus.gameObject, 110);
            return val;
        }

        // Bir dizi seçenek arasında "<  değer  >" ile dolaşan seçici. Uzun
        // etiketler (strateji kartları) için Stepper'dan uygun: başlık üstte,
        // değer ortada esner. onChange seçili indeksi verir.
        public static void Cycler(Transform parent, string title, string[] labels,
                                  int start, Action<int> onChange)
        {
            int n = Mathf.Max(1, labels.Length);
            int idx = Mathf.Clamp(start, 0, n - 1);

            Label(parent, title, 26, TextAlignmentOptions.Left, Accent);
            var row = new GameObject("Cycler", typeof(HorizontalLayoutGroup));
            row.transform.SetParent(parent, false);
            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.spacing = 10; h.childAlignment = TextAnchor.MiddleCenter;
            h.childControlWidth = true; h.childControlHeight = true;
            h.childForceExpandWidth = false; h.childForceExpandHeight = true;
            Pref(row, minH: 84);

            TMP_Text val = null;
            void Refresh() { val.text = labels[idx]; onChange?.Invoke(idx); }

            var prev = Button(row.transform, "<", () => { idx = (idx - 1 + n) % n; Refresh(); }, 80);
            Width(prev.gameObject, 90);
            val = Label(row.transform, labels[idx], 28, TextAlignmentOptions.Center);
            Flex(val.gameObject);
            var next = Button(row.transform, ">", () => { idx = (idx + 1) % n; Refresh(); }, 80);
            Width(next.gameObject, 90);
            onChange?.Invoke(idx);   // ilk değeri uygula
        }

        // Takım kimliğinden tutarlı bir renk (bilinenler elle, gerisi hash'ten).
        public static Color TeamColor(string teamId)
        {
            switch (teamId)
            {
                case "T_MER": return new Color(0.0f, 0.82f, 0.77f);
                case "T_FER": return new Color(0.90f, 0.10f, 0.12f);
                case "T_MCL": return new Color(1.0f, 0.55f, 0.0f);
                case "T_RBR": return new Color(0.20f, 0.30f, 0.90f);
                case "T_AST": return new Color(0.0f, 0.55f, 0.40f);
                case "T_ALP": return new Color(0.10f, 0.55f, 0.95f);
                case "T_WIL": return new Color(0.20f, 0.45f, 0.95f);
                case "T_HAA": return new Color(0.75f, 0.75f, 0.78f);
            }
            if (string.IsNullOrEmpty(teamId)) return Btn;
            int h = 0; foreach (char c in teamId) h = h * 31 + c;
            return Color.HSVToRGB((Mathf.Abs(h) % 360) / 360f, 0.6f, 0.9f);
        }

        static Sprite _knob;
        public static Sprite Knob()   // yuvarlak nokta sprite'ı (çalışırken üretilir)
        {
            if (_knob != null) return _knob;
            const int R = 64;
            var tex = new Texture2D(R, R, TextureFormat.RGBA32, false);
            float c = (R - 1) / 2f, rad = c;
            var px = new Color32[R * R];
            for (int y = 0; y < R; y++)
                for (int x = 0; x < R; x++)
                {
                    float d = Mathf.Sqrt((x - c) * (x - c) + (y - c) * (y - c));
                    float a = Mathf.Clamp01(rad - d);   // kenar yumuşatma
                    px[y * R + x] = new Color32(255, 255, 255, (byte)(a * 255));
                }
            tex.SetPixels32(px); tex.Apply();
            _knob = Sprite.Create(tex, new Rect(0, 0, R, R), new Vector2(0.5f, 0.5f));
            return _knob;
        }

        // ---- yardımcılar
        public static void Width(GameObject go, float w)
        {
            var le = go.GetComponent<LayoutElement>() ?? go.AddComponent<LayoutElement>();
            le.minWidth = w; le.preferredWidth = w; le.flexibleWidth = 0;
        }

        public static void Flex(GameObject go)
        {
            var le = go.GetComponent<LayoutElement>() ?? go.AddComponent<LayoutElement>();
            le.flexibleWidth = 1;
        }

        public static void Stretch(RectTransform rt, float margin = 0)
        {
            rt.anchorMin = Vector2.zero; rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(margin, margin);
            rt.offsetMax = new Vector2(-margin, -margin);
        }

        static void Pref(GameObject go, float minH)
        {
            var le = go.GetComponent<LayoutElement>() ?? go.AddComponent<LayoutElement>();
            le.minHeight = minH; le.preferredHeight = minH;
        }
    }
}
