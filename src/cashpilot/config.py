import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(os.environ.get("CASHPILOT_ROOT", str(Path(__file__).resolve().parents[2]))).resolve()


@dataclass(frozen=True)
class Settings:
    mode: str = "hosted"
    database_url: str = ""
    database_url_direct: str = ""
    sqlite_path: str = "cashpilot.sqlite"

    @property
    def storage_url(self):
        if self.mode == "local":
            return "sqlite:///" + str((ROOT / self.sqlite_path).resolve())
        if self.mode != "hosted":
            raise ValueError("Choose hosted or explicit local mode")
        if not self.database_url:
            return ""
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Hosted writes require PostgreSQL")
        return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    @property
    def migration_url(self):
        value = (
            self.database_url_direct.replace("postgresql://", "postgresql+psycopg://", 1)
            if self.database_url_direct
            else self.storage_url
        )
        if not value:
            raise ValueError("Configure the database explicitly before migrating")
        return value


def settings(secrets=None):
    load_dotenv(ROOT / ".env", override=False)
    values = dict(secrets or {})
    for key in ("mode", "database_url", "database_url_direct", "sqlite_path"):
        env = "CASHPILOT_" + key.upper()
        if env in os.environ:
            values[key] = os.environ[env]
    return Settings(**values)
