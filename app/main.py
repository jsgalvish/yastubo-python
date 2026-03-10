from fastapi import FastAPI

from app.config import settings
from app.http.controllers.admin import acl_controller as admin_acl
from app.http.controllers.admin import users_controller as admin_users
from app.http.controllers.auth import login_controller, password_controller

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.app_debug,
)

app.include_router(login_controller.router)
app.include_router(password_controller.router)
app.include_router(admin_users.router)
app.include_router(admin_acl.router)


@app.get("/")
def root():
    return {"status": "ok", "app": settings.app_name}
