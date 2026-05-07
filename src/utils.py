import csv
import json
import os
import unicodedata
from pathlib import Path
from typing import Iterable, Mapping, Any


def ensure_parent(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: str | Path, data: Any) -> Path:
    path = ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def write_text(path: str | Path, text: str) -> Path:
    path = ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        f.write(text)
    return path


def write_csv(path: str | Path, rows: Iterable[Mapping[str, Any]], fieldnames: list[str]) -> Path:
    path = ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return path


def normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.strip().lower()
    for ch in [" ", "-", ".", "/", "\\", "(", ")", "[", "]"]:
        normalized = normalized.replace(ch, "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def list_files(root: str | Path) -> list[Path]:
    root = Path(root)
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file() and p.name != ".gitkeep"]


def safe_float(value: Any):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if text in {"", "null", "None", "NaN"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None
