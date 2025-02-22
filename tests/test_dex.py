from dexsim.dex import DEX


def test_dex_setup(config_filename):
    dex = DEX(config_filename)
    assert 2 == dex.total_number_of_pools()

    assert (1446501726624926448360620032, -80068) == dex.pools.eth_usdc.get_sqrtp_tick()
    assert (3000.0, 0.0003333333333333333) == dex.pools.eth_usdc.exchange_prices()

    # config stuff
    assert 0.3 == dex.config.pools.eth_usdc.fee
    assert 0.01 == dex.config.pools.dia_usdc.fee
    assert 500 == dex.config.model.steps
    assert [500, 100] == dex.config.agents.lp.liquidity_range


def test_liquidity(config_filename):
    dex = DEX(config_filename)
    bob = dex.create_wallet()

    # get the eth/usdc pool
    eth_usdc_pool = dex.pools.eth_usdc
    eth_usdc_pool.mint_tokens(9000, 3, bob)

    # now directly interact with it.
    assert (0, 0) == eth_usdc_pool.reserves()
    _, _, tokenid = eth_usdc_pool.mint_liquidity_position(3000, 1, 2900, 3100, bob)

    r0, r1 = eth_usdc_pool.reserves()
    _, _, _, liqA = eth_usdc_pool.get_liquidity_position(tokenid)
    assert r0 == 2958.433408298888
    assert r1 == 1.0

    eth_usdc_pool.remove_liquidity(tokenid, 0.5, bob)

    r0a, r1a = eth_usdc_pool.reserves()
    _, _, _, liqB = eth_usdc_pool.get_liquidity_position(tokenid)
    assert r0a == r0 * 0.5
    assert r1a == r1 * 0.5
    assert liqB < liqA
