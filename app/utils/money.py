from __future__ import annotations


def format_stars(amount: int) -> str:
    return f"{amount} ⭐"


def format_signed_stars(amount: int) -> str:
    if amount > 0:
        return f"+{amount} ⭐"
    return f"{amount} ⭐"


def format_usd(amount: int) -> str:
    return f"${amount}"


def format_quote(amount: int, currency: str) -> str:
    code = currency.strip().upper()
    if code in {"RUB", "RUR"}:
        return f"{amount} ₽"
    if code in {"STARS", "XTR", "STAR"}:
        return f"{amount} ⭐"
    if code == "USDT":
        return f"{amount} USDT"
    if code == "USD":
        return f"{amount} USD"
    if code == "CRYPTO":
        return f"{amount} USDT"
    return f"{amount} {code}"


def available_balance(balance: int, reserved_balance: int) -> int:
    return balance - reserved_balance
