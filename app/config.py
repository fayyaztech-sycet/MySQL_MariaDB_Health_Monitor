"""Central configuration, loaded from environment variables via pydantic-settings."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- MySQL / MariaDB target ---
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "monitor"
    mysql_password: str = "changeme"
    mysql_database: str = ""

    # --- Web server ---
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # --- Storage ---
    sqlite_path: str = "monitor.db"

    # --- Collection cadences (seconds) ---
    system_interval: int = 5
    mysql_interval: int = 60
    analyze_interval: int = 3600
    report_hour: int = 2  # hour-of-day (0-23) for the daily report

    # --- Alert thresholds ---
    alert_cpu_high: float = 90.0
    alert_mem_avail_low: float = 10.0  # percent of RAM that must remain available
    alert_disk_high: float = 90.0
    alert_slow_query_ms: float = 5000.0
    alert_deadlock_trigger: int = 1

    # --- API auth ---
    api_token: str = "changeme-token"

    # --- Dashboard auth ---
    dashboard_password_hash: str = ""   # bcrypt hash; empty = no password required
    session_secret: str = "change-this-secret-key"  # used to sign session cookies

    # --- Paths ---
    report_dir: str = "reports"

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.sqlite_path}"

    @property
    def mysql_connector_kwargs(self) -> dict:
        """Keyword args for mysql.connector.connect()."""
        kwargs = {
            "host": self.mysql_host,
            "port": self.mysql_port,
            "user": self.mysql_user,
            "password": self.mysql_password,
            "connection_timeout": 5,
        }
        if self.mysql_database:
            kwargs["database"] = self.mysql_database
        return kwargs


@lru_cache
def get_settings() -> Settings:
    return Settings()
