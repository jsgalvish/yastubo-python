import sys, re

msg = sys.stdin.read().strip()
first_line = msg.split('\n')[0]
rest = msg[len(first_line):]

# Patron: feat(admin): Step N - ... a FastAPI
step_match = re.match(
    r"feat\(admin\): Step (\d+)\s*[\u2014\-]+\s*migra\s+(.+?)\s+a FastAPI",
    first_line
)
if step_match:
    num = step_match.group(1)
    what = step_match.group(2)
    # Traducir nombres tecnicos
    what = what.replace("Dashboard + ConfigController", "Dashboard y ConfigController")
    what = what.replace("TemplateController + TemplateVersionController", "TemplateController y TemplateVersionController")
    what = what.replace("Capitados Lotes y Reportes Mensuales", "capitados, lotes y reportes mensuales")
    what = what.replace("Capitados Core (Persons + Contracts)", "capitados core (personas y contratos)")
    what = what.replace("BusinessUnitApiController", "unidades de negocio")
    what = what.replace("RegaliasController", "controlador de regalias")
    what = what.replace("CoverageCatalog + PlanVersionCoverage", "catalogo de coberturas y versiones de plan")
    what = what.replace("PlanVersionController + AgeSurcharges", "versiones de plan y recargos por edad")
    what = what.replace("ProductController", "ProductController")
    print(f"feat(admin): paso {num} - migra {what} a FastAPI" + rest)
    sys.exit(0)

# feat(admin): Step N - ... (CRUD + tests)
step_match2 = re.match(
    r"feat\(admin\): Step (\d+)\s*[\u2014\-]+\s*(.+)",
    first_line
)
if step_match2:
    num = step_match2.group(1)
    what = step_match2.group(2)
    what = what.replace("migra ProductController a FastAPI (CRUD + tests)", "migra ProductController a FastAPI con CRUD y tests")
    print(f"feat(admin): paso {num} - {what}" + rest)
    sys.exit(0)

# Commits especificos restantes
MAPPING = {
    "feat: Complete PHP-to-Python API migration":
        "feat: completar migracion PHP a Python - todos los endpoints, servicios e infraestructura",
    "refactor: auditor":
        "refactor: auditoria de calidad - CORS, lifespan, conftest y modelos de respuesta tipados",
    "fix(admin): last_name requerido":
        "fix(admin): campo apellido requerido en creacion de usuario (NOT NULL en MySQL)",
    "feat(admin): gesti":
        "feat(admin): gestion de usuarios - CRUD, borrado logico y restauracion",
    "feat(auth): autenticaci":
        "feat(auth): autenticacion JWT con separacion de dominios admin y customer",
    "test(roles): cubrir permiso v":
        "test(roles): cubrir permisos por rol y token expirado en endpoints protegidos",
    "chore(setup)":
        "configuracion: estructura base del proyecto FastAPI con entorno y dependencias",
}

for prefix, replacement in MAPPING.items():
    if first_line.startswith(prefix):
        print(replacement + rest)
        sys.exit(0)

print(msg)
