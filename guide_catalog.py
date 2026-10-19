"""Kaynak bağlantılarıyla şehir, durak, örnek rota ve etkinlik kataloğu.

Süreler ve aile önerileri editoryal gezi tahminidir. Harita noktaları yapı/alan
merkezini yaklaşık gösterir; giriş kapısı veya erişilebilir yürüyüş güzergâhı
garantisi vermez. None, bilgi doğrulanmadı anlamındadır; olumsuzluk belirtmez.
Etkinlik tarihleri resmi sayfalardan 19 Ekim 2026 tarihinde kontrol edilmiştir.
Bu modül canlı etkinlik veya ziyaret saati servisi değildir.
"""

VERIFIED_ON = "2026-10-19"
UNKNOWN_ACCESS = "Tekerlekli sandalye erişimi resmi kaynakta doğrulanmadı. Ziyaret öncesi kurumla görüşün."
LOCATION_NOTE = "Yaklaşık konum; giriş kapısı ve erişilebilir güzergâh farklı olabilir."

CITIES = [
    {"slug": "istanbul", "name": "İstanbul", "latitude": 41.0300, "longitude": 28.9900, "zoom": 12},
    {"slug": "ankara", "name": "Ankara", "latitude": 39.9350, "longitude": 32.8540, "zoom": 13},
    {"slug": "izmir", "name": "İzmir", "latitude": 38.4250, "longitude": 27.1340, "zoom": 13},
]


def _meta(city, lat, lon, minutes, indoor, family, source, *, wheelchair=None, note=UNKNOWN_ACCESS, source_name="Resmi kurum"):
    return {
        "city_slug": city,
        "latitude": lat,
        "longitude": lon,
        "visit_minutes": minutes,
        "indoor": indoor,
        "family_friendly": family,
        "wheelchair_accessible": wheelchair,
        "accessibility_note": note,
        "source_url": source,
        "source_name": source_name,
        "verified_on": VERIFIED_ON,
        "location_note": LOCATION_NOTE,
    }


PLACE_META = {
    "ayasofya": _meta("istanbul", 41.0086, 28.9802, 90, True, None,
        "https://istanbul.ktb.gov.tr/TR-276793/tarihi-yarimada.html"),
    "topkapi-sarayi": _meta("istanbul", 41.0115, 28.9834, 150, None, None,
        "https://www.millisaraylar.gov.tr/Lokasyon/2/topkapi", source_name="Milli Saraylar"),
    "yerebatan-sarnici": _meta("istanbul", 41.0084, 28.9779, 60, True, None,
        "https://yerebatan.com/", source_name="Yerebatan Sarnıcı"),
    "istanbul-arkeoloji-muzeleri": _meta("istanbul", 41.0117, 28.9812, 120, True, True,
        "https://istanbul.ktb.gov.tr/TR-276120/mudurlugumuze-bagli-muzeler.html"),
    "galata-kulesi": _meta("istanbul", 41.0256, 28.9741, 75, None, None,
        "https://istanbul.ktb.gov.tr/TR-276120/mudurlugumuze-bagli-muzeler.html"),
    "pera-muzesi": _meta("istanbul", 41.0319, 28.9752, 90, True, True,
        "https://www.peramuzesi.org.tr/icerik/engelli-ziyaretciler/1532",
        wheelchair=True,
        note="Resmi bilgi: giriş tekerlekli sandalyeye uygun, tüm katlara asansör var; uygun tuvalet bulunuyor.",
        source_name="Pera Müzesi"),
    "masumiyet-muzesi": _meta("istanbul", 41.0290, 28.9798, 90, True, None,
        "https://www.masumiyetmuzesi.org/en/about-1", source_name="Masumiyet Müzesi"),
    "dolmabahce-sarayi": _meta("istanbul", 41.0393, 29.0005, 150, None, None,
        "https://millisaraylar.gov.tr/Lokasyon/3/Dolmabahce-Sarayi", source_name="Milli Saraylar"),
    "rahmi-koc-muzesi": _meta("istanbul", 41.0422, 28.9497, 150, None, True,
        "https://www.rmk-museum.org.tr/istanbul", source_name="Rahmi M. Koç Müzesi"),
    "sakip-sabanci-muzesi": _meta("istanbul", 41.0987, 29.0546, 120, None, True,
        "https://www.sakipsabancimuzesi.org/", source_name="Sakıp Sabancı Müzesi"),
    "emirgan-korusu": _meta("istanbul", 41.1081, 29.0529, 90, False, True,
        "https://isg.ibb.istanbul/emirgan-korusu/", source_name="İstanbul Büyükşehir Belediyesi"),
    "moda-sahili": _meta("istanbul", 40.9808, 29.0259, 90, False, True,
        "https://www.kadikoy.bel.tr/", source_name="Kadıköy Belediyesi"),
    "pierreloti-tepesi": _meta("istanbul", 41.0549, 28.9330, 75, False, None,
        "https://istanbuluseyret.ibb.istanbul/en/touristic-camera/pierre-loti", source_name="İstanbul Büyükşehir Belediyesi"),
    "suleymaniye-camii": _meta("istanbul", 41.0162, 28.9642, 60, None, None,
        "https://istanbul.ktb.gov.tr/TR-276793/tarihi-yarimada.html"),
    "istanbul-modern": _meta("istanbul", 41.0266, 28.9839, 120, True, True,
        "https://www.istanbulmodern.org/ziyaret/ziyaret-rehberi",
        note="Resmi rehber ödünç tekerlekli sandalye ve özel erişim programları bildiriyor. Tüm güzergâhın sandalye erişimi ayrıca doğrulanmadı; kurumla görüşün.",
        source_name="İstanbul Modern"),
}

