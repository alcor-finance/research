from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, payload: str) -> None:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True))


def atomic_write_yaml(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, yaml.safe_dump(payload, sort_keys=False))


def atomic_write_parquet(path: Path, df: pd.DataFrame) -> None:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, suffix=".parquet") as tmp:
        tmp_path = Path(tmp.name)
    df.to_parquet(tmp_path, index=False)
    os.replace(tmp_path, path)
