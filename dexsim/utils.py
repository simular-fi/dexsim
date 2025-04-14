"""
Various functions to calculate prices, etc...
"""

import math
from typing import Tuple

Q96 = 2**96
TICK_BASE = 1.0001

MIN_TICK = -887272
MAX_TICK = 887272


# Uniswap v3 fee schedule and spacing
FEE_RANGE = [100, 500, 3000, 10_000]
FEE_TICK_SPACING = [1, 10, 60, 200]


def is_valid_tick(tick: int):
    return tick >= MIN_TICK and tick <= MAX_TICK


def get_spacing_for_fee(fee: int) -> int:
    """
    Return the tick spacing for the given fee
    """
    assert fee in FEE_RANGE, "not a valid fee"
    return FEE_TICK_SPACING[FEE_RANGE.index(fee)]


def get_fee_for_spacing(spacing: int) -> int:
    """
    Return the fee for the given tick spacing
    """
    assert spacing in FEE_TICK_SPACING, "not a valid tick spacing"
    return FEE_RANGE[FEE_TICK_SPACING.index(spacing)]


def as_18(value: float) -> int:
    """
    Convert a price into 18 decimal places
    """
    return int(value * 1e18)


def from_18(value: int) -> float:
    """
    Convert a value from 18 decimal places
    """
    return value / 1e18


def are_sorted_tokens(t0_address, t1_address) -> bool:
    """
    Check of addresses are sorted
    """
    return bytes.fromhex(t0_address[2:]) < bytes.fromhex(t1_address[2:])


def is_tick_in_range(tick: int) -> bool:
    """
    Check a tick is in a valid range
    """
    return tick >= MIN_TICK and tick <= MAX_TICK


def sqrtp_to_price(sqrtpvalue: int) -> int:
    """
    Given sqrtp from slot0 return the price

    The value from slot0 is the exchange rate price of token1:
    "how much token1 does it cost to but 1 token0"
    """
    return (sqrtpvalue / Q96) ** 2


def price_to_sqrtp(token1price: float) -> int:
    """
    Get the sqrt price for the given token price.

    `value` should be the true format - without offsetting for 1e18 (DECIMALS)
    """
    return int(math.sqrt(token1price) * Q96)


def price_to_tick(token1price: float) -> int:
    """
    Get the tick index given the token1 price
    """
    return math.floor(math.log(token1price, TICK_BASE))


def price_to_tick_with_spacing(price, spacing=10):
    """
    Convert a price to a tick and offset for the spacing
    """
    tick = price_to_tick(price)
    return math.floor(tick / spacing) * spacing


def tick_to_price(tick: int) -> float:
    """
    Return the token1 price from the given tick

    Note: tick prices are not as accurate as the square root price
    (this should also mulitply 2**96 to be in sqrtp format...)
    """
    return TICK_BASE**tick


def tick_to_sqrtx96(tick: int) -> float:
    """
    Convert a ticks to sqrtX96 price format
    """
    return int((TICK_BASE ** (tick / 2)) * Q96)


def calculate_liquidity_balance(
    liquidity: int, lower_price: float, upper_price: float, current_price: float
) -> Tuple[float, float]:
    """
    Calculate Uniswap v3 token reserves given liquidity, price range, and current price.
    Often used to calculate a position's reserves.

    NOTE: This is scaled to 1e18 for readability.
    Args:
        liquidity: int, liquidity value
        lower_price: float, lower price bound
        upper_price: float, upper price bound
        current_price: float, current price

    Returns:
        (token0_reserve: float, token1_reserve: float)
    """
    sqrt_Pa = math.sqrt(lower_price)
    sqrt_Pb = math.sqrt(upper_price)
    sqrt_P = math.sqrt(current_price)

    if current_price < lower_price:
        # Only token0 is held
        X = liquidity * (1 / sqrt_Pa - 1 / sqrt_Pb)
        Y = 0
    elif current_price > upper_price:
        # Only token1 is held
        X = 0
        Y = liquidity * (sqrt_Pb - sqrt_Pa)
    else:
        # Both token0 and token1 are present
        X = liquidity * (1 / sqrt_P - 1 / sqrt_Pb)
        Y = liquidity * (sqrt_P - sqrt_Pa)

    return from_18(X), from_18(Y)
