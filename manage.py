"""Local management commands for the İstanbul guide."""

import argparse
import getpass
import re
import sqlite3

from main import db_session, hash_password, utc_now


def create_admin() -> None:
    name = input("Yönetici adı: ").strip()
    email = input("E-posta: ").strip().lower()
    password = getpass.getpass("Parola (en az 8 karakter): ")
    if len(name) < 2 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(password) < 8:
        raise SystemExit("Geçerli ad, e-posta ve en az 8 karakterlik parola gerekli.")
    with db_session() as db:
        row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            db.execute(
                "UPDATE users SET name = ?, password_hash = ?, role = 'admin' WHERE id = ?",
                (name, hash_password(password), row["id"]),
            )
            print("Yönetici hesabı güncellendi.")
        else:
            try:
                db.execute(
                    "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)",
                    (name, email, hash_password(password), utc_now()),
                )
            except sqlite3.IntegrityError as error:
                raise SystemExit("Hesap oluşturulamadı.") from error
            print("Yönetici hesabı oluşturuldu.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Şehir Arası yönetimi")
    parser.add_argument("command", choices=["create-admin"])
    arguments = parser.parse_args()
    if arguments.command == "create-admin":
        create_admin()
