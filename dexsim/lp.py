"""
Helper functions for liquidity provider strategies.

NOTES: not yet fully tested
"""

from typing import Tuple
from dexsim.utils import (
    as_18,
    from_18,
    MIN_TICK,
    MAX_TICK,
    price_to_tick_with_spacing,
    get_spacing_for_fee,
)
from dexsim.pool import Pool


def full_range_liquidity(
    pool: Pool, token0_amount: float, token1_amount: float, agent: str
) -> Tuple[int, int, int, int]:
    """
    Mint liquidity for the given pool across the full range.
    This is a low maintenance approach. It can reduce the possibility of
    impermanent loss, but may only yield modest fees.
    """
    return __mint_liquidity(
        pool, token0_amount, token1_amount, MIN_TICK, MAX_TICK, agent
    )


def tight_band_liquidity(
    pool,
    price_point: float,
    token0_amount: float,
    token1_amount: float,
    agent: str,
    band: float = 0.05,
):
    """
    Mint concentrated liquidity around a given price point.
    Requires active management to avoid impermanent loss if the price
    moves out of range.  If properly managed it can amplify fees.

    Args:
        - band: float, the +- percentage to calculate the range around the price point. Default 5%
    """
    low_price = price_point * (1 - band)
    high_price = price_point * (1 + band)

    spacing = get_spacing_for_fee(pool.fee)
    # print(f"spacing: {spacing}")
    low_tick = price_to_tick_with_spacing(low_price, spacing)
    high_tick = price_to_tick_with_spacing(high_price, spacing)

    # low_tick = price_to_tick_with_spacing(low_price)
    # high_tick = price_to_tick_with_spacing(high_price)

    return __mint_liquidity(
        pool, token0_amount, token1_amount, low_tick, high_tick, agent
    )


def __mint_liquidity(
    pool: Pool,
    token0_amount: float,
    token1_amount: float,
    low_tick: int,
    high_tick: int,
    agent: str,
) -> Tuple[int, int, int, int]:
    """
    Helper to mint liquidity for the given pool
    """
    t0amt = as_18(token0_amount)
    t1amt = as_18(token1_amount)

    bal0 = pool.token_contract.at(pool.token0).balanceOf.call(agent)
    bal1 = pool.token_contract.at(pool.token1).balanceOf.call(agent)

    assert (
        bal0 >= t0amt and bal1 >= t1amt
    ), "Mint position: Insufficient token balance. You need to mint more tokens"

    pool.token_contract.at(pool.token0).approve.transact(
        pool.nftposition.address, t0amt, caller=agent
    )
    pool.token_contract.at(pool.token1).approve.transact(
        pool.nftposition.address, t1amt, caller=agent
    )

    pool.token_contract.at(pool.token0).approve.transact(
        pool.nftposition.address, t0amt, caller=agent
    )
    pool.token_contract.at(pool.token1).approve.transact(
        pool.nftposition.address, t1amt, caller=agent
    )

    # mint the liquidity
    token_id, liq, a0, a1 = pool.nftposition.mint.transact(
        (
            pool.token0,
            pool.token1,
            pool.fee,
            low_tick,
            high_tick,
            t0amt,
            t1amt,
            0,
            0,
            agent,
            int(2e34),
        ),
        caller=agent,
    ).output

    return (from_18(a0), from_18(a1), liq, token_id)
