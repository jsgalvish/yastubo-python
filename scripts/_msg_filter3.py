import sys, re

msg = sys.stdin.read().strip()
first_line = msg.split('\n')[0]
rest = msg[len(first_line):]

# Los "Step X" tienen el em-dash almacenado como bytes UTF-8 leidos en Latin-1
# Aparece como los 3 chars: U+00E2 U+20AC U+201D  (â€")
# Usamos un patron que acepta cualquier separador entre Step N y migra

step_match = re.match(
    r"feat\(admin\): Step (\d+)\s*.+?migra\s+(.+)",
    first_line
)

if step_match:
    num = step_match.group(1)
    what = step_match.group(2).strip()

    # Normalizar lo que viene despues de "migra"
    what = re.sub(r'\s+a FastAPI.*', '', what)
    what = what.replace("Dashboard + ConfigController", "Dashboard y ConfigController")
    what = what.replace("TemplateController + TemplateVersionController", "TemplateController y TemplateVersionController")
    what = what.replace("Capitados Lotes y Reportes Mensuales", "capitados, lotes y reportes mensuales")
    what = what.replace("Capitados Core (Persons + Contracts)", "capitados core (personas y contratos)")
    what = what.replace("BusinessUnitApiController", "unidades de negocio")
    what = what.replace("RegaliasController", "controlador de regalias")
    what = what.replace("CoverageCatalog + PlanVersionCoverage", "catalogo de coberturas y versiones de plan")
    what = what.replace("PlanVersionController + AgeSurcharges", "versiones de plan y recargos por edad")
    what = what.replace("ProductController", "ProductController con CRUD y tests")

    # Limpiar trailing "a FastAPI (CRUD + tests)" etc
    what = re.sub(r'\s*\(CRUD.*$', '', what)

    print(f"feat(admin): paso {num} - migra {what} a FastAPI" + rest)
    sys.exit(0)

print(msg)
