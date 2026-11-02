"""Write a copy of data.yaml whose `path:` is an ABSOLUTE folder, so Ultralytics never
resolves it against the global datasets_dir stored in its settings.json (which may still
point at an old project)."""
from pathlib import Path
import yaml


def resolved_data_yaml(data_yaml) -> str:
    src = Path(data_yaml).resolve()
    cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
    cfg["path"] = str((src.parent / (cfg.get("path") or "dataset")).resolve())
    out = src.parent / ".data_resolved.yaml"
    out.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return str(out)
