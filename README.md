# Şehir Arası — İstanbul, Ankara ve İzmir

Müze, tarihî yer, manzara ve doğa duraklarını keşfetmek, gezi planlamak ve kişisel gezi günlüğü tutmak için hazırlanmış fullstack Python uygulaması.

## Özellikler

- FastAPI ile JSON API
- SQLite veritabanı; İstanbul'da 15, Ankara'da 5, İzmir'de 5 durak
- Ada, kategori ve semte göre arama ve filtreleme
- Popülerlik, puan ve ada göre sıralama
- Durak detayları, haritada açma bağlantısı ve ziyaretçi yorumları
- Kullanıcı hesabı, giriş/çıkış ve oturum çerezi
- Giriş yapan kullanıcılar için kalıcı favoriler; ziyaretçiler için tarayıcıda favoriler
- Kullanıcı başına durak için bir yorum ve yıldız puanlama
- Kişisel rota oluşturma, durak sırasını ayarlama, düzenleme ve silme
- Yönetici panelinden durak ekleme, düzenleme ve silme
- Mobil uyumlu web arayüzü
- Kültür Defteri tasarımı: kırmızı/krem renkler, fotoğraf kolajı ve el yazısı detayları
- Ana sayfada üç öneri, tüm durakları açma ve tüm liste üzerinde arama/filtreleme
- Yerel fotoğraflar ve yazı tipleri; sayfa içinde fotoğraf kaynakları bağlantısı
- Leaflet / OpenStreetMap ile seçilebilir durak haritası ve kart/harita görünümü
- Üç şehirde toplam 7 hazır rota; inceleme ve kişisel rotaya dönüştürme
- Sıralı duraklara göre kuş uçuşu mesafe, önerilen ziyaret süresi ve isteğe bağlı gerçek yürüyüş yolu hesabı
- Kullanıcıya özel ziyaret tarihi ve notlarla gezi günlüğü
- Rota bağlantısı oluşturma ve paylaşımı kapatma; özel notlar paylaşılmaz
- Kapalı mekân, çocukla gezi ve doğrulanmış tekerlekli sandalye erişimi filtreleri
- Aylık kültür takvimi, gün seçimi ve geçmiş etkinlikler
- Yönetici için kaynak ve kontrol tarihiyle etkinlik ekleme, düzenleme ve silme
- API dokümantasyonu: `/docs`

## Kurulum

