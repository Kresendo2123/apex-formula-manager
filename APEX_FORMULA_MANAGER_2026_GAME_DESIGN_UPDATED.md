# APEX FORMULA MANAGER 2026 - GAME DESIGN DOCUMENT (GDD)

## 1. OYUNUN VİZYONU VE ÖZETİ
Apex Formula Manager 2026, oyuncunun bir Formula yarış takımını yönettiği strateji ve simülasyon odaklı bir menajerlik oyunudur. Motor sporlarındaki en ufak verilerin ve hesaplamaların şampiyonluk yolunda ne kadar kritik olduğunu yansıtmayı amaçlar.

Oyun, turlar bazında (lap-by-lap) işleyen dinamik yarış motoru, sürpriz hava koşulları olayları, çarpışma/arıza dinamikleri, pilot özel yetenekleri (Perk) ve kübik/kuartik matematiksel gelişim sistemleriyle türünün klasiklerinden ayrışır.

---

## 2. MODELLER VE İSTATİSTİKLER (STATS)

### 2.1. Pilotlar (Drivers)
Her pilot 0-100 arasında değerlendirilen ana statlara ve gelişimi belirleyen bir potansiyele sahiptir:
* **Pace:** Sürücünün tur zamanlarına (Base Power) doğrudan etki eden ham hız katsayısı.
* **Consistency:** Hata (kaza/spin) yapma olasılığını azaltır. İstikrarlı tur atılmasını sağlar.
* **Attack & Defense:** DRS mesafelerinde veya normal sollama ataklarında başarılı olma (ve savunma) olasılığını artırır.
* **Tire Management:** Lastiklerin aşınma katsayısını (Tire Degradation) yavaşlatır.
* **Potential (Potansiyel):** Pilotun ne kadar hızlı öğrenebileceğini belirler. Geliştirilemez. XP kazanım çarpanıdır. Pilotun mevcut statı potansiyelini geçerse gelişim %90'a varan oranda yavaşlar (Soft Cap).

### 2.2. Araçlar (Cars)
Araç statları, pistin karakteristiğine göre pilot statlarıyla birleşerek nihai "Base Power" üretir:
* **Acceleration:** Düşük hızlı viraj çıkışları ve pistin hızlanma ihtiyacına karşılık gelir.
* **Top Speed:** Uzun düzlüklerdeki maksimum hızı temsil eder.
* **Grip:** Viraj hakimiyeti ve downforce seviyesidir.
* **Reliability:** Araç arıza yapma (Mekanik DNF) olasılığını azaltır.
* **Tire Consumption:** Aracın mekanik yapısının lastiği ne kadar hızlı yediğini belirler.

