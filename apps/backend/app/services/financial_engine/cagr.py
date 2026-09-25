from decimal import Decimal, localcontext


def calculate_cagr(beginning: Decimal, ending: Decimal, years: int) -> Decimal | None:
    if beginning <= 0 or ending < 0 or years <= 0:
        return None
    if ending == 0:
        return Decimal(-1)
    with localcontext() as context:
        context.prec = 38
        return (ending / beginning) ** (Decimal(1) / Decimal(years)) - Decimal(1)
