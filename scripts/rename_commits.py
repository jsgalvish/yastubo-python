"""
Script para reescribir los mensajes de commit al español.
Uso: python scripts/rename_commits.py
"""
import subprocess
import os

# Mapeo: mensaje original (exacto) → mensaje en español
MAPPING = {
    "test: 434 tests passing, 37% coverage across all modules": (
        "test: 434 pruebas exitosas con cobertura del 37% en todos los módulos"
    ),
    "chore: remove duplicate assets, empty placeholder dirs and untracked pycache": (
        "limpieza: eliminar assets duplicados, carpetas vacías heredadas y pycache del repo"
    ),
    "feat: add observability stack with Prometheus and Grafana": (
        "feat: agregar stack de observabilidad con Prometheus y Grafana"
    ),
    "feat: restructure monolith into 6 microservices with Docker orchestration": (
        "feat: reestructurar monolito en 6 microservicios con orquestación Docker"
    ),
    "fix: Mejoras al template PDF - layout, espaciado y estilos de coberturas": (
        "fix: mejorar template PDF — layout, espaciado y estilos de coberturas"
    ),
    "feat: Complete PHP-to-Python API migration — all endpoints, services, and infrastructure": (
        "feat: completar migración PHP→Python — todos los endpoints, servicios e infraestructura"
    ),
    "fix: PDF layout with fixed header/footer and full-bleed background on all pages": (
        "fix: PDF con header/footer fijo y fondo a sangre en todas las páginas"
    ),
    "fix: PDF template with running headers/footers and full-bleed background": (
        "fix: template PDF con encabezados y pies de página corridos, fondo a sangre"
    ),
    "fix: Improve PDF template - full bleed background, CSS contact bar, fix encoding": (
        "fix: mejorar template PDF — fondo a sangre, barra de contacto CSS, corrección de encoding"
    ),
    "feat: Add PDF generation with WeasyPrint for capitated contracts": (
        "feat: generación de PDF con xhtml2pdf para contratos capitados"
    ),
    "feat(admin): Step 18 — migra Dashboard + ConfigController a FastAPI": (
        "feat(admin): paso 18 — migra Dashboard y ConfigController a FastAPI"
    ),
    "feat(admin): Step 17 — migra TemplateController + TemplateVersionController a FastAPI": (
        "feat(admin): paso 17 — migra TemplateController y TemplateVersionController a FastAPI"
    ),
    "feat(admin): Step 16 — migra Capitados Lotes y Reportes Mensuales a FastAPI": (
        "feat(admin): paso 16 — migra capitados, lotes y reportes mensuales a FastAPI"
    ),
    "feat(admin): Step 15 — migra Capitados Core (Persons + Contracts) a FastAPI": (
        "feat(admin): paso 15 — migra capitados core (personas y contratos) a FastAPI"
    ),
    "feat(admin): Step 14 — migra BusinessUnitApiController a FastAPI": (
        "feat(admin): paso 14 — migra unidades de negocio a FastAPI"
    ),
    "feat(admin): Step 13 — migra RegaliasController a FastAPI": (
        "feat(admin): paso 13 — migra controlador de regalías a FastAPI"
    ),
    "feat(admin): Step 12 — migra CoverageCatalog + PlanVersionCoverage a FastAPI": (
        "feat(admin): paso 12 — migra catálogo de coberturas y versiones de plan a FastAPI"
    ),
    "feat(admin): Step 11 — migra PlanVersionController + AgeSurcharges a FastAPI": (
        "feat(admin): paso 11 — migra versiones de plan y recargos por edad a FastAPI"
    ),
    "refactor: auditoría de skills — CORS, lifespan, conftest, response models tipados": (
        "refactor: auditoría de calidad — CORS, lifespan, conftest y modelos de respuesta tipados"
    ),
    "feat(admin): Step 10 — migra ProductController a FastAPI (CRUD + tests)": (
        "feat(admin): paso 10 — migra ProductController a FastAPI con CRUD y tests"
    ),
    "Completa API geo y empresas: respuestas PHP-compatible, validaciones y tests": (
        "feat: completar API geo y empresas — respuestas compatibles PHP, validaciones y tests"
    ),
    "Agrega API de empresas y usuarios de comisiones; tabla de pasos en README": (
        "feat: agregar API de empresas y usuarios de comisiones; tabla de avance en README"
    ),
    "Agrega API de catalogos geograficos: paises y zonas": (
        "feat: agregar API de catálogos geográficos — países y zonas"
    ),
    "feat(admin): ACL API - roles permisos y matriz de asignacion": (
        "feat(admin): API de ACL — roles, permisos y matriz de asignación"
    ),
    "fix(admin): last_name requerido en creación de usuario (NOT NULL en MySQL)": (
        "fix(admin): campo apellido requerido en creación de usuario (NOT NULL en MySQL)"
    ),
    "feat(admin): gestión de usuarios admin (CRUD + soft-delete + restore)": (
        "feat(admin): gestión de usuarios — CRUD, borrado lógico y restauración"
    ),
    "fix(models): alinear columnas SQLAlchemy con esquema real MySQL": (
        "fix(modelos): alinear columnas SQLAlchemy con el esquema real de MySQL"
    ),
    "chore(scripts): agregar validador de esquema y script de usuario de prueba": (
        "utilidades: agregar validador de esquema y script de usuario de prueba"
    ),
    "test(roles): cubrir permiso vía rol y token expirado en endpoints protegidos": (
        "test(roles): cubrir permisos por rol y token expirado en endpoints protegidos"
    ),
    "feat(roles): sistema de roles y permisos Spatie-like": (
        "feat(roles): sistema de roles y permisos granular estilo Spatie"
    ),
    "test(auth): cubrir historial de passwords y guardia de realm cruzado": (
        "test(auth): cubrir historial de contraseñas y separación de dominios admin/customer"
    ),
    "feat(auth): autenticación JWT para dominios admin y customer": (
        "feat(auth): autenticación JWT con separación de dominios admin y customer"
    ),
    "feat(models): traducir modelos Eloquent a SQLAlchemy 2.0": (
        "feat(modelos): traducir modelos Eloquent de Laravel a SQLAlchemy 2.0"
    ),
    "feat(support): migrar clases de soporte 1:1 desde PHP": (
        "feat(soporte): migrar clases de soporte 1:1 desde PHP"
    ),
    "chore(setup): configuración base del proyecto FastAPI": (
        "configuración: estructura base del proyecto FastAPI con entorno y dependencias"
    ),
    "chore(init): estructura de carpetas 1:1 con monolito PHP": (
        "inicio: estructura de carpetas 1:1 con el monolito PHP como referencia"
    ),
}

def get_commits():
    result = subprocess.run(
        ["git", "log", "--format=%H\t%s", "--reverse"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    commits = []
    for line in result.stdout.strip().split("\n"):
        if "\t" in line:
            hash_, subject = line.split("\t", 1)
            commits.append((hash_, subject))
    return commits

def main():
    commits = get_commits()
    print(f"Total commits encontrados: {len(commits)}\n")
    for hash_, subject in commits:
        new_msg = MAPPING.get(subject)
        if new_msg:
            print(f"  RENOMBRAR: {hash_[:8]} | {subject[:60]}")
            print(f"         → {new_msg[:60]}\n")
        else:
            print(f"  OK (ya en español): {hash_[:8]} | {subject[:60]}\n")

if __name__ == "__main__":
    main()
