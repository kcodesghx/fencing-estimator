# app/estimator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.pricebook_loader import Pricebook, PricebookItem, get_item
from math import ceil 


@dataclass
class FenceEstimateInput:
    """
    High-level inputs for a fence job.

    These are the simple fields you or n8n/JobNimbus will send.
    """
    fence_length_ft: float
    style: str = "wood"
    posts_per_ft: float = 0.0833  # ~1 post per 12 ft
    gates: int = 0


def build_fence_bom(pricebook: Pricebook, fence: FenceEstimateInput) -> List[LineItemInput]:
    """
    Build a Bill of Materials (BOM) for a fence based on length, style, etc.

    For now, this:
      - finds one item in each category (post, rail, picket, concrete, fastener, gate)
      - calculates quantities using simple demo formulas
    """

    # --- helper: pick first item by category ---
    def pick_by_category(category: str) -> PricebookItem:
        for item in pricebook.values():
            if item.category == category:
                return item
        raise KeyError(f"No pricebook item with category='{category}'")

    # simple formulas – good enough for a demo, can refine later
    posts_qty = max(2, ceil(fence.fence_length_ft * fence.posts_per_ft))
    rails_per_section = 2
    rails_qty = max(0, (posts_qty - 1) * rails_per_section)

    # Demo assumption: 2 pickets per foot for wood
    pickets_per_ft = 2.0 if fence.style == "wood" else 2.0
    pickets_qty = ceil(fence.fence_length_ft * pickets_per_ft)

    # Concrete: 0.75 bag per post
    bags_per_post = 0.75
    concrete_qty = ceil(posts_qty * bags_per_post)

    # Fasteners: 1 box per 200 pickets
    fasteners_boxes = max(1, ceil(pickets_qty / 200))

    gate_qty = max(0, fence.gates)

    # Look up one SKU per category
    post_item = pick_by_category("post")
    rail_item = pick_by_category("rail")
    picket_item = pick_by_category("picket")
    concrete_item = pick_by_category("concrete")
    fastener_item = pick_by_category("fastener")

    gate_item = None
    if gate_qty > 0:
        try:
            gate_item = pick_by_category("gate")
        except KeyError:
            gate_item = None  # optional

    bom: List[LineItemInput] = [
        LineItemInput(sku=post_item.sku, quantity=posts_qty),
        LineItemInput(sku=rail_item.sku, quantity=rails_qty),
        LineItemInput(sku=picket_item.sku, quantity=pickets_qty),
        LineItemInput(sku=concrete_item.sku, quantity=concrete_qty),
        LineItemInput(sku=fastener_item.sku, quantity=fasteners_boxes),
    ]

    if gate_item and gate_qty > 0:
        bom.append(LineItemInput(sku=gate_item.sku, quantity=gate_qty))

    return bom


@dataclass
class LineItemInput:
    sku: str
    quantity: float


@dataclass
class LineItemEstimate:
    sku: str
    description: str
    quantity: float
    unit: str
    unit_price: float
    extended_price: float


@dataclass
class EstimateBreakdown:
    materials_subtotal: float
    labor_hours: float
    labor_rate: float
    labor_total: float
    subtotal: float
    margin_pct: float
    margin_amount: float
    total: float
    line_items: List[LineItemEstimate]


def _round_money(value: float) -> float:
    return round(value, 2)


def calculate_estimate(
    pricebook: Pricebook,
    line_items: List[LineItemInput],
    labor_hours: float = 0.0,
    labor_rate: float = 0.0,
    margin_pct: float = 0.0,
) -> EstimateBreakdown:
    """
    Core math for a fence estimate.

    - Looks up each SKU in the pricebook.
    - Multiplies quantity * unit_price for material totals.
    - Adds labor (labor_hours * labor_rate).
    - Applies margin_pct as a markup on subtotal (materials + labor).
    """
    if labor_hours < 0 or labor_rate < 0 or margin_pct < 0:
        raise ValueError("labor_hours, labor_rate, and margin_pct must be non-negative")

    estimated_lines: List[LineItemEstimate] = []
    materials_subtotal = 0.0

    for item in line_items:
        if item.quantity <= 0:
            raise ValueError(f"Quantity must be positive for SKU {item.sku}")

        pb_item: PricebookItem = get_item(pricebook, item.sku)
        extended_price = item.quantity * pb_item.unit_price
        materials_subtotal += extended_price

        estimated_lines.append(
            LineItemEstimate(
                sku=pb_item.sku,
                description=pb_item.description,
                quantity=item.quantity,
                unit=pb_item.unit,
                unit_price=pb_item.unit_price,
                extended_price=_round_money(extended_price),
            )
        )

    labor_total = labor_hours * labor_rate
    subtotal = materials_subtotal + labor_total

    margin_amount = subtotal * (margin_pct / 100.0)
    total = subtotal + margin_amount

    return EstimateBreakdown(
        materials_subtotal=_round_money(materials_subtotal),
        labor_hours=_round_money(labor_hours),
        labor_rate=_round_money(labor_rate),
        labor_total=_round_money(labor_total),
        subtotal=_round_money(subtotal),
        margin_pct=_round_money(margin_pct),
        margin_amount=_round_money(margin_amount),
        total=_round_money(total),
        line_items=estimated_lines,
    )

