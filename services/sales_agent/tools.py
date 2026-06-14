"""Deterministic tools exposed to the sales-closing agent."""

from __future__ import annotations

from typing import Any

from services.sales_agent.domain.order import Order, validate_order_field


def save_order_info(field: str, value: str) -> dict[str, Any]:
    """Validate a piece of order information before it enters conversation state."""

    try:
        normalized = validate_order_field(field, value)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    return {"status": "success", "saved_field": field, "saved_value": normalized}


def get_order_status() -> dict[str, str]:
    """Ask the model to inspect conversation state for missing order fields."""

    return {
        "status": "success",
        "message": "Review the conversation and ask only for missing order fields.",
    }


def confirm_order(
    product: str,
    quantity: str,
    price: str,
    address: str,
    phone: str,
) -> dict[str, Any]:
    """Validate and return a complete order for downstream persistence."""

    try:
        order = Order(
            product=validate_order_field("product", product),
            quantity=validate_order_field("quantity", quantity),
            price=validate_order_field("price", price),
            address=validate_order_field("address", address),
            phone=validate_order_field("phone", phone),
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    return {
        "status": "success",
        "message": "Order confirmed successfully.",
        "order": order.to_dict(),
    }
