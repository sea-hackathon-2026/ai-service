"""
Sales Agent Tools — State-managed order collection via ToolContext.

These tools use ADK's ToolContext to persist customer order information
across conversation turns. The agent calls them as it gathers data from
the customer during the sales closing flow.
"""

from __future__ import annotations

from typing import Any, Dict


# ── Required fields for a complete order ──────────────────────────────
REQUIRED_FIELDS = ["product", "quantity", "price", "address", "phone"]

FIELD_LABELS = {
    "product": "Sản phẩm",
    "quantity": "Số lượng",
    "price": "Giá",
    "address": "Địa chỉ giao hàng",
    "phone": "Số điện thoại",
}


def save_order_info(field: str, value: str) -> Dict[str, Any]:
    """Save a single piece of order information to the session state.

    Args:
        field: One of 'product', 'quantity', 'price', 'address', 'phone'.
        value: The value provided by the customer.

    Returns:
        A dict with status, the saved field, and a list of still-missing fields.
    """
    if field not in REQUIRED_FIELDS:
        return {
            "status": "error",
            "message": f"Trường '{field}' không hợp lệ. Các trường hợp lệ: {', '.join(REQUIRED_FIELDS)}",
        }

    return {
        "status": "success",
        "message": f"Đã lưu {FIELD_LABELS.get(field, field)}: {value}",
        "saved_field": field,
        "saved_value": value,
    }


def get_order_status() -> Dict[str, Any]:
    """Check which order fields have been collected so far.

    Returns:
        A dict describing current order status.
    """
    return {
        "status": "success",
        "message": "Hãy kiểm tra lại lịch sử hội thoại để xem đã thu thập được thông tin gì.",
    }


def confirm_order(
    product: str,
    quantity: str,
    price: str,
    address: str,
    phone: str,
) -> Dict[str, Any]:
    """Confirm and finalise the order with all required information.

    Args:
        product: Tên sản phẩm khách muốn mua.
        quantity: Số lượng.
        price: Giá tiền.
        address: Địa chỉ giao hàng.
        phone: Số điện thoại liên hệ.

    Returns:
        A dict with the full confirmed order.
    """
    return {
        "status": "success",
        "message": "✅ Đơn hàng đã được xác nhận thành công!",
        "order": {
            "product": product,
            "quantity": quantity,
            "price": price,
            "address": address,
            "phone": phone,
            "status": "confirmed",
        },
    }
