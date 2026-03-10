"""
Smoke test contra el servidor FastAPI levantado localmente.

Uso:
    python scripts/smoke_test.py
    python scripts/smoke_test.py --base-url http://localhost:8000
    python scripts/smoke_test.py --admin-email admin@gfa.cl --admin-password SecretPass1!

Requiere:
    - Servidor corriendo: uvicorn app.main:app --reload
    - Un usuario admin activo en la BD con las credenciales indicadas
    - Un usuario customer activo en la BD con las credenciales indicadas
"""
from __future__ import annotations

import argparse
import sys

import httpx

# ─────────────────────────── Configuración ───────────────────────────────────

DEFAULTS = {
    "base_url": "http://localhost:8000",
    "admin_email": "admin@gfa.cl",
    "admin_password": "Admin123!",
    "customer_email": "cliente@gfa.cl",
    "customer_password": "Cliente123!",
}

# ─────────────────────────── Helpers ─────────────────────────────────────────

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
SKIP = "\033[93m~\033[0m"

results: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> bool:
    symbol = PASS if passed else FAIL
    line = f"  {symbol} {name}"
    if detail:
        line += f"  ({detail})"
    print(line)
    results.append((name, passed, detail))
    return passed


def section(title: str) -> None:
    print(f"\n── {title} ──")


# ─────────────────────────── Checks ──────────────────────────────────────────


def run(cfg: dict) -> None:
    base = cfg["base_url"].rstrip("/")
    client = httpx.Client(base_url=base, timeout=10)
    admin_token: str | None = None
    customer_token: str | None = None

    # ── 1. Server up ─────────────────────────────────────────────────────────
    section("Servidor")
    try:
        r = client.get("/")
        check("GET / responde", r.status_code < 500, f"HTTP {r.status_code}")
    except httpx.ConnectError:
        check("GET / responde", False, "No se puede conectar — ¿está corriendo el servidor?")
        print("\n  Levanta el servidor con:  uvicorn app.main:app --reload")
        sys.exit(1)

    # ── 2. Endpoint público de política de contraseñas ────────────────────────
    section("Endpoints públicos")
    r = client.get("/password/policy")
    check(
        "GET /password/policy → 200",
        r.status_code == 200,
        f"HTTP {r.status_code}",
    )
    if r.status_code == 200:
        check(
            "Respuesta contiene min_length",
            "min_length" in r.json(),
            str(r.json().keys()),
        )

    # ── 3. Login admin ────────────────────────────────────────────────────────
    section("Login admin")
    r = client.post(
        "/admin/login",
        json={"email": cfg["admin_email"], "password": cfg["admin_password"]},
    )
    ok = check("POST /admin/login → 200", r.status_code == 200, f"HTTP {r.status_code}")
    if ok:
        body = r.json()
        check("Respuesta tiene access_token", "access_token" in body)
        admin_token = body.get("access_token")
    else:
        print(f"    Detalle: {r.text[:200]}")

    # ── 4. Login customer ─────────────────────────────────────────────────────
    section("Login customer")
    r = client.post(
        "/customer/login",
        json={"email": cfg["customer_email"], "password": cfg["customer_password"]},
    )
    ok = check("POST /customer/login → 200", r.status_code == 200, f"HTTP {r.status_code}")
    if ok:
        customer_token = r.json().get("access_token")
    else:
        print(f"    Detalle: {r.text[:200]}")

    # ── 5. Endpoint protegido sin token → 401 ────────────────────────────────
    section("Protección JWT")
    r = client.post("/admin/password/change", json={})
    check("Sin token → 401", r.status_code == 401, f"HTTP {r.status_code}")

    # ── 6. Token admin en endpoint customer → 403 ────────────────────────────
    if admin_token:
        r = client.post(
            "/customer/password/change",
            json={"current_password": "x", "password": "x", "password_confirmation": "x"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        check(
            "Token admin en endpoint customer → 403",
            r.status_code == 403,
            f"HTTP {r.status_code}",
        )

    # ── 7. Token customer en endpoint admin → 403 ────────────────────────────
    if customer_token:
        r = client.post(
            "/admin/password/change",
            json={"current_password": "x", "password": "x", "password_confirmation": "x"},
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        check(
            "Token customer en endpoint admin → 403",
            r.status_code == 403,
            f"HTTP {r.status_code}",
        )

    # ── 8. Logout ─────────────────────────────────────────────────────────────
    section("Logout")
    if admin_token:
        r = client.post(
            "/admin/logout", headers={"Authorization": f"Bearer {admin_token}"}
        )
        check("POST /admin/logout → 200", r.status_code == 200, f"HTTP {r.status_code}")

    # ── Resumen ───────────────────────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'═' * 40}")
    print(f"  Resultado: {passed}/{total} checks OK")
    if passed < total:
        print(f"  {FAIL} {total - passed} checks fallaron")
        sys.exit(1)
    else:
        print(f"  {PASS} Todo en orden")


# ─────────────────────────── Entry point ─────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke test contra el servidor FastAPI")
    parser.add_argument("--base-url", default=DEFAULTS["base_url"])
    parser.add_argument("--admin-email", default=DEFAULTS["admin_email"])
    parser.add_argument("--admin-password", default=DEFAULTS["admin_password"])
    parser.add_argument("--customer-email", default=DEFAULTS["customer_email"])
    parser.add_argument("--customer-password", default=DEFAULTS["customer_password"])
    args = parser.parse_args()

    run(
        {
            "base_url": args.base_url,
            "admin_email": args.admin_email,
            "admin_password": args.admin_password,
            "customer_email": args.customer_email,
            "customer_password": args.customer_password,
        }
    )
