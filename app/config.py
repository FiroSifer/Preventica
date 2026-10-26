from pathlib import Path
import os
from dotenv import dotenv_values
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='SAFESENSE_', env_file=ROOT / '.env', extra='ignore')
    database: str = 'data/safesense.db'
    model_path: str = ''
    ppe_model_path: str = ''
    fire_model_path: str = ''
    admin_name: str = 'admin'
    admin_password: str = 'admin'
    session_hours: int = Field(8, ge=1, le=72)
    confidence: float = Field(.45, ge=.05, le=1)
    image_size: int = Field(640, ge=160, le=2048)
    device: str = 'cpu'
    capture_fps: float = Field(12, ge=1, le=60)
    inference_fps: float = Field(3, ge=.2, le=30)
    min_observations: int = Field(3, ge=1, le=100)
    cooldown_seconds: float = Field(30, ge=0)
    class_map: dict[str, str] = {}

    def source_variable(self, name):
        # Pydantic reads declared settings from .env; camera references also need
        # access to non-SAFESENSE names without exposing or copying their values.
        return os.environ.get(name, dotenv_values(ROOT / '.env').get(name, '')) or ''

    def path(self, value):
        p = Path(value)
        return p if p.is_absolute() else ROOT / p
