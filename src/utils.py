import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


def ensure_parent(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: str | Path, data: Any) -> Path:
    path = ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def read_json(path: str | Path) -> Any:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_csv(path: str | Path, rows: Iterable[Mapping[str, Any]], fieldnames: list[str]) -> Path:
    path = ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return path


def read_csv(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def safe_float(value: Any):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def list_files(root: str | Path) -> list[Path]:
    root = Path(root)
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file() and p.name != ".gitkeep"]
