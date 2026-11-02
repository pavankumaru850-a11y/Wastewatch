"""config.py -- one place for tunable settings.

Order of precedence: value saved by an admin in the DB (system_settings)
> config/settings_defaults.json > nothing. Scoring rules live in
config/severity_config.json. Secrets stay in .env, never here.
"""
import json
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@lru_cache(maxsize=1)
def _defaults() -> dict:
    return json.loads((CONFIG_DIR / "settings_defaults.json").read_text(encoding="utf-8"))


def scoring_config() -> dict:
    # Re-read each call so an admin edit to the JSON takes effect without restart.
    return json.loads((CONFIG_DIR / "severity_config.json").read_text(encoding="utf-8"))


def save_scoring_config(data: dict) -> None:
    (CONFIG_DIR / "severity_config.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_settings(db=None) -> dict:
    """Defaults overlaid with admin overrides stored in the DB."""
    merged = dict(_defaults())
    if db is not None:
        from .models import SystemSetting
        for row in db.query(SystemSetting).all():
            try:
                merged[row.key] = json.loads(row.value)
            except (TypeError, ValueError):
                pass
    return merged


def default_keys() -> set[str]:
    return set(_defaults().keys())
