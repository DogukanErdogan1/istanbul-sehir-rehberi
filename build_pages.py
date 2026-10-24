"""Generate the personal pages from the shared site shell."""
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent / "static"
PAGES = {
    "hesabim.html": ("account", "Hesabım", "Favori durakların, gezi rotaların ve sana ait şehir defterin."),
    "rotalarim.html": ("routes", "Rotalarım", "Kendi gezi rotalarını oluştur, düzenle ve şehre kendi yolundan bak."),
    "gunlugum.html": ("journal", "Gezi Günlüğüm", "Ziyaretlerini ve güzel günlerden kalan anılarını kendi şehir defterinde sakla."),
}

def build_pages() -> None:
    shell = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for filename, (page, title, description) in PAGES.items():
        source = shell.replace('<html lang="tr">', f'<html lang="tr" data-page="{page}" data-auth="loading">', 1)
        source = source.replace("<title>Şehir Arası — Bir şehir. Bin hikâye. Senin rotan.</title>", f"<title>{title} — Şehir Arası</title>", 1)
        source = source.replace("İstanbul, Ankara ve İzmir'i merakının peşinden keşfet. Haritada durak bul, rotanı çiz ve gezi günlüğünü tut.", description, 1)
        (STATIC_DIR / filename).write_text(source, encoding="utf-8")

if __name__ == "__main__":
    build_pages()
