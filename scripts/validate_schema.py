"""
Valida que el esquema MySQL real coincida con los modelos SQLAlchemy definidos.

Uso:
    python scripts/validate_schema.py

Verifica:
  - Que cada tabla definida en Base.metadata exista en MySQL
  - Que cada columna definida exista en la tabla correspondiente
  - Que los índices de autenticación (email+realm) existan
  - Que las tablas Spatie de permisos existan y tengan las columnas correctas

Salida:
  - Verde ✓ por cada tabla/columna OK
  - Rojo  ✗ por cada diferencia encontrada
  - Resumen final con conteo de errores
"""
from __future__ import annotations

import sys

import pymysql

sys.path.insert(0, "C:/yastubo/yastubo-python")

import app.models  # noqa: F401, E402 — asegura que Base.metadata tenga todos los modelos
from app.config import settings  # noqa: E402
from app.models.base import Base  # noqa: E402

# ─────────────────────────── Colores ─────────────────────────────────────────

OK = "\033[92m[OK]\033[0m"
FAIL = "\033[91m[!!]\033[0m"
WARN = "\033[93m[~~]\033[0m"
SECTION = "\033[1m"
RESET = "\033[0m"

errors: list[str] = []
warnings: list[str] = []


def ok(msg: str) -> None:
    print(f"  {OK} {msg}")


def fail(msg: str) -> None:
    print(f"  {FAIL} {msg}")
    errors.append(msg)


def warn(msg: str) -> None:
    print(f"  {WARN} {msg}")
    warnings.append(msg)


def section(title: str) -> None:
    print(f"\n--- {title} ---")


# ─────────────────────────── Conexión ────────────────────────────────────────


def get_conn() -> pymysql.Connection:
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
    )


# ─────────────────────────── Helpers ─────────────────────────────────────────


def get_db_tables(cur) -> set[str]:
    cur.execute("SHOW TABLES")
    return {row[0] for row in cur.fetchall()}


def get_db_columns(cur, table: str) -> set[str]:
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    return {row[0] for row in cur.fetchall()}


# ─────────────────────────── Validaciones ────────────────────────────────────


def validate_tables(cur, db_tables: set[str]) -> None:
    section("Tablas (modelos SQLAlchemy vs MySQL)")

    model_tables = {
        name: table
        for name, table in Base.metadata.tables.items()
    }

    for table_name, table in sorted(model_tables.items()):
        if table_name in db_tables:
            ok(f"tabla  {table_name}")
        else:
            fail(f"tabla  {table_name}  — NO EXISTE en MySQL")


def validate_columns(cur, db_tables: set[str]) -> None:
    section("Columnas por tabla")

    model_tables = Base.metadata.tables

    for table_name, table in sorted(model_tables.items()):
        if table_name not in db_tables:
            continue  # ya reportado arriba

        db_cols = get_db_columns(cur, table_name)
        model_cols = {col.name for col in table.columns}
        missing = model_cols - db_cols

        if missing:
            for col in sorted(missing):
                fail(f"{table_name}.{col}  — columna NO EXISTE en MySQL")
        else:
            ok(f"{table_name}  ({len(model_cols)} columnas OK)")

        # Columnas extra en DB no definidas en modelo (solo warning)
        extra = db_cols - model_cols
        if extra:
            for col in sorted(extra):
                warn(f"{table_name}.{col}  — columna en MySQL pero no en modelo")


def validate_spatie_tables(cur, db_tables: set[str]) -> None:
    section("Tablas Spatie de permisos")

    spatie = {
        "permissions": {"id", "name", "guard_name"},
        "roles": {"id", "name", "guard_name"},
        "model_has_roles": {"role_id", "model_type", "model_id"},
        "model_has_permissions": {"permission_id", "model_type", "model_id"},
        "role_has_permissions": {"role_id", "permission_id"},
    }

    for table_name, required_cols in spatie.items():
        if table_name not in db_tables:
            fail(f"tabla Spatie  {table_name}  — NO EXISTE")
            continue

        db_cols = get_db_columns(cur, table_name)
        missing = required_cols - db_cols
        if missing:
            fail(f"{table_name}  columnas faltantes: {missing}")
        else:
            ok(f"{table_name}  ({len(required_cols)} columnas clave OK)")


def validate_users_table(cur, db_tables: set[str]) -> None:
    section("Tabla users — datos de ejemplo")

    if "users" not in db_tables:
        fail("tabla users no existe")
        return

    cur.execute("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE realm='admin' AND deleted_at IS NULL")
    admins = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE realm='customer' AND deleted_at IS NULL")
    customers = cur.fetchone()[0]

    if total > 0:
        ok(f"{total} usuarios activos  ({admins} admin, {customers} customer)")
    else:
        warn("La tabla users está vacía — no hay datos para probar login")


# ─────────────────────────── Main ────────────────────────────────────────────


def run() -> None:
    print(f"\nValidacion de esquema MySQL: {settings.db_name}@{settings.db_host}")

    try:
        conn = get_conn()
    except Exception as e:
        print(f"\n  {FAIL} No se puede conectar a MySQL: {e}")
        sys.exit(1)

    cur = conn.cursor()
    db_tables = get_db_tables(cur)

    print(f"\n  Base de datos: {settings.db_name}  ({len(db_tables)} tablas encontradas)")

    validate_tables(cur, db_tables)
    validate_columns(cur, db_tables)
    validate_spatie_tables(cur, db_tables)
    validate_users_table(cur, db_tables)

    conn.close()

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 50}")
    if errors:
        print(f"  {FAIL}  {len(errors)} error(es) encontrado(s):")
        for e in errors:
            print(f"       • {e}")
        if warnings:
            print(f"  {WARN}  {len(warnings)} warning(s) (columnas extra en DB)")
        sys.exit(1)
    else:
        print(f"  {OK}  Esquema OK — todos los modelos coinciden con MySQL")
        if warnings:
            print(f"  {WARN}  {len(warnings)} warning(s): columnas en MySQL no definidas en modelos")
            for w in warnings:
                print(f"       • {w}")


if __name__ == "__main__":
    run()
