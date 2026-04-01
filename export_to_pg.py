"""Export MySQL gfa database to PostgreSQL-compatible SQL."""
import pymysql
from datetime import datetime, date
from decimal import Decimal

conn = pymysql.connect(
    host="127.0.0.1", port=3306, user="root", password="",
    database="gfa", charset="utf8mb4",
)
cur = conn.cursor()

cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]

skip_tables = {
    "migrations", "cache", "cache_locks", "failed_jobs",
    "job_batches", "jobs", "sessions",
}

data_lines: list[str] = []
tables_exported: set[str] = set()

for table in tables:
    if table in skip_tables:
        continue

    cur.execute(f"DESCRIBE `{table}`")
    columns = cur.fetchall()
    col_names = [c[0] for c in columns]

    cur.execute(f"SELECT * FROM `{table}`")
    rows = cur.fetchall()

    if not rows:
        continue

    tables_exported.add(table)

    for row in rows:
        values = []
        for val in row:
            if val is None:
                values.append("NULL")
            elif isinstance(val, bool):
                values.append("TRUE" if val else "FALSE")
            elif isinstance(val, (int, float)):
                values.append(str(val))
            elif isinstance(val, Decimal):
                values.append(str(val))
            elif isinstance(val, datetime):
                values.append(f"'{val.isoformat()}'")
            elif isinstance(val, date):
                values.append(f"'{val.isoformat()}'")
            elif isinstance(val, bytes):
                values.append(f"E'\\\\x{val.hex()}'")
            elif isinstance(val, str):
                escaped = val.replace("'", "''")
                # Handle backslashes for PostgreSQL E-string
                if "\\" in escaped:
                    escaped = escaped.replace("\\", "\\\\")
                    values.append(f"E'{escaped}'")
                else:
                    values.append(f"'{escaped}'")
            else:
                escaped = str(val).replace("'", "''")
                values.append(f"'{escaped}'")

        cols_str = ", ".join(f'"{c}"' for c in col_names)
        vals_str = ", ".join(values)
        data_lines.append(f'INSERT INTO "{table}" ({cols_str}) VALUES ({vals_str});')

print(f"Total INSERT statements: {len(data_lines)}")
print(f"Tables with data: {len(tables_exported)}")
print(f"Tables: {', '.join(sorted(tables_exported))}")

with open("db_dump_pg.sql", "w", encoding="utf-8") as f:
    for line in data_lines:
        f.write(line + "\n")
    # Reset sequences for auto-increment columns
    f.write("\n-- Reset sequences\n")
    for table in sorted(tables_exported):
        f.write(
            f"SELECT setval(pg_get_serial_sequence('\"{table}\"', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM \"{table}\"), 0) + 1, false);\n"
        )

conn.close()
print("Written to db_dump_pg.sql")