NEW_PLACES = [
    {
        "slug": "anitkabir", "name": "Anıtkabir", "category": "history", "district": "Çankaya",
        "address": "Anıttepe, Çankaya, Ankara",
        "summary": "Atatürk'ün anıt mezarını ve Cumhuriyet tarihinin izlerini ziyaret et.",
        "description": "Anıtkabir, anıt mezar, tören alanı ve Atatürk ve Kurtuluş Savaşı Müzesi ile kapsamlı bir ziyaret sunar. Açık alan ve müzeyi birlikte gezmek için zaman ayırabilirsin. Giriş ve ziyaret düzenini resmi sayfadan kontrol et.",
        "duration": "1.5–2 saat", "best_for": "Cumhuriyet tarihi", "art": "columns", "featured": 1,
        **_meta("ankara", 39.9251, 32.8368, 120, None, True,
            "https://www.anitkabir.tsk.tr/", source_name="Anıtkabir Komutanlığı"),
    },
    {
        "slug": "anadolu-medeniyetleri-muzesi", "name": "Anadolu Medeniyetleri Müzesi", "category": "museum", "district": "Altındağ",
        "address": "Kale, Gözcü Sokak No:2, Ulus, Altındağ, Ankara",
        "summary": "Anadolu'nun uygarlıklarını tarihî bir bedesten ve handa keşfet.",
        "description": "Mahmutpaşa Bedesteni ve Kurşunlu Han'daki koleksiyon, Anadolu'nun tarihini arkeolojik eserlerle anlatır. Kronolojik sergilemeyi Ankara Kalesi çevresinde bir yürüyüşle birleştirebilirsin.",
        "duration": "2–3 saat", "best_for": "Arkeoloji ve uygarlıklar", "art": "objects", "featured": 1,
        **_meta("ankara", 39.9384, 32.8618, 150, True, True,
            "https://turkishmuseums.kprod.kultur.gov.tr/museum/detail/1940-ankara-anadolu-medeniyetleri-muzesi/1940/1",
            note="Resmi katalog 'Engelli Dostu' bilgisi veriyor; tekerlekli sandalye ile tüm alanlara erişim ayrıntısı belirtilmedi. Ziyaret öncesi kurumla görüşün.",
            source_name="Kültür ve Turizm Bakanlığı / Turkish Museums"),
    },
    {
        "slug": "ankara-etnografya-muzesi", "name": "Ankara Etnografya Müzesi", "category": "museum", "district": "Altındağ",
        "address": "Hacettepe, Türkocağı Sokak No:4, Opera, Altındağ, Ankara",
        "summary": "Ahşap, çini, halı ve gündelik yaşam eserleriyle kültür tarihine bak.",
        "description": "Müzenin salonlarında el sanatları ve farklı dönemlerin yaşam kültürü yer alır. Giriş holündeki anma alanı, Atatürk'ün naaşının Anıtkabir'e taşınmadan önce burada bulunduğu yılları hatırlatır.",
        "duration": "1–1.5 saat", "best_for": "El sanatları ve kültür", "art": "gallery", "featured": 0,
        **_meta("ankara", 39.9327, 32.8552, 90, True, True,
            "https://www.kulturportali.gov.tr/turkiye/ankara/gezilecekyer/etnografya-muzes", source_name="Türkiye Kültür Portalı"),
    },
    {
        "slug": "ankara-kalesi", "name": "Ankara Kalesi", "category": "view", "district": "Altındağ",
        "address": "Kale Mahallesi, Altındağ, Ankara",
        "summary": "Tarihî surlardan Ankara'yı izle, kale içi sokaklarını keşfet.",
        "description": "Kale ve çevresindeki geleneksel evler, eski Ankara'nın dokusunu bir arada gösterir. Bölgede yokuşlar ve basamaklar bulunabilir; yürüyüşünü kendi hareket ihtiyaçlarına göre planla.",
        "duration": "1–1.5 saat", "best_for": "Manzara ve fotoğraf", "art": "tower", "featured": 1,
        **_meta("ankara", 39.9415, 32.8654, 90, False, None,
            "https://ankara.gov.tr/ankara-kalesi", source_name="Ankara Valiliği"),
    },
    {
        "slug": "ankara-vakif-eserleri-muzesi", "name": "Ankara Vakıf Eserleri Müzesi", "category": "museum", "district": "Altındağ",
        "address": "Anafartalar, Atatürk Bulvarı No:23, Altındağ, Ankara",
        "summary": "Vakıf kültüründen halı, kilim ve el sanatlarıyla sakin bir müze molası.",
        "description": "Vakıf eserlerini bir araya getiren müzede halı, kilim, çini ve çeşitli el sanatı örneklerini görebilirsin. Ulus ve Opera çevresindeki kültür rotasına kısa bir durak olarak eklenebilir.",
        "duration": "45–60 dakika", "best_for": "Dokuma ve el sanatları", "art": "objects", "featured": 0,
        **_meta("ankara", 39.9356, 32.8550, 60, True, True,
            "https://avem.vgm.gov.tr/eser-ve-bilgiler/teknolojik-kullanim", wheelchair=True,
            note="Resmi bilgi: salonlara erişim için engelli asansörü ve uygun tuvalet bulunuyor. Güncel kullanım durumunu kurumdan öğrenebilirsin.",
            source_name="Vakıflar Genel Müdürlüğü"),
    },
    {
        "slug": "izmir-saat-kulesi", "name": "İzmir Saat Kulesi", "category": "history", "district": "Konak",
        "address": "Konak Meydanı, Konak, İzmir",
        "summary": "Konak Meydanı'nda İzmir'in simgesiyle buluş.",
        "description": "1901 yılında tamamlanan Saat Kulesi, Konak Meydanı'nın tarihî odak noktalarından biridir. Çevresindeki meydanı keşfedip Kemeraltı ve Agora yönüne yürüyüşe devam edebilirsin.",
        "duration": "20–30 dakika", "best_for": "Şehir simgeleri ve fotoğraf", "art": "tower", "featured": 1,
        **_meta("izmir", 38.4189, 27.1287, 30, False, True,
            "https://www.izmir.bel.tr/tr/SaatKulesi/208", source_name="İzmir Büyükşehir Belediyesi"),
    },
    {
        "slug": "smyrna-agorasi", "name": "Smyrna Agorası", "category": "history", "district": "Konak",
        "address": "Namazgah, Tarık Sarı Sokak, Konak, İzmir",
        "summary": "Şehrin merkezinde antik Smyrna'nın meydanını keşfet.",
        "description": "Kadifekale'nin kuzey yamacındaki agora, antik kentin kamusal yaşamına dair kalıntılar barındırır. Günümüze ulaşan yapıların önemli bölümü Roma dönemine aittir. Açık alandaki gezi için hava koşullarını dikkate al.",
        "duration": "1–1.5 saat", "best_for": "Arkeoloji ve antik tarih", "art": "columns", "featured": 1,
        **_meta("izmir", 38.4190, 27.1384, 90, False, None,
            "https://izmir.ktb.gov.tr/TR-77364/agora.html", source_name="İzmir İl Kültür ve Turizm Müdürlüğü"),
    },
    {
        "slug": "izmir-ataturk-muzesi", "name": "İzmir Atatürk Müzesi", "category": "museum", "district": "Alsancak",
        "address": "Atatürk Caddesi, Alsancak, Konak, İzmir",
        "summary": "Kordon'daki tarihî evde Atatürk'ün İzmir ziyaretlerinin izlerini gör.",
        "description": "Atatürk'ün İzmir'e geldiğinde kullandığı ev, bugün müze olarak ziyaretçilerini ağırlıyor. İç mekândaki dönem eşyaları ve yapının mimarisi, Kordon yürüyüşüne tarih molası ekler.",
        "duration": "45–60 dakika", "best_for": "Cumhuriyet tarihi ve mimari", "art": "gallery", "featured": 0,
        **_meta("izmir", 38.4357, 27.1406, 60, True, True,
            "https://izmir.ktb.gov.tr/TR-77094/ataturk-muzesi.html", source_name="İzmir İl Kültür ve Turizm Müdürlüğü"),
    },
    {
        "slug": "tarihi-asansor", "name": "Tarihî Asansör", "category": "view", "district": "Karataş",
        "address": "Turgut Reis, Şehit Nihatbey Caddesi, Konak, İzmir",
        "summary": "Karataş'ın tarihî asansöründen İzmir Körfezi'ne bak.",
        "description": "1907'de iki cadde arasındaki yükseklik farkını aşmak için inşa edilen Asansör, şehrin seyir noktalarından biridir. Çevredeki sokaklar ve körfez manzarasıyla kısa bir yürüyüş planlayabilirsin.",
        "duration": "45–60 dakika", "best_for": "Körfez manzarası", "art": "viewpoint", "featured": 1,
        **_meta("izmir", 38.4090, 27.1175, 60, False, True,
            "https://www.visitizmir.org/tr/Destinasyon/14563",
            note="Asansör bulunması bütün ziyaret güzergâhının tekerlekli sandalyeye uygun olduğunu doğrulamaz. Giriş ve seyir alanını kurumdan öğrenin.",
            source_name="Visit İzmir"),
    },
    {
        "slug": "kulturpark", "name": "Kültürpark", "category": "nature", "district": "Konak",
        "address": "Mimar Sinan, Şair Eşref Bulvarı, Konak, İzmir",
        "summary": "İzmir'in merkezinde ağaçlı yollarda kültür ve doğa molası ver.",
        "description": "Fuar geçmişi, sergi alanları ve bitki çeşitliliğiyle Kültürpark şehir içinde geniş bir yeşil alan sunar. Park yürüyüşünü Alsancak ve Kordon çevresindeki duraklarla birleştirebilirsin.",
        "duration": "1–2 saat", "best_for": "Yürüyüş ve aile gezisi", "art": "garden", "featured": 0,
        **_meta("izmir", 38.4278, 27.1447, 90, False, True,
            "https://www.visitizmir.org/tr/destinasyon/6116", source_name="Visit İzmir"),
    },
]

