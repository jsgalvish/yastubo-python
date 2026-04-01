"""Reset admin password on VPS PostgreSQL."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("45.76.20.245", username="root", password="N5[qMM8,W-c3GyUZ", timeout=15)

# Write hash script to VPS
script = 'import bcrypt\nh = bcrypt.hashpw(b"Admin2026!", bcrypt.gensalt(rounds=12)).decode()\nh = h.replace("$2b$", "$2y$", 1)\nprint(h)\n'
sftp = ssh.open_sftp()
with sftp.file("/tmp/genhash.py", "w") as f:
    f.write(script)
sftp.close()

# Generate hash inside Docker container
stdin, stdout, stderr = ssh.exec_command(
    "docker cp /tmp/genhash.py yastubo-auth-1:/tmp/genhash.py && "
    "docker exec yastubo-auth-1 python3 /tmp/genhash.py",
    timeout=10,
)
hashed = stdout.read().decode().strip()
print(f"Hash: {hashed}")

if not hashed.startswith("$2y$"):
    print("ERROR: hash format wrong")
    ssh.close()
    exit(1)

# Update in DB
sql = f"UPDATE users SET password = '{hashed}', force_password_change = false WHERE id = 1;"
cmd = f"PGPASSWORD=gfa_prod_2026 psql -h 127.0.0.1 -U gfa -d gfa -c \"{sql}\""
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
print(stdout.read().decode().strip())

# Test login
import json
payload = json.dumps({"email": "arieltapia@gmail.com", "password": "Admin2026!"})
cmd = f"curl -s -X POST http://localhost:8001/admin/login -H 'Content-Type: application/json' -d '{payload}'"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
resp = stdout.read().decode().strip()
print(f"Login: {resp[:500]}")

ssh.close()
