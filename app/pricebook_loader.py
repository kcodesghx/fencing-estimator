# app/pricebook_loader.py
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional


@dataclass
class PricebookItem:
    sku: str
    description: str
    unit: str
    unit_price: float
    unit_cost: Optional[float] = None
    category: Optional[str] = None


Pricebook = Dict[str, PricebookItem]


_FIELD_ALIASES: Mapping[str, Iterable[str]] = {
    "sku": ("sku", "item", "item_code"),
    "description": ("description", "desc", "name"),
    "unit": ("unit", "uom"),
    "unit_price": ("unit_price", "price", "sell_price"),
    "unit_cost": ("unit_cost", "cost"),
    "category": ("category", "group"),
}


def _normalise_header(header: str) -> str:
    return header.strip().lower()


def _build_header_map(headers: Iterable[str]) -> Dict[str, str]:
    """
    Map canonical field names (sku, description, ...) to the actual CSV header.

    This allows some flexibility in how the pricebook CSV is named.
    """
    normalised = {_normalise_header(h): h for h in headers}
    mapping: Dict[str, str] = {}
    for field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalised:
                mapping[field] = normalised[alias]
                break
    required = ("sku", "description", "unit", "unit_price")
    missing = [f for f in required if f not in mapping]
    if missing:
        raise ValueError(
            f"Pricebook CSV is missing required columns: {', '.join(missing)}"
        )
    return mapping


def load_pricebook(path: str | Path) -> Pricebook:
    """
    Load a pricebook CSV into a dictionary of PricebookItem keyed by SKU.

    The CSV must include, at minimum, columns for:
      - sku
      - description
      - unit
      - unit_price

    Column names are matched case-insensitively and with a few common aliases
    (for example, 'price' is accepted for 'unit_price').
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Pricebook CSV not found: {path}")

    items: Pricebook = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Pricebook CSV has no header row")

        header_map = _build_header_map(reader.fieldnames)

        for idx, row in enumerate(reader, start=2):  # 1-based + header
            def get(field: str, default: str = "") -> str:
                header = header_map.get(field)
                return (row.get(header, default) or "").strip() if header else default

            sku = get("sku")
            if not sku:
                # Skip completely blank lines
                if not any(value.strip() for value in row.values() if value):
                    continue
                raise ValueError(f"Row {idx}: missing SKU")

            description = get("description")
            unit = get("unit")
            unit_price_raw = get("unit_price")

            if not unit_price_raw:
                raise ValueError(f"Row {idx} (SKU {sku}): missing unit_price/price")

            try:
                unit_price = float(unit_price_raw)
            except ValueError as exc:
                raise ValueError(
                    f"Row {idx} (SKU {sku}): invalid unit_price '{unit_price_raw}'"
                ) from exc

            unit_cost_value: Optional[float] = None
            unit_cost_raw = get("unit_cost")
            if unit_cost_raw:
                try:
                    unit_cost_value = float(unit_cost_raw)
                except ValueError:
                    unit_cost_value = None

            category = get("category") or None

            items[sku] = PricebookItem(
                sku=sku,
                description=description,
                unit=unit,
                unit_price=unit_price,
                unit_cost=unit_cost_value,
                category=category,
            )

    return items


def get_item(pricebook: Pricebook, sku: str) -> PricebookItem:
    """
    Look up an item in the pricebook, raising a clear error if missing.
    """
    try:
        return pricebook[sku]
    except KeyError as exc:
        raise KeyError(f"SKU not found in pricebook: {sku}") from exc

