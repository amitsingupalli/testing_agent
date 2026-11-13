"""Price helpers for the demo — intentionally without tests."""


def apply_discount(price: float, percent: float) -> float:
    """Reduce price by `percent` (0-100), rounded to 2 decimals."""
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return round(price * (1 - percent / 100), 2)


def total_with_tax(prices: list[float], tax_rate: float = 0.0) -> float:
    """Sum prices and add tax on the subtotal, rounded to 2 decimals."""
    if tax_rate < 0:
        raise ValueError("tax_rate must be non-negative")
    subtotal = sum(prices)
    return round(subtotal * (1 + tax_rate), 2)
