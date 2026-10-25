"""Şehir Arası — FastAPI + SQLite city guide."""

from __future__ import annotations

import sqlite3
import hashlib
import hmac
import os
import re
import secrets
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from guide_features import upgrade_database, install_features, route_metrics


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("GUIDE_DB_PATH", DATA_DIR / "guide.db"))
SESSION_COOKIE = "sehir_arasi_session"
SESSION_SECONDS = 60 * 60 * 24 * 30

app = FastAPI(
    title="Şehir Arası API",
    description="İstanbul, Ankara ve İzmir'deki kültür, tarih ve gezi noktalarını keşfet.",
    version="2.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


CATEGORIES = [
    ("museum", "Müzeler"),
    ("history", "Tarihî yerler"),
    ("view", "Manzara"),
    ("nature", "Doğa"),
    ("culture", "Kültür"),
]

# Saat ve ücret bilgileri bilinçli olarak eklenmedi; bu bilgiler sık değişebilir.
PLACES = [
    {
        "slug": "ayasofya",
        "name": "Ayasofya",
        "category": "history",
        "district": "Sultanahmet",
        "address": "Sultan Ahmet, Fatih",
        "summary": "İstanbul'un yüzyıllar boyunca farklı kültürlere ev sahipliği yapan en etkileyici yapılarından biri.",
        "description": "Ayasofya'nın kubbesi, mozaikleri ve katmanlı geçmişi İstanbul'un tarihini tek bir yapıda buluşturuyor. Sultanahmet çevresindeki diğer tarihî noktalarla birlikte gezilebilir.",
        "duration": "1–2 saat",
        "best_for": "Tarih ve mimari",
        "art": "dome",
        "featured": 1,
    },
    {
        "slug": "topkapi-sarayi",
        "name": "Topkapı Sarayı",
        "category": "museum",
        "district": "Sultanahmet",
        "address": "Cankurtaran, Fatih",
        "summary": "Osmanlı saray yaşamını avluları, köşkleri ve koleksiyonlarıyla keşfet.",
        "description": "Geniş avluları ve farklı dönemlerden eserleriyle Topkapı Sarayı, İstanbul'un tarihini yakından tanımak için kapsamlı bir durak. Geziyi rahatça tamamlamak için yeterli zaman ayırmak iyi olur.",
        "duration": "2–3 saat",
        "best_for": "Saray tarihi",
        "art": "palace",
        "featured": 1,
    },
    {
        "slug": "yerebatan-sarnici",
        "name": "Yerebatan Sarnıcı",
        "category": "history",
        "district": "Sultanahmet",
        "address": "Alemdar, Fatih",
        "summary": "Sütunların arasında, şehrin altında saklı Bizans döneminden kalma bir su yapısı.",
        "description": "Loş ışıklandırması ve sütun ormanını andıran iç mekânıyla Yerebatan Sarnıcı, Sultanahmet'in en farklı atmosferlerinden birine sahip. Medusa başlarını görmeyi unutma.",
        "duration": "45–60 dakika",
        "best_for": "Mimari ve fotoğraf",
        "art": "cistern",
        "featured": 1,
    },
    {
        "slug": "istanbul-arkeoloji-muzeleri",
        "name": "İstanbul Arkeoloji Müzeleri",
        "category": "museum",
        "district": "Sultanahmet",
        "address": "Cankurtaran, Fatih",
        "summary": "Antik çağlardan farklı uygarlıkların izlerini bir araya getiren müze kompleksi.",
        "description": "Birden fazla binaya yayılan koleksiyonlarda antik dönemlerden eserler ve tarihî lahitler yer alıyor. Müze çevresindeki Gülhane Parkı ile aynı güne eklenebilir.",
        "duration": "1.5–2 saat",
        "best_for": "Arkeoloji",
        "art": "columns",
        "featured": 0,
    },
    {
        "slug": "galata-kulesi",
        "name": "Galata Kulesi",
        "category": "view",
        "district": "Galata",
        "address": "Bereketzade, Beyoğlu",
        "summary": "Beyoğlu silüetinde yükselen tarihî kuleden Boğaz'a ve Haliç'e bak.",
        "description": "Galata'nın simge yapılarından kule, çevredeki yokuşlu sokakları ve tarihî binaları keşfetmek için güzel bir başlangıç noktası. Ziyaret öncesinde güncel erişim bilgisini kontrol et.",
        "duration": "45–90 dakika",
        "best_for": "Şehir manzarası",
        "art": "tower",
        "featured": 1,
    },
    {
        "slug": "pera-muzesi",
        "name": "Pera Müzesi",
        "category": "museum",
        "district": "Tepebaşı",
        "address": "Meşrutiyet Caddesi, Beyoğlu",
        "summary": "Sanat sergileri ve tanınmış koleksiyonlarıyla Beyoğlu'nda keyifli bir kültür molası.",
        "description": "Pera Müzesi, kalıcı koleksiyonlarının yanı sıra dönemsel sergilere de ev sahipliği yapıyor. İstiklal Caddesi ve çevresindeki kitapçılarla birlikte bir Beyoğlu rotasına eklenebilir.",
        "duration": "1–2 saat",
        "best_for": "Sanat",
        "art": "gallery",
        "featured": 0,
    },
    {
        "slug": "masumiyet-muzesi",
        "name": "Masumiyet Müzesi",
        "category": "museum",
        "district": "Çukurcuma",
        "address": "Çukurcuma Caddesi, Beyoğlu",
        "summary": "Bir romanın dünyasını İstanbul'un gündelik hayatından objelerle anlatan özel bir müze.",
        "description": "Orhan Pamuk'un romanıyla aynı adı taşıyan müze, hikâyedeki karakterlerin eşyalarını ve dönemin İstanbul yaşamını vitrinler aracılığıyla bir araya getiriyor.",
        "duration": "1–1.5 saat",
        "best_for": "Edebiyat ve nostalji",
        "art": "objects",
        "featured": 0,
    },
    {
        "slug": "dolmabahce-sarayi",
        "name": "Dolmabahçe Sarayı",
        "category": "history",
        "district": "Beşiktaş",
        "address": "Vişnezade, Beşiktaş",
        "summary": "Boğaz kıyısındaki görkemli saray ve tören salonlarını ziyaret et.",
        "description": "Dolmabahçe Sarayı, Boğaz kıyısındaki konumu ve farklı mimari etkileri taşıyan iç mekânlarıyla öne çıkıyor. Saray bahçesini ve çevredeki sahil yolunu da rotana dahil edebilirsin.",
        "duration": "2–3 saat",
        "best_for": "Saray mimarisi",
        "art": "palace",
        "featured": 1,
    },
    {
        "slug": "rahmi-koc-muzesi",
        "name": "Rahmi M. Koç Müzesi",
        "category": "museum",
        "district": "Hasköy",
        "address": "Hasköy Caddesi, Beyoğlu",
        "summary": "Ulaşım, sanayi ve iletişim tarihini interaktif koleksiyonlarla tanı.",
        "description": "Haliç kıyısındaki müze; ulaşım araçları, makineler ve günlük yaşam nesneleriyle farklı yaş gruplarına hitap eden geniş bir koleksiyona sahip.",
        "duration": "2–3 saat",
        "best_for": "Aile gezisi ve teknoloji tarihi",
        "art": "machine",
        "featured": 0,
    },
    {
        "slug": "sakip-sabanci-muzesi",
        "name": "Sakıp Sabancı Müzesi",
        "category": "museum",
        "district": "Emirgan",
        "address": "Emirgan, Sarıyer",
        "summary": "Boğaz manzaralı tarihî köşkte sanat ve hat koleksiyonlarını gör.",
        "description": "Emirgan'da, Boğaz'a bakan bir yamaçta yer alan müze; sanat sergileri ve çevresindeki bahçeyle sakin bir gezi sunuyor.",
        "duration": "1.5–2 saat",
        "best_for": "Sanat ve Boğaz manzarası",
        "art": "gallery",
        "featured": 0,
    },
    {
        "slug": "emirgan-korusu",
        "name": "Emirgan Korusu",
        "category": "nature",
        "district": "Emirgan",
        "address": "Emirgan, Sarıyer",
        "summary": "Yürüyüş yolları, köşkleri ve Boğaz manzarasıyla şehirden kısa bir kaçış.",
        "description": "Emirgan Korusu, geniş yeşil alanları ve Boğaz'a açılan manzarasıyla özellikle açık havada vakit geçirmek isteyenler için güzel bir durak.",
        "duration": "1–2 saat",
        "best_for": "Yürüyüş ve piknik",
        "art": "garden",
        "featured": 0,
    },
    {
        "slug": "moda-sahili",
        "name": "Moda Sahili",
        "category": "nature",
        "district": "Moda",
        "address": "Moda Caddesi, Kadıköy",
        "summary": "Kadıköy'ün sahilinde yürüyüş yap, gün batımını deniz kıyısından izle.",
        "description": "Moda sahil yolu, deniz kenarında yürüyüş ve gün batımı için sevilen bir buluşma noktası. Kadıköy çarşısı ve Moda'nın kafeleriyle aynı rotada gezilebilir.",
        "duration": "1–2 saat",
        "best_for": "Gün batımı ve yürüyüş",
        "art": "coast",
        "featured": 1,
    },
    {
        "slug": "pierreloti-tepesi",
        "name": "Pierre Loti Tepesi",
        "category": "view",
        "district": "Eyüpsultan",
        "address": "Eyüpsultan merkez, Eyüpsultan",
        "summary": "Haliç'e yukarıdan bakan seyir noktasında manzaranın tadını çıkar.",
        "description": "Eyüpsultan'daki seyir noktası, Haliç manzarası ve çevredeki tarihî semt dokusuyla öne çıkıyor. Bölgeye yürüyerek ya da teleferik bağlantısıyla ulaşılabiliyor.",
        "duration": "1–1.5 saat",
        "best_for": "Manzara ve fotoğraf",
        "art": "viewpoint",
        "featured": 0,
    },
    {
        "slug": "suleymaniye-camii",
        "name": "Süleymaniye Camii",
        "category": "culture",
        "district": "Süleymaniye",
        "address": "Süleymaniye, Fatih",
        "summary": "Mimar Sinan'ın eserini ve çevresindeki tarihî külliye dokusunu keşfet.",
        "description": "Süleymaniye Camii'nin geniş avlusu ve Haliç'e bakan çevresi, eski İstanbul'u yürüyerek keşfetmek için etkileyici bir rota sunuyor. Ziyaret sırasında ibadet saatlerine saygı göstermeyi unutma.",
        "duration": "45–90 dakika",
        "best_for": "Mimari ve şehir tarihi",
        "art": "dome",
        "featured": 0,
    },
    {
        "slug": "istanbul-modern",
        "name": "İstanbul Modern",
        "category": "culture",
        "district": "Karaköy",
        "address": "Kılıçali Paşa, Beyoğlu",
        "summary": "Türkiye'den ve dünyadan modern sanat eserlerini Boğaz kıyısında gör.",
        "description": "Karaköy sahilindeki İstanbul Modern, modern ve çağdaş sanat sergileriyle şehir gezisine kültür molası eklemek isteyenler için uygun bir durak.",
        "duration": "1.5–2 saat",
        "best_for": "Modern sanat",
        "art": "gallery",
        "featured": 0,
    },
]


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db_session():
    db = connect_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize_database() -> None:
    with db_session() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                category_id INTEGER NOT NULL REFERENCES categories(id),
                district TEXT NOT NULL,
                address TEXT NOT NULL,
                summary TEXT NOT NULL,
                description TEXT NOT NULL,
                duration TEXT NOT NULL,
                best_for TEXT NOT NULL,
                art TEXT NOT NULL,
                featured INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
                author TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, place_id)
            );
            CREATE TABLE IF NOT EXISTS routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS route_places (
                route_id INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
                place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                PRIMARY KEY (route_id, place_id)
            );
            CREATE INDEX IF NOT EXISTS idx_places_district ON places(district);
            CREATE INDEX IF NOT EXISTS idx_reviews_place_id ON reviews(place_id);
            CREATE INDEX IF NOT EXISTS idx_routes_user_id ON routes(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
            """
        )

        # Older project databases are upgraded in place; existing demo reviews stay anonymous.
        review_columns = {row["name"] for row in db.execute("PRAGMA table_info(reviews)")}
        if "user_id" not in review_columns:
            db.execute("ALTER TABLE reviews ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_reviews_one_per_user_place "
            "ON reviews(user_id, place_id) WHERE user_id IS NOT NULL"
        )

        if db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            db.executemany("INSERT INTO categories (slug, name) VALUES (?, ?)", CATEGORIES)

        if db.execute("SELECT COUNT(*) FROM places").fetchone()[0] == 0:
            category_ids = {
                row["slug"]: row["id"]
                for row in db.execute("SELECT id, slug FROM categories").fetchall()
            }
            db.executemany(
                """INSERT INTO places
                   (slug, name, category_id, district, address, summary, description,
                    duration, best_for, art, featured)
                   VALUES (:slug, :name, :category_id, :district, :address, :summary,
                           :description, :duration, :best_for, :art, :featured)""",
                [{**place, "category_id": category_ids[place["category"]]} for place in PLACES],
            )

        if db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0:
            place_ids = {
                row["slug"]: row["id"]
                for row in db.execute("SELECT id, slug FROM places").fetchall()
            }
            demo_reviews = [
                ("ayasofya", "Deniz", 5, "Detayları görmek için acele etmeden gezmek gerekiyor. Çok etkileyici."),
                ("ayasofya", "Mert", 4, "Sultanahmet rotasının vazgeçilmez duraklarından."),
                ("topkapi-sarayi", "Elif", 5, "Avluları ve koleksiyonlarıyla tam bir gün ayırmaya değer."),
                ("yerebatan-sarnici", "Ece", 5, "İçerideki atmosfer gerçekten bambaşka."),
                ("galata-kulesi", "Can", 4, "Çevresindeki sokaklarda yürümek de gezinin güzel bir parçası."),
                ("moda-sahili", "Ada", 5, "Gün batımında yürüyüş için harika bir yer."),
                ("emirgan-korusu", "Bora", 4, "Şehir içinde doğada vakit geçirmek için çok güzel."),
                ("istanbul-modern", "Selin", 5, "Sergi sonrası sahil yolunda yürüyüş yapmayı öneririm."),
            ]
            now = datetime.now(timezone.utc).isoformat(timespec="minutes")
            db.executemany(
                "INSERT INTO reviews (place_id, author, rating, body, created_at) VALUES (?, ?, ?, ?, ?)",
                [(place_ids[slug], author, rating, body, now) for slug, author, rating, body in demo_reviews],
            )

        upgrade_database(db)


initialize_database()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    rounds = 260_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"


def ensure_demo_account() -> None:
    with db_session() as db:
        row = db.execute("SELECT id FROM users WHERE email = ?", ("demo@sehirarasi.demo",)).fetchone()
        if row:
            return
        db.execute(
            "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, 'member', ?)",
            ("Demo Gezgin", "demo@sehirarasi.demo", hash_password(secrets.token_urlsafe(32)), utc_now()),
        )


ensure_demo_account()


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        expected = bytes.fromhex(digest_hex)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError):
        return False


def public_user(row: sqlite3.Row | dict) -> dict:
    return {key: row[key] for key in ("id", "name", "email", "role")}


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and urlparse(origin).netloc != request.url.netloc:
        raise HTTPException(status_code=403, detail="Bu kaynaktan işlem yapılamıyor.")


def current_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with db_session() as db:
        row = db.execute(
            """SELECT u.id, u.name, u.email, u.role FROM sessions s
               JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > ?""",
            (token_hash, int(datetime.now(timezone.utc).timestamp())),
        ).fetchone()
    return public_user(row) if row else None


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Devam etmek için giriş yapmalısın.")
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yönetici yetkisi gerekiyor.")
    return user


def create_session_response(user: dict, request: Request) -> JSONResponse:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires = int(datetime.now(timezone.utc).timestamp()) + SESSION_SECONDS
    with db_session() as db:
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(datetime.now(timezone.utc).timestamp()),))
        db.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user["id"], expires),
        )
    response = JSONResponse({"user": user})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return response


class RegisterCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginCreate(BaseModel):
    email: str
    password: str


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    body: str = Field(min_length=8, max_length=600)


class RouteWrite(BaseModel):
    title: str = Field(min_length=3, max_length=70)
    notes: str = Field(default="", max_length=500)
    place_slugs: list[str] = Field(min_length=1, max_length=12)


class PlaceWrite(BaseModel):
    slug: str = Field(min_length=3, max_length=80)
    name: str = Field(min_length=3, max_length=100)
    category_slug: str = Field(min_length=2, max_length=40)
    district: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=3, max_length=160)
    summary: str = Field(min_length=10, max_length=240)
    description: str = Field(min_length=20, max_length=1800)
    duration: str = Field(min_length=2, max_length=40)
    best_for: str = Field(min_length=2, max_length=80)
    art: Literal["dome", "palace", "cistern", "columns", "tower", "gallery", "objects", "machine", "garden", "coast", "viewpoint"] = "gallery"
    featured: bool = False
    city_slug: str = Field(default="istanbul", max_length=40)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    visit_minutes: int = Field(default=90, ge=5, le=720)
    indoor: bool | None = None
    family_friendly: bool | None = None
    wheelchair_accessible: bool | None = None
    accessibility_note: str = Field(default="", max_length=500)
    source_url: str = Field(default="", max_length=700)


def _place_select() -> str:
    return """SELECT p.id, p.slug, p.name, p.district, p.address, p.summary,
                     p.description, p.duration, p.best_for, p.art, p.featured,
                     p.city_slug, ci.name AS city_name, p.latitude, p.longitude, p.visit_minutes,
                     p.indoor, p.family_friendly, p.wheelchair_accessible, p.accessibility_note, p.source_url,
                     c.slug AS category_slug, c.name AS category_name,
                     COALESCE(ROUND(AVG(r.rating), 1), 0) AS average_rating,
                     COUNT(r.id) AS review_count
              FROM places p
              JOIN categories c ON c.id = p.category_id
              LEFT JOIN cities ci ON ci.slug = p.city_slug
              LEFT JOIN reviews r ON r.place_id = p.id"""


def _as_place(row: sqlite3.Row) -> dict:
    place = dict(row)
    place["featured"] = bool(place["featured"])
    place["average_rating"] = float(place["average_rating"])
    for field in ("indoor", "family_friendly", "wheelchair_accessible"):
        if place.get(field) is not None:
            place[field] = bool(place[field])
    return place


@app.get("/hesabim", include_in_schema=False)
@app.get("/rotalarim", include_in_schema=False)
@app.get("/gunlugum", include_in_schema=False)
@app.get("/", include_in_schema=False)
def home(request: Request) -> FileResponse:
    pages = {"/hesabim": "hesabim.html", "/rotalarim": "rotalarim.html", "/gunlugum": "gunlugum.html"}
    return FileResponse(STATIC_DIR / pages.get(request.url.path, "index.html"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/auth/me")
def auth_me(request: Request) -> dict:
    return {"user": current_user(request)}


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterCreate, request: Request) -> JSONResponse:
    check_origin(request)
    name = payload.name.strip()
    email = payload.email.strip().lower()
    if len(name) < 2 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Geçerli bir ad ve e-posta gir.")
    with db_session() as db:
        try:
            cursor = db.execute(
                "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, 'member', ?)",
                (name, email, hash_password(payload.password), utc_now()),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="Bu e-posta zaten kayıtlı.") from error
        user = {"id": cursor.lastrowid, "name": name, "email": email, "role": "member"}
    response = create_session_response(user, request)
    response.status_code = status.HTTP_201_CREATED
    return response


@app.post("/api/auth/login")
def login(payload: LoginCreate, request: Request) -> JSONResponse:
    check_origin(request)
    with db_session() as db:
        row = db.execute(
            "SELECT id, name, email, role, password_hash FROM users WHERE email = ?",
            (payload.email.strip().lower(),),
        ).fetchone()
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="E-posta veya parola hatalı.")
    return create_session_response(public_user(row), request)


@app.post("/api/auth/demo-login")
def demo_login(request: Request) -> JSONResponse:
    check_origin(request)
    with db_session() as db:
        row = db.execute(
            "SELECT id, name, email, role FROM users WHERE email = ?",
            ("demo@sehirarasi.demo",),
        ).fetchone()
    if row is None or row["role"] != "member":
        raise HTTPException(status_code=503, detail="Demo hesabı şu anda kullanılamıyor.")
    return create_session_response(public_user(row), request)


@app.post("/api/auth/logout")
def logout(request: Request) -> JSONResponse:
    check_origin(request)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with db_session() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/api/categories")
def list_categories(city: str = "istanbul") -> list[dict]:
    with db_session() as db:
        rows = db.execute(
            """SELECT c.slug, c.name, COUNT(p.id) AS place_count
               FROM categories c LEFT JOIN places p ON p.category_id = c.id AND (?='' OR p.city_slug=?)
               GROUP BY c.id ORDER BY c.id""", (city, city)
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/districts")
def list_districts(city: str = "istanbul") -> list[str]:
    with db_session() as db:
        rows = db.execute("SELECT DISTINCT district FROM places WHERE (?='' OR city_slug=?) ORDER BY district COLLATE NOCASE", (city, city)).fetchall()
    return [row["district"] for row in rows]


@app.get("/api/places")
def list_places(
    q: str = Query(default="", max_length=100),
    category: str = Query(default="", max_length=40),
    district: str = Query(default="", max_length=80),
    sort: Literal["popular", "rating", "az"] = "popular",
    limit: int = Query(default=50, ge=1, le=100),
    city: str = Query(default="istanbul", max_length=40),
    indoor: bool | None = None,
    family_friendly: bool | None = None,
    wheelchair_accessible: bool | None = None,
) -> dict:
    where = []
    params: list = []
    if city:
        where.append("p.city_slug = ?")
        params.append(city)
    for field, value in (("indoor", indoor), ("family_friendly", family_friendly), ("wheelchair_accessible", wheelchair_accessible)):
        if value is not None:
            where.append(f"p.{field} = ?")
            params.append(int(value))
    if q.strip():
        where.append("(p.name LIKE ? OR p.district LIKE ? OR p.summary LIKE ? OR c.name LIKE ?)")
        term = f"%{q.strip()}%"
        params.extend([term, term, term, term])
    if category:
        where.append("c.slug = ?")
        params.append(category)
    if district:
        where.append("p.district = ?")
        params.append(district)

    order_by = {
        "popular": "p.featured DESC, review_count DESC, average_rating DESC, p.name COLLATE NOCASE",
        "rating": "average_rating DESC, review_count DESC, p.name COLLATE NOCASE",
        "az": "p.name COLLATE NOCASE",
    }[sort]
    sql = _place_select()
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" GROUP BY p.id ORDER BY {order_by} LIMIT ?"
    params.append(limit)

    with db_session() as db:
        rows = db.execute(sql, params).fetchall()
    return {"items": [_as_place(row) for row in rows], "total": len(rows)}


def place_details(slug: str, user_id: int | None = None) -> dict:
    with db_session() as db:
        row = db.execute(_place_select() + " WHERE p.slug = ? GROUP BY p.id", [slug]).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Durak bulunamadı.")
        reviews = db.execute(
            """SELECT user_id, author, rating, body, created_at FROM reviews
               WHERE place_id = ? ORDER BY id DESC LIMIT 20""",
            [row["id"]],
        ).fetchall()
        has_reviewed = bool(user_id and db.execute(
            "SELECT 1 FROM reviews WHERE place_id = ? AND user_id = ?", (row["id"], user_id)
        ).fetchone())
    return {"place": _as_place(row), "reviews": [dict(review) for review in reviews], "user_has_reviewed": has_reviewed}


@app.get("/api/places/{slug}")
def get_place(slug: str, request: Request) -> dict:
    user = current_user(request)
    return place_details(slug, user["id"] if user else None)


@app.post("/api/places/{slug}/reviews", status_code=status.HTTP_201_CREATED)
def create_review(slug: str, payload: ReviewCreate, request: Request) -> dict:
    check_origin(request)
    user = require_user(request)
    body = payload.body.strip()
    if len(body) < 8:
        raise HTTPException(status_code=422, detail="Yorum en az 8 karakter olmalı.")

    with db_session() as db:
        place = db.execute("SELECT id FROM places WHERE slug = ?", [slug]).fetchone()
        if place is None:
            raise HTTPException(status_code=404, detail="Durak bulunamadı.")
        created_at = utc_now()
        try:
            cursor = db.execute(
                """INSERT INTO reviews (place_id, user_id, author, rating, body, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (place["id"], user["id"], user["name"], payload.rating, body, created_at),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="Bu durak için zaten yorum yazdın.") from error
        review_id = cursor.lastrowid
    return {
        "id": review_id,
        "author": user["name"],
        "rating": payload.rating,
        "body": body,
        "created_at": created_at,
    }


@app.get("/api/favorites")
def get_favorites(request: Request) -> dict:
    user = require_user(request)
    with db_session() as db:
        rows = db.execute(
            """SELECT p.slug FROM favorites f JOIN places p ON p.id = f.place_id
               WHERE f.user_id = ? ORDER BY p.name COLLATE NOCASE""",
            (user["id"],),
        ).fetchall()
    return {"slugs": [row["slug"] for row in rows]}


@app.post("/api/favorites/{slug}")
def add_favorite(slug: str, request: Request) -> dict:
    check_origin(request)
    user = require_user(request)
    with db_session() as db:
        place = db.execute("SELECT id FROM places WHERE slug = ?", (slug,)).fetchone()
        if place is None:
            raise HTTPException(status_code=404, detail="Durak bulunamadı.")
        db.execute(
            "INSERT OR IGNORE INTO favorites (user_id, place_id) VALUES (?, ?)",
            (user["id"], place["id"]),
        )
    return {"saved": True}


@app.delete("/api/favorites/{slug}")
def remove_favorite(slug: str, request: Request) -> dict:
    check_origin(request)
    user = require_user(request)
    with db_session() as db:
        db.execute(
            "DELETE FROM favorites WHERE user_id = ? AND place_id = (SELECT id FROM places WHERE slug = ?)",
            (user["id"], slug),
        )
    return {"saved": False}


def route_place_ids(db: sqlite3.Connection, slugs: list[str]) -> list[int]:
    if len(set(slugs)) != len(slugs):
        raise HTTPException(status_code=422, detail="Aynı durak rotaya iki kez eklenemez.")
    placeholders = ",".join("?" for _ in slugs)
    rows = db.execute(f"SELECT id, slug, city_slug FROM places WHERE slug IN ({placeholders})", slugs).fetchall()
    ids = {row["slug"]: row["id"] for row in rows}
    if len(ids) != len(slugs):
        raise HTTPException(status_code=422, detail="Rotadaki duraklardan biri bulunamadı.")
    if len({row["city_slug"] for row in rows}) > 1:
        raise HTTPException(status_code=422, detail="Bir rotadaki duraklar aynı şehirde olmalı.")
    return [ids[slug] for slug in slugs]


def route_detail(db: sqlite3.Connection, route: sqlite3.Row) -> dict:
    places = db.execute(
        """SELECT p.slug, p.name, p.district, p.city_slug, p.latitude, p.longitude,
                  p.visit_minutes, rp.position FROM route_places rp
           JOIN places p ON p.id = rp.place_id
           WHERE rp.route_id = ? ORDER BY rp.position""",
        (route["id"],),
    ).fetchall()
    entries = [dict(place) for place in places]
    token = db.execute("SELECT share_token FROM routes WHERE id=?", (route["id"],)).fetchone()["share_token"]
    return {**dict(route), "places": entries, "metrics": route_metrics(entries),
            "share_enabled": bool(token), "share_path": "/r/" + token if token else None}


@app.get("/api/routes")
def list_routes(request: Request) -> dict:
    user = require_user(request)
    with db_session() as db:
        rows = db.execute(
            "SELECT id, title, notes, created_at, updated_at FROM routes WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
            (user["id"],),
        ).fetchall()
        items = [route_detail(db, row) for row in rows]
    return {"items": items}


@app.post("/api/routes", status_code=status.HTTP_201_CREATED)
def create_route(payload: RouteWrite, request: Request) -> dict:
    check_origin(request)
    user = require_user(request)
    title = payload.title.strip()
    if len(title) < 3:
        raise HTTPException(status_code=422, detail="Rota adı en az 3 karakter olmalı.")
    with db_session() as db:
        place_ids = route_place_ids(db, payload.place_slugs)
        now = utc_now()
        cursor = db.execute(
            "INSERT INTO routes (user_id, title, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (user["id"], title, payload.notes.strip(), now, now),
        )
        db.executemany(
            "INSERT INTO route_places (route_id, place_id, position) VALUES (?, ?, ?)",
            [(cursor.lastrowid, place_id, index) for index, place_id in enumerate(place_ids)],
        )
        row = db.execute(
            "SELECT id, title, notes, created_at, updated_at FROM routes WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        result = route_detail(db, row)
    return result


@app.put("/api/routes/{route_id}")
def update_route(route_id: int, payload: RouteWrite, request: Request) -> dict:
    check_origin(request)
    user = require_user(request)
    title = payload.title.strip()
    if len(title) < 3:
        raise HTTPException(status_code=422, detail="Rota adı en az 3 karakter olmalı.")
    with db_session() as db:
        route = db.execute("SELECT id FROM routes WHERE id = ? AND user_id = ?", (route_id, user["id"])).fetchone()
        if route is None:
            raise HTTPException(status_code=404, detail="Rota bulunamadı.")
        place_ids = route_place_ids(db, payload.place_slugs)
        db.execute(
            "UPDATE routes SET title = ?, notes = ?, updated_at = ? WHERE id = ?",
            (title, payload.notes.strip(), utc_now(), route_id),
        )
        db.execute("DELETE FROM route_places WHERE route_id = ?", (route_id,))
        db.executemany(
            "INSERT INTO route_places (route_id, place_id, position) VALUES (?, ?, ?)",
            [(route_id, place_id, index) for index, place_id in enumerate(place_ids)],
        )
        row = db.execute(
            "SELECT id, title, notes, created_at, updated_at FROM routes WHERE id = ?", (route_id,)
        ).fetchone()
        result = route_detail(db, row)
    return result


@app.delete("/api/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(route_id: int, request: Request) -> Response:
    check_origin(request)
    user = require_user(request)
    with db_session() as db:
        deleted = db.execute(
            "DELETE FROM routes WHERE id = ? AND user_id = ?", (route_id, user["id"])
        ).rowcount
        if not deleted:
            raise HTTPException(status_code=404, detail="Rota bulunamadı.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def normalized_place(payload: PlaceWrite) -> dict:
    data = payload.model_dump()
    for key, value in list(data.items()):
        if isinstance(value, str):
            data[key] = value.strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", data["slug"]):
        raise HTTPException(status_code=422, detail="Kısa ad yalnızca küçük harf, rakam ve tire içerebilir.")
    for key in ("name", "district", "address", "summary", "description", "duration", "best_for"):
        if not data[key]:
            raise HTTPException(status_code=422, detail="Tüm durak alanları doldurulmalı.")
    data["featured"] = int(data["featured"])
    if (data["latitude"] is None) != (data["longitude"] is None):
        raise HTTPException(422, "Enlem ve boylamı birlikte gir.")
    if data["source_url"] and (urlparse(data["source_url"]).scheme not in ("https", "http") or not urlparse(data["source_url"]).netloc):
        raise HTTPException(422, "Geçerli bir kaynak bağlantısı gir.")
    return data


def category_id_for(db: sqlite3.Connection, slug: str) -> int:
    row = db.execute("SELECT id FROM categories WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail="Geçerli bir kategori seç.")
    return row["id"]


@app.post("/api/admin/places", status_code=status.HTTP_201_CREATED)
def admin_create_place(payload: PlaceWrite, request: Request) -> dict:
    check_origin(request)
    require_admin(request)
    data = normalized_place(payload)
    with db_session() as db:
        data["category_id"] = category_id_for(db, data["category_slug"])
        if not db.execute("SELECT 1 FROM cities WHERE slug=?", (data["city_slug"],)).fetchone():
            raise HTTPException(422, "Geçerli bir şehir seç.")
        try:
            db.execute(
                """INSERT INTO places (slug, name, category_id, district, address, summary,
                   description, duration, best_for, art, featured, city_slug, latitude, longitude,
                   visit_minutes, indoor, family_friendly, wheelchair_accessible, accessibility_note, source_url)
                   VALUES (:slug, :name, :category_id, :district, :address, :summary,
                   :description, :duration, :best_for, :art, :featured, :city_slug, :latitude, :longitude,
                   :visit_minutes, :indoor, :family_friendly, :wheelchair_accessible, :accessibility_note, :source_url)""",
                data,
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="Bu kısa ad zaten kullanılıyor.") from error
    return place_details(data["slug"])["place"]


@app.put("/api/admin/places/{slug}")
def admin_update_place(slug: str, payload: PlaceWrite, request: Request) -> dict:
    check_origin(request)
    require_admin(request)
    data = normalized_place(payload)
    with db_session() as db:
        existing = db.execute("SELECT id FROM places WHERE slug = ?", (slug,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Durak bulunamadı.")
        data["category_id"] = category_id_for(db, data["category_slug"])
        data["id"] = existing["id"]
        if not db.execute("SELECT 1 FROM cities WHERE slug=?", (data["city_slug"],)).fetchone():
            raise HTTPException(422, "Geçerli bir şehir seç.")
        try:
            db.execute(
                """UPDATE places SET slug=:slug, name=:name, category_id=:category_id,
                   district=:district, address=:address, summary=:summary,
                   description=:description, duration=:duration, best_for=:best_for,
                   art=:art, featured=:featured, city_slug=:city_slug, latitude=:latitude, longitude=:longitude,
                   visit_minutes=:visit_minutes, indoor=:indoor, family_friendly=:family_friendly,
                   wheelchair_accessible=:wheelchair_accessible, accessibility_note=:accessibility_note,
                   source_url=:source_url WHERE id=:id""",
                data,
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="Bu kısa ad zaten kullanılıyor.") from error
    return place_details(data["slug"])["place"]


@app.delete("/api/admin/places/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_place(slug: str, request: Request) -> Response:
    check_origin(request)
    require_admin(request)
    with db_session() as db:
        deleted = db.execute("DELETE FROM places WHERE slug = ?", (slug,)).rowcount
        if not deleted:
            raise HTTPException(status_code=404, detail="Durak bulunamadı.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


install_features(app, sys.modules[__name__])
