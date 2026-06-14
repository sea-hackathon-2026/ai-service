"""Unit tests for deterministic sales-agent tools."""

from services.sales_agent.tools import confirm_order, save_order_info


def test_save_order_info_rejects_unknown_field() -> None:
    result = save_order_info("email", "customer@example.com")
    assert result["status"] == "error"


def test_confirm_order_returns_normalized_order() -> None:
    result = confirm_order(
        product="  Cocoon scrub  ",
        quantity="2",
        price="199000",
        address="Ho Chi Minh City",
        phone="0900000000",
    )
    assert result["status"] == "success"
    assert result["order"]["product"] == "Cocoon scrub"
    assert result["order"]["status"] == "confirmed"
