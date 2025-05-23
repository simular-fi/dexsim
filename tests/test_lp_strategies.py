from dexsim import (
    DEX,
    full_range_liquidity,
    MIN_TICK,
    MAX_TICK,
    tight_band_liquidity,
    price_to_tick_with_spacing,
)


def test_full_range_lp_strategy(config_filename):
    dex = DEX(config_filename)
    bob = dex.create_wallet()
    pool = dex.pools.usdc_dai_100

    pool.mint_tokens(15_000, 15_000, bob)

    a0, a1, _liq, tid = full_range_liquidity(pool, 10_000, 10_000, bob)
    assert 10_000 == a0
    assert 10_000 == a1
    assert 1 == tid

    _fee, low_tick, high_tick, _amt = pool.get_liquidity_position(tid)
    assert MIN_TICK == low_tick
    assert MAX_TICK == high_tick


def test_band_range_lp_strategy(config_filename):
    dex = DEX(config_filename)
    bob = dex.create_wallet()
    pool = dex.pools.usdc_dai_100

    pool.mint_tokens(15_000, 15_000, bob)

    a0, a1, _liq, tid = tight_band_liquidity(pool, 1.0, 100, 100, bob)
    assert a0 == 94.99323925846541
    assert a1 == 100.0

    _fee, low_tick, high_tick, _amt = pool.get_liquidity_position(tid)

    lt = price_to_tick_with_spacing(1.0 * (1 - 0.05), 1)
    ht = price_to_tick_with_spacing(1.0 * (1 + 0.05), 1)
    assert lt == low_tick
    assert ht == high_tick
