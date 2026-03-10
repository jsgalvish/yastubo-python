"""
Crea (o actualiza) un usuario de prueba en la BD para el smoke test.
Uso: python scripts/create_test_user.py
Borra después con: python scripts/create_test_user.py --delete
"""
from __future__ import annotations

import argparse
import sys

import bcrypt
import pymysql

sys.path.insert(0, "C:/yastubo/yastubo-python")
from app.config import settings  # noqa: E402

TEST_EMAIL = "smoketest@gfa.dev"
TEST_PASSWORD = "SmokeTest123!"
TEST_REALM = "admin"


def get_conn():
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
    )


def create(conn):
    hashed = bcrypt.hashpw(TEST_PASSWORD.encode(), bcrypt.gensalt(rounds=12)).decode()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users
                (realm, email, password, force_password_change,
                 first_name, last_name, status, locale, timezone, created_at, updated_at)
            VALUES (%s, %s, %s, 0, 'Smoke', 'Test', 'active', 'es', 'America/Santiago', NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                password = VALUES(password),
                status = 'active',
                deleted_at = NULL,
                updated_at = NOW()
            """,
            (TEST_REALM, TEST_EMAIL, hashed),
        )
    conn.commit()
    print(f"✓ Usuario creado/actualizado: {TEST_EMAIL} / {TEST_PASSWORD}")


def delete(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE email = %s AND realm = %s", (TEST_EMAIL, TEST_REALM))
    conn.commit()
    print(f"✓ Usuario eliminado: {TEST_EMAIL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="Eliminar el usuario de prueba")
    args = parser.parse_args()

    conn = get_conn()
    try:
        delete(conn) if args.delete else create(conn)
    finally:
        conn.close()
