# app/pdf_quote.py
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Optional

from app.estimator import EstimateBreakdown


def render_quote_pdf(
    estimate: EstimateBreakdown,
    customer_name: Optional[str] = None,
    project_name: Optional[str] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """
    Very simple, dependency-free "PDF" placeholder for a fence quote.

    This function intentionally avoids external libraries. It generates a
    human-readable text representation of the quote, encoded as bytes. You can
    later swap this out for a real PDF generator like ReportLab or WeasyPrint
    without changing the public interface.
    """
    data = asdict(estimate)

    lines = []
    lines.append("FENCE QUOTE")
    lines.append("=" * 40)
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    if customer_name:
        lines.append(f"Customer: {customer_name}")
    if project_name:
        lines.append(f"Project: {project_name}")
    lines.append("")
    lines.append("LINE ITEMS")
    lines.append("-" * 40)

    for item in data["line_items"]:
        lines.append(
            f"{item['sku']:<12} "
            f"{item['quantity']:>7.2f} {item['unit']:<6} "
            f"@ {item['unit_price']:>8.2f} = {item['extended_price']:>9.2f}"
        )
        if item["description"]:
            lines.append(f"  {item['description']}")

    lines.append("")
    lines.append("TOTALS")
    lines.append("-" * 40)
    lines.append(f"Materials:     {data['materials_subtotal']:>10.2f}")
    lines.append(
        f"Labor:         {data['labor_hours']:>5.2f} h x "
        f"{data['labor_rate']:>7.2f} = {data['labor_total']:>10.2f}"
    )
    lines.append(f"Subtotal:      {data['subtotal']:>10.2f}")
    lines.append(
        f"Margin ({data['margin_pct']:>4.1f}%): {data['margin_amount']:>10.2f}"
    )
    lines.append(f"TOTAL:         {data['total']:>10.2f}")
    lines.append("")
    lines.append("Thank you for your business.")

    content = "\n".join(lines) + "\n"
    pdf_bytes = content.encode("utf-8")

    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes

