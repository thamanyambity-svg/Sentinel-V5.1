from bot.journal.audit import audit


class DerivValidationError(Exception):
    pass


ALLOWED_SIDES = {"BUY", "SELL"}


def validate_trade(asset, side, amount=None):
    # asset
    if not isinstance(asset, str) or len(asset.strip()) < 2:
        audit("DERIV_VALIDATION_FAILED", context={
            "field": "asset",
            "value": asset
        })
        raise DerivValidationError("Invalid asset")

    # side
    if not isinstance(side, str) or side.upper() not in ALLOWED_SIDES:
        audit("DERIV_VALIDATION_FAILED", context={
            "field": "side",
            "value": side
        })
        raise DerivValidationError("Invalid side")

    # amount
    if amount is not None:
        if not isinstance(amount, (int, float)) or amount <= 0:
            audit("DERIV_VALIDATION_FAILED", context={
                "field": "amount",
                "value": amount
            })
            raise DerivValidationError("Invalid amount")

    return {
        "asset": asset.strip().upper(),
        "side": side.upper(),
        "amount": amount
    }
