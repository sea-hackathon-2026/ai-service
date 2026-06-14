"""Pure order validation policies used by agent tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass

REQUIRED_ORDER_FIELDS = ("product", "quantity", "price", "address", "phone")


@dataclass(frozen=True, slots=True)
class Order:
    """A complete order collected by the conversational agent."""

    product: str
    quantity: str
    price: str
    address: str
    phone: str

    def to_dict(self) -> dict[str, str]:
        return {**asdict(self), "status": "confirmed"}


def validate_order_field(field: str, value: str) -> str:
    """Validate one tool argument and return a normalized value."""

    if field not in REQUIRED_ORDER_FIELDS:
        raise ValueError(f"Unsupported order field: {field}")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"Order field '{field}' cannot be empty")
    return normalized