### 2.3. Pistler (Tracks)
Her pist, araçların ve pilotların farklı özelliklerini test eden katsayılara sahiptir:
* **Requirement Çarpanları:** `req_top_speed`, `req_acceleration`, `req_grip`. Pistin doğasına göre aracın hangi özelliğinin daha çok süre kazandıracağını belirler.
* **Driver Skill Requirement:** Pistin pilot yeteneğine (Pace ve Consistency) ne kadar dayandığını (örneğin Monaco'da yüksek) gösterir.
* **Weather Volatility:** Yağmur yağma veya hava koşullarının aniden değişme ihtimalini belirler.

---

## 3. GELİŞTİRME VE AR-GE SİSTEMİ (PROGRESSION)

Oyun statik gelişim yerine, rekabeti artıran ve tepe noktalara ulaşmayı zorlaştıran üstel bir gelişim mekaniği kullanır.

### 3.1. Sezon İçi Geliştirme (XP Mekaniği)
* Sürücülerin statları **Kübik Formula** `100 + (Stat^3 / 20)` ile seviye atlar.
* Araçların statları **Kuartik Formula** `500 + (Stat^4 / 700)` ile çok daha zor seviye atlar.
* Stat 70'ten 71'e çıkmak görece çok hızlı ve kolayken, stat 90'dan 91'e çıkmak büyük bir yatırım ister (Catch-up Mekaniği).

### 3.2. Ar-Ge Tesisleri (Base Building)
Takımların gelişim hızını artıran 3 adet tesisi bulunur. Bu tesislerin her biri 6 yarışlık süreçte seviye atlar.
* **Seviye Çarpanları:** Seviye 1 (1.0x), Seviye 2 (1.5x), Seviye 3 (2.2x XP Çarpanı).
* **Wind Tunnel (Rüzgar Tüneli):** Araç Grip ve Acceleration yatırımlarını hızlandırır.
* **Simulator (Simülatör):** Sürücülerin stat geliştirmelerini ve XP kazanımını hızlandırır.
* **Factory (Fabrika):** Araç Top Speed, Reliability ve Tire Consumption yatırımlarını hızlandırır.

---

## 4. ÖZEL YETENEKLER (PERK) SİSTEMİ

Her pilotun yarış kaderini etkileyebilecek maksimum 2 adet "Perk"ü olabilir. Pilotlar antrenmanlara ve geliştirmelere odaklandıkça %10 şansla yeni bir perk kazanabilirler. 

**Perk Havuzu (Mevcut Yetenekler):**
1. **Rainmaster:** Yağmurlu yarışlarda Pace +10 artar.
2. **Divebomber:** Atak bonusu kazandırır ancak kaza riskini x1.5 artırır.
3. **Tire Whisperer:** Lastik aşınmasını %20 yavaşlatır.
4. **Bare Canvas:** Lastikler çok aşındığında (%50 altına düştüğünde) tur süresi kaybını ciddi oranda azaltır.
5. **Experience Master:** Geliştirmelerden %20 daha fazla XP kazanır.
6. **Mr. Saturday:** Sıralama turlarında formuna +2 bonus sağlar.
7. **Smooth Operator:** Araç mekanik arıza (DNF) riskini %30 düşürür.
8. **Clutch Start:** Yarış startında arkalarda başlamanın verdiği grid dezavantajını minimuma indirir.
9. **Defensive Minister:** Sırada kalmayı kolaylaştırır, Consistency statına gizli +5 bonus sağlar.
10. **Street Fighter:** Dar sokak pistlerinde (Monaco, Singapur vb.) Pace +5 artar.
11. **High Speed Junkie:** Düzlük ağırlıklı pistlerde (Monza, Spa vb.) Pace +5 artar.
12. **Pressure Cooker:** Kaza ihtimaline sebep olan hata payını (Consistency riskini) %20 azaltır.

---

## 5. YARIŞ MOTORU (RACE ENGINE) DİNAMİKLERİ

### 5.1. Dinamik Hava Durumu ve Tahmin
* Takımlara yarış öncesinde bir "Hava Tahmini" verilir.
* Bu tahmin güven aralığına göre sapabilir (beklenen yağmur erken/geç başlayabilir veya hiç yağmayabilir).
* Islaklık derecesine göre Dry, Intermediate veya Full Wet lastikler arası geçiş hayati önem taşır. Kuru lastiklerle sular altında yarışmak, hem saniye kaybına hem de yüksek kaza riskine yol açar.

### 5.2. Olaylar, Güvenlik Aracı ve DNF Mekaniği
Yarış içinde her tur statlara bağlı olarak kaza zarları atılır.
* **Retire (DNF):** Büyük kazalar ve mekanik arızalar. Yarış dışı kalma durumu.
* **Damage:** Ufak temas veya kırık kanat. Pilot mecburi pite girer ve "Pace Penalty" alarak hız kaybeder.
* **Spin (Minor Time Loss):** Pist dışına taşma sonucu ufak zaman kaybı.
* **SC & VSC:** Kaza büyüklüğüne göre Güvenlik Aracı, Sanal Güvenlik Aracı (VSC) veya Kırmızı Bayrak çıkabilir. Araçlar SC arkasında yavaşlar, aralarındaki saniye farkı kapanır ve restart kaosuna zemin hazırlanır.

### 5.3. Sollama Sistemi
* Araçların Base Power'ı, pilotun Attack/Defense gücü ve pistin Overtaking Difficulty (Geçiş Zorluğu) katsayısı kıyaslanır.
* Belirli bir turdan sonra DRS devreye girerek sollama ihtimalini geçici süreyle artırır.
* Geçiş denemelerinde çarpışma (Collision) riski bulunur, agresif perk'ler (Divebomber) bu riskle birlikte oynanışı şekillendirir.

---

## 6. EXCEL RAPORLAMA VE VERİ BİLİMİ
Oyun simulasyonu sonuçlandıktan sonra "Gelişmiş Excel Formatında" detaylı bir rapor sunar.
* **Özet Sayfası:** Tüm sezonun yarış kazananları, Pole pozisyonları, Yağmur durumu, SC sayısı ve DNF sayıları.
* **Şampiyona:** Pilotların ve Markaların gerçek şampiyona sıralamaları, sezon öncesi **Beklenen Sıralamalarına (Expected Rank)** kıyasla kaç sıra geriledikleri/yükseldikleri.
* **Geliştirme Raporu:** Pilotların ve Araçların sezon başı statları ile sezon sonu statları, hangi statın kaç kere yatırıma uğradığı ve kazanılan Perk sayıları.
* **Yarış Sayfaları:** Her yarışın olay kütüğü (Kritik anlar: SC, Yağmur, DNF, Sollama vb.) ve bitiriş pozisyonları.

---

## 7. GELECEK YOL HARİTASI (ROADMAP)
* Bütçe sınırı (Cost Cap), Sponsorluklar ve Hasar Maliyeti sistemlerinin arayüze (GUI) entegrasyonu.
* Transfer Pazarı ve Emeklilik / Çaylak (Regen) pilot sisteminin getirilmesi.
* Grafik arayüz / Web uygulaması tabanlı bir takım yönetim ekranı inşa edilmesi.