# Aynı metadata biçimi hem mevcut hem yeni duraklar için kullanılabilir.
_META_FIELDS = ("city_slug", "latitude", "longitude", "visit_minutes", "indoor", "family_friendly", "wheelchair_accessible", "accessibility_note", "source_url", "source_name", "verified_on", "location_note")
PLACE_META.update({place["slug"]: {key: place[key] for key in _META_FIELDS} for place in NEW_PLACES})

ROUTE_TEMPLATES = [
    {"slug": "tarihi-yarimada", "title": "Tarihî Yarımada'da bir gün", "description": "Sultanahmet'in büyük yapıları ve arkeoloji koleksiyonlarıyla dolu bir gün. Ziyaret sırasını güncel giriş koşullarına göre düzenleyebilirsin.", "city_slug": "istanbul", "place_slugs": ["ayasofya", "yerebatan-sarnici", "istanbul-arkeoloji-muzeleri", "topkapi-sarayi"], "theme": "Tarih"},
    {"slug": "beyoglu-sanat", "title": "Beyoğlu'nda sanat yürüyüşü", "description": "Pera'dan Çukurcuma'ya, Galata'dan Karaköy sahiline uzanan müze ve manzara rotası.", "city_slug": "istanbul", "place_slugs": ["pera-muzesi", "masumiyet-muzesi", "galata-kulesi", "istanbul-modern"], "theme": "Sanat"},
    {"slug": "emirgan-doga-sanat", "title": "Emirgan'da doğa ve sanat", "description": "Koru yürüyüşü ve Boğaz kıyısında bir müze ziyaretini aynı güne sığdır.", "city_slug": "istanbul", "place_slugs": ["emirgan-korusu", "sakip-sabanci-muzesi"], "theme": "Doğa ve sanat"},
    {"slug": "ankara-kale-arkeoloji", "title": "Kale'den uygarlıklara", "description": "Eski Ankara sokaklarını ve Anadolu'nun arkeolojik mirasını birlikte keşfet. Kale bölümü eğimli ve basamaklı olabilir.", "city_slug": "ankara", "place_slugs": ["ankara-kalesi", "anadolu-medeniyetleri-muzesi", "ankara-vakif-eserleri-muzesi"], "theme": "Arkeoloji"},
    {"slug": "ankara-kultur-hafiza", "title": "Başkentte kültür ve hafıza", "description": "Anıtkabir ziyaretiyle başlayıp Etnografya ve Vakıf Eserleri koleksiyonlarıyla devam et. Duraklar arasındaki ulaşımı ayrıca planla.", "city_slug": "ankara", "place_slugs": ["anitkabir", "ankara-etnografya-muzesi", "ankara-vakif-eserleri-muzesi"], "theme": "Kültür"},
    {"slug": "izmir-konak-tarih", "title": "Konak'ta tarihin izleri", "description": "Saat Kulesi ve Smyrna Agorası'ndan sonra körfez manzarası için Karataş'a uzan.", "city_slug": "izmir", "place_slugs": ["izmir-saat-kulesi", "smyrna-agorasi", "tarihi-asansor"], "theme": "Tarih ve manzara"},
    {"slug": "izmir-alsancak-mola", "title": "Alsancak'ta kültür molası", "description": "Atatürk Müzesi'ni gördükten sonra Kültürpark'ın ağaçlı yollarında gezinebilirsin.", "city_slug": "izmir", "place_slugs": ["izmir-ataturk-muzesi", "kulturpark"], "theme": "Aile ve kültür"},
]