Python 3.10 veya üzeri gerekir. Windows PowerShell'de proje klasöründen:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe baslat.py
```

`py` komutu Python bulamıyorsa Python 3.10+ kurup ilk satırda `python -m venv .venv` kullan. Başlatma komutu terminalde bir adres gösterir; uygulamayı o adreste aç. Başlatıcı önce `8765` portunu dener, gerekirse başka kullanılabilir bir port seçer. İlk çalıştırmada `data/guide.db` dosyası ve örnek durak/yorum kayıtları oluşturulur.

Yeni kullanıcılar arayüzden hesap açabilir. Yönetici hesabı eklemek veya mevcut hesabı yöneticiye çevirmek için sunucudan ayrı bir terminalde:

```powershell
.\.venv\Scripts\python.exe manage.py create-admin
```

Komut adı, e-postayı ve parolayı terminalde ister. Yönetici girişi yaptıktan sonra durak yönetimi bölümü görünür.

Veritabanını farklı bir konumda tutmak için sunucuyu başlatmadan önce `GUIDE_DB_PATH` ortam değişkenini ayarla. Uygulama eski örnek veritabanına kullanıcı hesabı ve rota tablolarını otomatik ekler.

## Bu sürüme geçiş

Çalışan sunucuyu terminalde `Ctrl+C` ile durdur, `baslat.py` komutunu yeniden çalıştır ve tarayıcıda `Ctrl+F5` ile yenile. Yeni Python API uçları için yalnızca sayfayı yenilemek yeterli değildir. Veritabanı ilk açılışta yükseltilir; mevcut hesap, favori, yorum ve rotalar korunur. Bu çalışma sırasında önceki veritabanının yedeği `data/backups/guide-before-v2-20261019.db` konumuna alındı. ZIP paketi kişisel veritabanını ve yedekleri içermez.

## Yeni bölümlerin kullanımı

Üst menüden şehir seç. Keşif bölümünde Kartlar / Harita görünümünü veya gezi filtrelerini kullan. Bir durağın ayrıntısındaki “Ziyaret ettim” düğmesi özel gezi günlüğüne kayıt açar. Hazır rotalar bölümündeki “Kendime ekle” düğmesi rotayı düzenlenebilir gezi planına çevirir; kaydetmeden önce durak sırasını değiştirebilirsin.

Rota düzenlerken veya rotayı görüntülerken “Yürüyüş yolunu hesapla” düğmesi OSRM / FOSSGIS hizmetinden yaya güzergâhını ister. Hesaplanana kadar gösterilen mesafe **kuş uçuşudur**, yürüyüş yolu veya yürüyüş süresi değildir. Yürüyüş servisi yanıt verdiğinde yol mesafesi, yürüyüş süresi, önerilen ziyaret ve toplam süre ayrı gösterilir. İnternet kesildiğinde kuş uçuşu bilgi ve açıklama korunur. `GUIDE_ROUTING_URL` ile uyumlu bir OSRM yaya sunucusu belirtilebilir; boş değer hizmeti kapatır. Sonuçlar 24 saat bellekte tutulur ve dış hizmete saniyede en fazla bir istek gönderilir. [Hizmet kullanım bilgisi](https://routing.openstreetmap.de/about.html).

Harita zemini internet ister; Leaflet kitaplığı yereldir. OpenStreetMap atıfları haritada görünür. [Leaflet](https://leafletjs.com/) ve [OpenStreetMap harita kullanım ilkeleri](https://operations.osmfoundation.org/policies/tiles/).

Kişisel rotanın “Paylaş” düğmesi tahmin edilemeyen bir bağlantı oluşturur. Bağlantıyı bilenler rota adını ve durakları görür; gezi notları, e-posta ve hesap bilgileri gösterilmez. Düzenlemeler aynı bağlantıya yansır; “Paylaşımı kapat” önceki bağlantıyı geçersiz kılar. Yerel `127.0.0.1` bağlantıları yalnızca sunucunun çalıştığı bilgisayardan açılır. Arkadaşlarınla internet üzerinden paylaşmak için uygulamanın erişilebilir bir sunucuda yayımlanması gerekir.

Takvimde yalnızca resmî kaynaklardan doğrulanmış tarihler kullanılır; son kontrol tarihi kartlarda görünür. Veriler otomatik canlı akış değildir. İzmir için doğrulanmış güncel kayıt yoksa boş takvim gösterilir. Yönetici hesabıyla takvimden kayıt eklenebilir ve güncellenebilir. Erişilebilirlik için `bilinmiyor`, `evet` ve `hayır` ayrıdır; yalnızca doğrulanmış `evet` kayıtları filtreye girer. Çocukla gezi etiketleri ve ziyaret süreleri editoryal öneridir. Konumlar yaklaşık noktalardır; giriş kapısı ve erişilebilir güzergâh garantisi vermez.

## API uçları

| Yöntem | Uç | Açıklama |
|---|---|---|
| `GET` | `/api/places` | Arama, kategori, semt ve sıralama filtreleri |
| `GET` | `/api/places/{slug}` | Durak ayrıntısı ve yorumlar |
| `POST` | `/api/places/{slug}/reviews` | Giriş yapmış kullanıcıdan yorum alma |
| `GET` | `/api/categories` | Kategoriler ve durak sayıları |
| `GET` | `/api/auth/me` | Açık oturumu görüntüleme |
| `POST` | `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` | Hesap ve oturum işlemleri |
| `GET`, `POST`, `DELETE` | `/api/favorites`, `/api/favorites/{slug}` | Kişisel favoriler |
| `GET`, `POST`, `PUT`, `DELETE` | `/api/routes`, `/api/routes/{id}` | Kişisel gezi rotaları |
| `POST`, `PUT`, `DELETE` | `/api/admin/places`, `/api/admin/places/{slug}` | Yönetici durak işlemleri |
| `GET` | `/api/districts` | Rehberdeki semtler |
| `GET` | `/api/health` | Servis durumu |
| `GET` | `/api/cities` | Şehirler, harita merkezleri ve durak sayıları |
| `GET` | `/api/route-templates?city=ankara` | Hazır rotalar ve süre/mesafe özeti |
| `POST` | `/api/route-estimate` | Sıralı duraklar için mesafe; `walking=true` ile yaya güzergâhı |
| `POST`, `DELETE` | `/api/routes/{id}/share` | Kendi rotan için paylaşım açma/kapatma |
| `GET` | `/api/shared-routes/{token}`, `/r/{token}` | Özel not içermeyen paylaşılan rota |
| `GET`, `PUT`, `DELETE` | `/api/journal`, `/api/journal/{slug}` | Oturum sahibinin özel ziyaret günlüğü |
| `GET` | `/api/events?city=istanbul&start=2026-10-01&end=2026-10-31` | Tarih aralığıyla çakışan etkinlikler |
| `POST`, `PUT`, `DELETE` | `/api/admin/events`, `/api/admin/events/{id}` | Yönetici etkinlik işlemleri |

`/api/places`, `/api/categories` ve `/api/districts` varsayılan olarak İstanbul'u döndürür. `city=ankara` veya `city=izmir` başka şehri seçer; `city=` tüm durak kataloğunu verir. Durak listesindeki ek filtreler `indoor=true`, `family_friendly=true`, `wheelchair_accessible=true` şeklindedir. Aynı rota farklı şehirlerden durak içeremez.

Örnek yorum isteği:

```json
{
  "rating": 5,
  "body": "Sakin bir saatte gezmek çok keyifliydi."
}
```

## Kontroller

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kontroller; keşif, hesap, favori, yorum, rota, şehir filtreleri, hazır rotalar, yürüyüş hesabı/bağlantı kesintisi, özel günlük, paylaşımın gizlilik sınırları, etkinlik takvimi, yönetici yetkisi ve eski veritabanının yükseltilmesini kapsar. Testler geçici veritabanı kullanır ve dış yürüyüş hizmetini taklit eder.

## Kapsam

Örnek durakların fotoğrafları ve yazı tipleri proje içinde bulunur. Fotoğrafların sahipleri, kaynakları ve lisansları `static/photos/credits.html`, `city-credits.html` ve karşılık gelen JSON dosyalarında yer alır. Wikimedia Commons fotoğrafları kendi lisanslarıyla; Manrope ve Caveat yazı tipleri `static/fonts/` içindeki SIL Open Font License ile dağıtılır. Yeni eklenen ve fotoğrafı bulunmayan duraklar için harfli kart görünümü kullanılır. Dosya yükleme ve otomatik etkinlik akışı bu sürümde bulunmaz.

## Proje yapısı

```text
istanbul-sehir-rehberi/
├── main.py
├── guide_catalog.py
├── guide_features.py
├── baslat.py
├── manage.py
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── tests/
│   ├── test_app.py
│   └── test_features.py
└── static/
    ├── index.html
    ├── app.css
    ├── app.js
    ├── photos.js
    ├── city-photos.js
    ├── features.js
    ├── features.css
    ├── photos/
    ├── vendor/leaflet/
    └── fonts/
```
