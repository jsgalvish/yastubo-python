from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Global Funeral Assistance"
    app_env: str = "local"
    app_debug: bool = True
    app_url: str = "http://localhost:8001"
    app_timezone: str = "UTC"

    # Database
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "gfa"
    db_user: str = "gfa"
    db_password: str = "gfa"

    # Auth
    secret_key: str = "change-me-in-production"
    bcrypt_rounds: int = 12
    session_lifetime_minutes: int = 30

    # Storage
    app_storage_dir: str = ""

    # Módulos
    module_users: bool = True
    module_plantillas: bool = True
    module_roles: bool = False
    module_company: bool = True
    module_units: bool = False
    module_config: bool = True
    module_country: bool = True
    module_country_zones: bool = True
    module_coverage: bool = True
    module_productos: bool = True

    # Capitados batch logs
    capitados_batch_item_log_applied: bool = True
    capitados_batch_item_log_rejected: bool = True
    capitados_batch_item_log_incongruence: bool = True
    capitados_batch_item_log_duplicated: bool = True

    # IP / GeoIP
    ip_country_provider: str = "iplocate"
    ip_country_fallback_iso2: str = "CL"
    ip_country_cache_ttl_seconds: int = 86400

    # Empresa
    company_name: str = "Global Funeral Assistance"
    company_short_name: str = "GFA"

    @property
    def db_url(self) -> str:
        """URL async para SQLAlchemy (aiomysql)."""
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def db_url_sync(self) -> str:
        """URL sync para Alembic (pymysql)."""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