EVENTS = [
    {
        "slug": "semiha-berksoy-renklerin-aryasi-2026",
        "title": "Semiha Berksoy: Tüm Renklerin Aryası",
        "city_slug": "istanbul", "place_slug": "istanbul-modern",
        "start_date": "2026-01-22", "end_date": "2026-11-22",
        "description": "Semiha Berksoy'un sahne ve görsel sanatlar arasındaki üretimini bir araya getiren sergi. Güncel bilet ve ziyaret bilgisi resmi sayfada.",
        "source_url": "https://www.istanbulmodern.org/sergi/semiha-berksoy-tum-renklerin-aryasi",
        "source_name": "İstanbul Modern", "verified_on": VERIFIED_ON,
    },
    {
        "slug": "zeliha-berksoy-sergi-turu-2026-10-22",
        "title": "Zeliha Berksoy ile Sergi Turu",
        "city_slug": "istanbul", "place_slug": "istanbul-modern",
        "start_date": "2026-10-22", "end_date": "2026-10-22",
        "description": "Semiha Berksoy sergisinde Zeliha Berksoy'un anlatımıyla tur. Resmi program: 18.00–19.00; Türkçe, biletli ve sınırlı kontenjanlı.",
        "source_url": "https://www.istanbulmodern.org/etkinlikler/sergi-etkinligi-zeliha-berksoy-ile-sergi-turu",
        "source_name": "İstanbul Modern", "verified_on": VERIFIED_ON,
    },
    {
        "slug": "blue-revolution-delft-ankara-2026",
        "title": "The Blue Revolution Delft–Ankara",
        "city_slug": "ankara", "place_slug": "anadolu-medeniyetleri-muzesi",
        "start_date": "2026-10-07", "end_date": "2026-10-25",
        "description": "Anadolu Medeniyetleri Müzesi'nin resmi etkinlik kataloğunda duyurulan sergi. Ayrıntı ve ziyaret koşullarını kurumun duyurusundan kontrol et.",
        "source_url": "https://turkishmuseums.kprod.kultur.gov.tr/events/detail?etkinlikId=21232&langId=1",
        "source_name": "Kültür ve Turizm Bakanlığı / Turkish Museums", "verified_on": VERIFIED_ON,
    },
    {
        "slug": "panorama-hayaller-yerler-2026",
        "title": "Panorama: Hayaller ve Yerler",
        "city_slug": "istanbul", "place_slug": "istanbul-modern",
        "start_date": "2026-02-19", "end_date": "2026-10-18",
        "description": "Fotoğraf ve mercek temelli sanat üzerine tematik sergi. Resmi bitiş tarihi 18 Ekim 2026; geçmiş etkinlik arşivinde gösterilmelidir.",
        "source_url": "https://www.istanbulmodern.org/sergi/panorama-hayaller-ve-yerler",
        "source_name": "İstanbul Modern", "verified_on": VERIFIED_ON,
    },
    {
        "slug": "elde-vefa-gozde-zarafet-2026",
        "title": "Elde Vefa, Gözde Zarafet: Takı Sanatının 12.000 Yıllık Öyküsü",
        "city_slug": "ankara", "place_slug": "ankara-etnografya-muzesi",
        "start_date": "2026-05-18", "end_date": "2026-09-01",
        "description": "Farklı müze koleksiyonlarından seçilen takılarla kültürler arası bir bakış. Resmi duyurudaki 1 Eylül 2026 bitiş tarihi korunmuştur; arşiv kaydıdır.",
        "source_url": "https://kvmgm.ktb.gov.tr/TR-456493/ankara-etnografya-muzesi-mudurlugu-sergi-etkinligi.html",
        "source_name": "Kültür Varlıkları ve Müzeler Genel Müdürlüğü", "verified_on": VERIFIED_ON,
    },
]

CATALOG_NOTES = {
    "verified_on": VERIFIED_ON,
    "events": "Resmi kaynaklardan son kontrol tarihi gösterilir. Süresi geçen kayıtlar geçmiş etkinlik olarak ayrılır; doğrulanmış güncel kayıt yoksa boş takvim gösterilir.",
    "izmir_events": "İzmir için kesin başlangıç ve bitiş tarihi doğrulanan güncel kayıt henüz eklenmedi.",
    "accessibility": "Yalnızca resmi kaynakta açıkça doğrulanan erişim True olarak işaretlidir. None bilgi eksikliğidir; erişilemez anlamına gelmez.",
    "family": "Aile ve kapalı alan etiketleri editoryal gezi önerileridir. Çocuklara özel tesis veya yaşa uygunluk garantisi değildir.",
    "duration": "Ziyaret süreleri yaklaşık gezi önerileridir; ulaşım, kuyruk ve mola süreleri değişebilir.",
    "location": LOCATION_NOTE,
}
