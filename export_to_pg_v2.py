"""Export MySQL gfa → PostgreSQL-compatible SQL, matching PG schema columns."""
import paramiko
import pymysql
from datetime import datetime, date
from decimal import Decimal

# ── Get PG column names from VPS ──────────────────────────────────────
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("45.76.20.245", username="root", password="N5[qMM8,W-c3GyUZ", timeout=15)

cmd = (
    "PGPASSWORD=gfa_prod_2026 psql -h 127.0.0.1 -U gfa -d gfa -t -c \""
    "SELECT table_name || '|' || string_agg(column_name || ':' || data_type, ',' ORDER BY ordinal_position) "
    "FROM information_schema.columns WHERE table_schema = 'public' "
    "GROUP BY table_name ORDER BY table_name;\""
)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
pg_raw = stdout.read().decode().strip()
ssh.close()

pg_cols: dict[str, list[str]] = {}
pg_types: dict[str, dict[str, str]] = {}  # table -> {col: type}
for line in pg_raw.split("\n"):
    line = line.strip()
    if "|" in line:
        table, cols = line.split("|", 1)
        table = table.strip()
        pg_cols[table] = []
        pg_types[table] = {}
        for col_type in cols.split(","):
            col_type = col_type.strip()
            if ":" in col_type:
                col, dtype = col_type.rsplit(":", 1)
                col = col.strip()
                pg_cols[table].append(col)
                pg_types[table][col] = dtype.strip()
            else:
                pg_cols[table].append(col_type)

print(f"PG tables found: {len(pg_cols)}")

# ── Get MySQL data ────────────────────────────────────────────────────
conn = pymysql.connect(
    host="127.0.0.1", port=3306, user="root", password="",
    database="gfa", charset="utf8mb4",
)
cur = conn.cursor()
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]

lines: list[str] = []
stats: dict[str, int] = {}


def escape_val(val: object, is_boolean: bool = False) -> str:
    if val is None:
        return "NULL"
    if is_boolean:
        # MySQL stores booleans as 0/1 tinyint
        return "TRUE" if val else "FALSE"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, datetime):
        return f"'{val.isoformat()}'"
    if isinstance(val, date):
        return f"'{val.isoformat()}'"
    if isinstance(val, bytes):
        return f"E'\\\\x{val.hex()}'"
    if isinstance(val, str):
        escaped = val.replace("'", "''")
        if "\\" in escaped:
            escaped = escaped.replace("\\", "\\\\")
            return f"E'{escaped}'"
        return f"'{escaped}'"
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"


for table in tables:
    if table not in pg_cols:
        continue

    target_cols = pg_cols[table]

    cur.execute(f"DESCRIBE `{table}`")
    mysql_cols = [c[0] for c in cur.fetchall()]

    # Only columns that exist in BOTH MySQL and PG
    common = [c for c in mysql_cols if c in target_cols]
    if not common:
        continue

    col_indices = [mysql_cols.index(c) for c in common]

    cur.execute(f"SELECT * FROM `{table}`")
    rows = cur.fetchall()
    if not rows:
        continue

    stats[table] = len(rows)

    # Detect boolean columns
    bool_flags = [
        pg_types.get(table, {}).get(common[i], "") == "boolean"
        for i in range(len(common))
    ]

    for row in rows:
        values = [
            escape_val(row[col_indices[i]], is_boolean=bool_flags[i])
            for i in range(len(common))
        ]
        cols_str = ", ".join(f'"{c}"' for c in common)
        vals_str = ", ".join(values)
        lines.append(f'INSERT INTO "{table}" ({cols_str}) VALUES ({vals_str});')

conn.close()

# ── Write SQL file ────────────────────────────────────────────────────
with open("db_dump_pg_v2.sql", "w", encoding="utf-8") as f:
    for line in lines:
        f.write(line + "\n")

    f.write("\n-- Reset sequences\n")
    for table in sorted(pg_cols.keys()):
        if "id" in pg_cols[table]:
            f.write(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f'COALESCE((SELECT MAX(id) FROM "{table}"), 0) + 1, false);\n'
            )

print(f"\nTables exported: {len(stats)}")
print(f"Total INSERTs: {len(lines)}")
for t, cnt in sorted(stats.items()):
    print(f"  {t}: {cnt}")
print("\nWritten to db_dump_pg_v2.sql")
