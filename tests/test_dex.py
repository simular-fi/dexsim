from dexsim import DEX


def test_dex_setup(config_filename):
    dex = DEX(config_filename)
    assert 3 == dex.total_number_of_pools()
    assert (
        1120455419495722814493687808,
        -85177,
    ) == dex.pools.usdc_weth_500.get_sqrtp_tick()
    assert (79228162514264337593543950336, 0) == dex.pools.usdc_dai_100.get_sqrtp_tick()
    assert (
        19807040628566084398385987584,
        -27728,
    ) == dex.pools.weth_wbtc_500.get_sqrtp_tick()

    assert (5000, 0.0002) == dex.pools.usdc_weth_500.exchange_rates()
    assert (1, 1) == dex.pools.usdc_dai_100.exchange_rates()
    assert (16, 0.0625) == dex.pools.weth_wbtc_500.exchange_rates()

    pool_names = dex.list_pools()
    assert "usdc_weth_500" in pool_names
    assert "usdc_dai_100" in pool_names
    assert "weth_wbtc_500" in pool_names

    assert 0 == dex.pools.usdc_weth_500.liquidity()
    assert 0 == dex.pools.usdc_dai_100.liquidity()


def test_mint_tokens(config_filename):
    dex = DEX(config_filename)
    bob = dex.create_wallet()

    dex.pools.usdc_weth_500.mint_tokens(5000, 1, bob)
    dex.pools.usdc_dai_100.mint_tokens(10_000, 10_000, bob)

    assert (15_000, 1) == dex.pools.usdc_weth_500.token_pair_balance(bob)
    assert (15_000, 10_000) == dex.pools.usdc_dai_100.token_pair_balance(bob)

    # burn some usdc
    dex.pools.usdc_weth_500.burn_tokens(1000, 0, bob)

    assert (14_000, 1) == dex.pools.usdc_weth_500.token_pair_balance(bob)
    assert (14_000, 10_000) == dex.pools.usdc_dai_100.token_pair_balance(bob)

    # burn all usdc and dai
    dex.pools.usdc_dai_100.burn_tokens(14_000, 10_000, bob)
    assert (0, 1) == dex.pools.usdc_weth_500.token_pair_balance(bob)
    assert (0, 0) == dex.pools.usdc_dai_100.token_pair_balance(bob)

    # pool reserves
    assert (0, 0) == dex.pools.usdc_weth_500.reserves()
    assert (0, 0) == dex.pools.usdc_dai_100.reserves()


def test_usdc_weth_liquidity(config_filename):
    dex = DEX(config_filename)
    bob = dex.create_wallet()
    dex.pools.usdc_weth_500.mint_tokens(15_000, 3, bob)

    # We specify the price ranges in terms of Y
    a0, a1, _, tid = dex.pools.usdc_weth_500.mint_liquidity_position(
        10000, 2, 1 / 4900, 1 / 5100, bob
    )
    assert 9628 == round(a0)
    assert 2 == a1
    assert tid == 1
    assert (
        500,
        -85380,
        -84980,
        13949318807175567298654,
    ) == dex.pools.usdc_weth_500.get_liquidity_position(tid)

    assert (
        9667.92025496101,
        1.9920153358026262,
    ) == dex.pools.usdc_weth_500.get_amounts_by_liquidity_position(tid)


def test_weth_wbtc_liquidity(config_filename):
    dex = DEX(config_filename)
    bob = dex.create_wallet()
    dex.pools.weth_wbtc_500.mint_tokens(32, 2, bob)

    # We specify the price ranges in terms of Y
    a0, a1, _, tid = dex.pools.weth_wbtc_500.mint_liquidity_position(
        16, 1, 1 / 15.8, 1 / 16.1, bob
    )
    assert 16 == round(a0)
    assert 0.535602997473512 == a1
    assert tid == 1
    assert (
        500,
        -27790,
        -27610,
        684202146845331317010,
    ) == dex.pools.weth_wbtc_500.get_liquidity_position(tid)

    assert (
        16.099412275209396,
        0.5293899559561913,
    ) == dex.pools.weth_wbtc_500.get_amounts_by_liquidity_position(tid)


def test_increase_decrease_liquidity(config_filename):
    dex = DEX(config_filename)
    bob = dex.create_wallet()
    dex.pools.usdc_weth_500.mint_tokens(15_000, 3, bob)

    _, _, liqa, tid = dex.pools.usdc_weth_500.mint_liquidity_position(
        10000, 2, 1 / 4900, 1 / 5100, bob
    )

    liq0 = dex.pools.usdc_weth_500.liquidity()
    assert liq0 == liqa

    assert (
        6974659403587783649327,
        4813.997659003724,
        1.0,
    ) == dex.pools.usdc_weth_500.increase_liquidity(tid, 5000, 1, bob)
    liq1 = dex.pools.usdc_weth_500.liquidity()
    assert liq1 > liq0

    assert (7220.996488505585, 1.5) == dex.pools.usdc_weth_500.remove_liquidity(
        tid, 0.5, bob
    )
    liq2 = dex.pools.usdc_weth_500.liquidity()
    assert liq2 < liq1


def test_swaps(config_filename):
    dex = DEX(config_filename)
    lp = dex.create_wallet()
    bob = dex.create_wallet()
    pool = dex.pools.usdc_dai_100
    pool.mint_tokens(10_000, 10_000, lp)
    pool.mint_tokens(1000, 0, bob)

    _, _, liq, _ = pool.mint_liquidity_position(1000, 1000, 0.98, 1.10, lp)
    assert liq > 0

    # bob swaps usdc for dai: 0 => 1
    i0, o0 = pool.swap_0_for_1(100, bob)
    assert i0 == 100
    assert o0 == 99.52694458830966

    t0bal, t1bal = pool.token_pair_balance(bob)
    assert t0bal == 900
    assert t1bal == o0

    # bob swaps dai for usdc: 1 => 0
    i1, o1 = pool.swap_1_for_0(10, bob)
    assert i1 == 10
    assert o1 == 10.08754327384422


def test_track_liquidity(config_filename):
    dex = DEX(config_filename)
    bob = dex.create_wallet()
    dex.pools.usdc_weth_500.mint_tokens(100_000, 20, bob)

    # 3 positions
    _, _, _, id1 = dex.pools.usdc_weth_500.mint_liquidity_position(
        10000, 2, 1 / 4900, 1 / 5100, bob
    )
    assert (
        9667.92025496101,
        1.9920153358026262,
    ) == dex.pools.usdc_weth_500.get_amounts_by_liquidity_position(id1)

    _, _, _, id2 = dex.pools.usdc_weth_500.mint_liquidity_position(
        10000, 2, 1 / 5000, 1 / 5200, bob
    )
    assert (
        0.0,
        2.000000000000721,
    ) == dex.pools.usdc_weth_500.get_amounts_by_liquidity_position(id2)

    _, _, _, id3 = dex.pools.usdc_weth_500.mint_liquidity_position(
        10000, 2, 1 / 5100, 1 / 5300, bob
    )
    assert (
        0.0,
        2.000000000000719,
    ) == dex.pools.usdc_weth_500.get_amounts_by_liquidity_position(id3)
