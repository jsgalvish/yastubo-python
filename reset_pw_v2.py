"""Reset admin password using Python directly on VPS."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("45.76.20.245", username="root", password="N5[qMM8,W-c3GyUZ", timeout=15)

# Write a complete reset script that runs on the VPS with psycopg2
reset_script = r"""
import asyncio
import asyncpg

async def main():
    import bcrypt
    # Generate hash
    pw_hash = bcrypt.hashpw(b"Admin2026!", bcrypt.gensalt(rounds=12)).decode("utf-8")
    print(f"Generated hash: {pw_hash}")

    conn = await asyncpg.connect(
        host="127.0.0.1", port=5432,
        user="gfa", password="gfa_prod_2026", database="gfa",
    )

    # Update using parameterized query (no shell escaping issues)
    result = await conn.execute(
        "UPDATE users SET password = $1, force_password_change = false WHERE id = 1",
        pw_hash,
    )
    print(f"Update result: {result}")

    # Verify
    row = await conn.fetchrow("SELECT password FROM users WHERE id = 1")
    print(f"Stored: {row['password']}")
    print(f"Match: {pw_hash == row['password']}")

    await conn.close()

asyncio.run(main())
"""

sftp = ssh.open_sftp()
with sftp.file("/tmp/reset_pw.py", "w") as f:
    f.write(reset_script)
sftp.close()

# Run on VPS natively (asyncpg already installed)
stdin, stdout, stderr = ssh.exec_command(
    "python3 /tmp/reset_pw.py", timeout=15
)
print(stdout.read().decode().strip())
err = stderr.read().decode().strip()
if err:
    print(f"ERR: {err}")

# Now test login
import json
payload = json.dumps({"email": "arieltapia@gmail.com", "password": "Admin2026!"})
cmd = f"curl -s -X POST http://localhost:8001/admin/login -H 'Content-Type: application/json' -d '{payload}'"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
print(f"\nLogin: {stdout.read().decode().strip()[:500]}")

ssh.close()
