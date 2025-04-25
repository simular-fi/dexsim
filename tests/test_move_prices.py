from dexsim import DEX, sqrtp_to_price, as_18


def test_increase_price_token0(config_filename):
    dex = DEX(config_filename)
    lp = dex.create_wallet()
    bob = dex.create_wallet()

    dex.pools.usdc_dai_100.mint_tokens(100_000, 100_000, lp)
    dex.pools.usdc_dai_100.mint_tokens(5000, 5000, bob)

    _, _, liq, _ = dex.pools.usdc_dai_100.mint_liquidity_position(
        1000, 1000, 0.98, 1.10, lp
    )
    assert liq > 0
    assert (1, 1) == dex.pools.usdc_dai_100.exchange_rates()

    target_price = 1.09
    spent_token1, recv_token0 = dex.pools.usdc_dai_100.increase_price_of_token0(
        target_price, bob
    )
    c, _ = dex.pools.usdc_dai_100.get_sqrtp_tick()
    new_price = sqrtp_to_price(c)
    # profitable
    assert recv_token0 * new_price > spent_token1
    # moved the price
    assert target_price == round(new_price, 2)


def test_decrease_price_token0(config_filename):
    dex = DEX(config_filename)
    lp = dex.create_wallet()
    bob = dex.create_wallet()

    dex.pools.usdc_dai_100.mint_tokens(100_000, 100_000, lp)
    dex.pools.usdc_dai_100.mint_tokens(5000, 5000, bob)

    _, _, liq, _ = dex.pools.usdc_dai_100.mint_liquidity_position(
        1000, 1000, 0.97, 1.10, lp
    )
    assert liq > 0
    assert (1, 1) == dex.pools.usdc_dai_100.exchange_rates()

    target_price = 0.980
    spent_token0, recv_token1 = dex.pools.usdc_dai_100.decrease_price_of_token0(
        target_price, bob
    )

    c, _ = dex.pools.usdc_dai_100.get_sqrtp_tick()
    new_price = sqrtp_to_price(c)

    # profitable
    assert recv_token1 * 1 / new_price > spent_token0
    # moved the price
    assert target_price == round(new_price, 2)
