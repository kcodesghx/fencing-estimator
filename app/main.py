#app/main.py
from __future__ import annotations

import base64
import io
import os
from dataclasses import asdict
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


from app.estimator import (
    EstimateBreakdown,
    LineItemInput, 
    calculate_estimate,
    FenceEstimateInput,      # add this
    build_fence_bom, 
)
from app.pdf_quote import render_quote_pdf
from app.pricebook_loader import Pricebook, load_pricebook


app = FastAPI(title="Fencing Estimator")


class LineItem(BaseModel):
    sku: str
    quantity: float = Field(gt=0)


class EstimateRequest(BaseModel):
    line_items: List[LineItem]
    labor_hours: float = Field(0, ge=0)
    labor_rate: float = Field(0, ge=0)
    margin_pct: float = Field(0, ge=0)
    customer_name: Optional[str] = None
    project_name: Optional[str] = None
    include_pdf: bool = False

class FenceEstimateRequest(BaseModel):
    fence_length_ft: float = Field(..., gt=0)
    style: str = "wood"
    posts_per_ft: float = Field(0.0833, gt=0)  # ~1 post per 12 ft
    gates: int = Field(0, ge=0)
    labor_hours: float = Field(0, ge=0)
    labor_rate: float = Field(0, ge=0)
    margin_pct: float = Field(0, ge=0)
    customer_name: Optional[str] = None
    project_name: Optional[str] = None
    include_pdf: bool = False

class PORequest(BaseModel):
    line_items: List[LineItem]
    customer_name: Optional[str] = None
    project_name: Optional[str] = None


def _load_pricebook_for_app() -> Pricebook:
    """
    Locate and load the pricebook for the API.

    - Use PRICEBOOK_PATH if set.
    - Otherwise try ./pricebook.csv then ./samples/pricebook.csv
    """
    candidates = []
    env_path = os.getenv("PRICEBOOK_PATH")
    if env_path:
        candidates.append(env_path)
    candidates.extend(["pricebook.csv", os.path.join("samples", "pricebook.csv")])

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return load_pricebook(candidate)

    raise RuntimeError(
        "No pricebook CSV found. Set PRICEBOOK_PATH or add pricebook.csv."
    )


@app.on_event("startup")
def startup_event() -> None:
    app.state.pricebook = _load_pricebook_for_app()


def _ensure_pricebook() -> Pricebook:
    pricebook = getattr(app.state, "pricebook", None)
    if not pricebook:
        raise HTTPException(status_code=500, detail="Pricebook is not loaded")
    return pricebook


@app.post("/estimate")
def create_estimate(request: EstimateRequest):
    if not request.line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")

    pricebook = _ensure_pricebook()
    line_inputs: List[LineItemInput] = [
        LineItemInput(sku=item.sku, quantity=item.quantity)
        for item in request.line_items
    ]

    try:
        estimate: EstimateBreakdown = calculate_estimate(
            pricebook=pricebook,
            line_items=line_inputs,
            labor_hours=request.labor_hours,
            labor_rate=request.labor_rate,
            margin_pct=request.margin_pct,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = asdict(estimate)

    if request.include_pdf:
        pdf_bytes = render_quote_pdf(
            estimate,
            customer_name=request.customer_name,
            project_name=request.project_name,
        )
        payload["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")

    return payload


@app.post("/po")
def create_purchase_order(request: PORequest):
    if not request.line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")

    pricebook = _ensure_pricebook()
    line_inputs: List[LineItemInput] = [
        LineItemInput(sku=item.sku, quantity=item.quantity)
        for item in request.line_items
    ]

    try:
        estimate: EstimateBreakdown = calculate_estimate(
            pricebook=pricebook,
            line_items=line_inputs,
            labor_hours=0.0,
            labor_rate=0.0,
            margin_pct=0.0,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pdf_bytes = render_quote_pdf(
        estimate,
        customer_name=request.customer_name,
        project_name=request.project_name,
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="po.pdf"'},
    )


@app.post("/estimate_fence")
def create_fence_estimate(request: FenceEstimateRequest):
    """
    High-level fence estimator.

    You send: fence_length_ft, style, gates, labor, margin.
    The API:
      - builds a fence BOM (posts, rails, pickets, concrete, fasteners, gate)
      - runs the standard calculate_estimate()
      - optionally returns a base64 "PDF" quote.
    """
    pricebook = _ensure_pricebook()

    fence_input = FenceEstimateInput(
        fence_length_ft=request.fence_length_ft,
        style=request.style,
        posts_per_ft=request.posts_per_ft,
        gates=request.gates,
    )

    try:
        line_inputs: List[LineItemInput] = build_fence_bom(pricebook, fence_input)
        estimate: EstimateBreakdown = calculate_estimate(
            pricebook=pricebook,
            line_items=line_inputs,
            labor_hours=request.labor_hours,
            labor_rate=request.labor_rate,
            margin_pct=request.margin_pct,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = asdict(estimate)

    if request.include_pdf:
        pdf_bytes = render_quote_pdf(
            estimate,
            customer_name=request.customer_name,
            project_name=request.project_name,
        )
        payload["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")

    return payload

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

