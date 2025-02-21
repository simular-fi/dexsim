import pytest

from dexsim.abis import (
    uniswap_factory_contract,
    uniswap_nftpositionmanager,
    uniswap_router_contract,
)
from dexsim.utils import (
    price_to_sqrtp,
    tick_to_price,
    calculate_liquidity_balance,
)
from dexsim.pool import Pool, Token, get_fee_for_spacing, get_spacing_for_fee

from simular import create_many_accounts, create_account


def test_sorts_addresses(snapshot_evm, deployer):
    fee = 500
    router = uniswap_router_contract(snapshot_evm)
    nft = uniswap_nftpositionmanager(snapshot_evm)
    ta = Token("USDC", 3300)
    tb = Token("WETH", 1)

    # check it throws exception on wrong order of tokens
    with pytest.raises(Exception):
        Pool(snapshot_evm, tb, ta, fee, router, nft, deployer)

    pool = Pool(snapshot_evm, ta, tb, fee, router, nft, deployer)
    assert "USDC" == pool.token0.symbol.call()
    assert "WETH" == pool.token1.symbol.call()
    assert "USDC_WETH_500" == pool.name


def test_pool_create(snapshot_evm, deployer):
    fee = 500
    router = uniswap_router_contract(snapshot_evm)
    nft = uniswap_nftpositionmanager(snapshot_evm)
    ta = Token("USDC", 3300)
    tb = Token("WETH", 1)

    pool = Pool(snapshot_evm, ta, tb, fee, router, nft, deployer)
    assert fee == pool.fee

    sqrtp, tick = pool.get_sqrtp_tick()
    assert sqrtp == price_to_sqrtp(1 / 3300)
    assert tick == -81021
    t0price, t1price = pool.exchange_prices()
    assert 3300.0 == t0price
    assert 0.00030303030303030303 == t1price

    factory = uniswap_factory_contract(snapshot_evm)
    p_address = factory.getPool.call(pool.token0.address, pool.token1.address, fee)
    assert p_address == pool.pool_contract.address


def test_multiple_pools(snapshot_evm, deployer):
    fee = 500
    router = uniswap_router_contract(snapshot_evm)
    nft = uniswap_nftpositionmanager(snapshot_evm)

    dia = Token("DIA", 1)
    usdc1 = Token("USDC", 1)

    usdc2 = Token("USDC", 3300)
    weth = Token("WETH", 1)

    usdc3 = Token("USDC", 50_000)
    wbtc = Token("WBTC", 1)

    dia_usdc_pool = Pool(snapshot_evm, dia, usdc1, fee, router, nft, deployer)
    usdc_weth_pool = Pool(snapshot_evm, usdc2, weth, fee, router, nft, deployer)
    usdc_wbtc_pool = Pool(snapshot_evm, usdc3, wbtc, fee, router, nft, deployer)

    # check initial pricing
    dia_usdc_sqrtp, _ = dia_usdc_pool.get_sqrtp_tick()
    assert dia_usdc_sqrtp == price_to_sqrtp(1)
    dia_usdc_0_price, dia_usdc_pool_1_price = dia_usdc_pool.exchange_prices()
    assert 1 == dia_usdc_0_price
    assert 1 == dia_usdc_pool_1_price

    usdc_weth_sqrtp, _ = usdc_weth_pool.get_sqrtp_tick()
    assert usdc_weth_sqrtp == price_to_sqrtp(1 / 3300)
    usdc_weth_0_price, usdc_weth_pool_1_price = usdc_weth_pool.exchange_prices()
    assert 3300.0 == usdc_weth_0_price
    assert 0.00030303030303030303 == usdc_weth_pool_1_price

    usdc_wbtc_sqrtp, _ = usdc_wbtc_pool.get_sqrtp_tick()
    assert usdc_wbtc_sqrtp == price_to_sqrtp(1 / 50_000)
    usdc_wbtc_0_price, usdc_wbtc_pool_1_price = usdc_wbtc_pool.exchange_prices()
    assert 49999.99999999999 == usdc_wbtc_0_price
    assert 2e-05 == usdc_wbtc_pool_1_price


def test_pool_mint_tokens(snapshot_evm, deployer):
    fee = 500
    router = uniswap_router_contract(snapshot_evm)
    nft = uniswap_nftpositionmanager(snapshot_evm)
    ta = Token("USDC", 3300)
    tb = Token("WETH", 1)

    pool = Pool(snapshot_evm, ta, tb, fee, router, nft, deployer)

    bob, alice = create_many_accounts(snapshot_evm, 2)
    pool.mint_tokens(9900, 3, bob)
    pool.mint_tokens(6000, 2, alice)

    b1, b2 = pool.token_pair_balance(bob)
    assert b1 >= 9900.0
    assert b2 >= 3

    a1, a2 = pool.token_pair_balance(bob)
    assert a1 >= 6000.0
    assert a2 >= 2


def test_pool_burn_tokens(snapshot_evm, deployer):
    fee = 500
    router = uniswap_router_contract(snapshot_evm)
    nft = uniswap_nftpositionmanager(snapshot_evm)
    ta = Token("DIA", 1)
    tb = Token("USDC", 1)

    pool = Pool(snapshot_evm, ta, tb, fee, router, nft, deployer)
    bob = create_account(snapshot_evm)

    # doesn't fail even though we know bob doesn't have any yet.
    pool.burn_tokens(1000, 0, bob)

    pool.mint_tokens(10, 10, bob)
    assert (10, 10) == pool.token_pair_balance(bob)

    pool.burn_tokens(5, 0, bob)
    assert (5, 10) == pool.token_pair_balance(bob)

    pool.burn_tokens(0, 5, bob)
    assert (5, 5) == pool.token_pair_balance(bob)

    pool.burn_tokens(5, 5, bob)
    assert (0, 0) == pool.token_pair_balance(bob)


def test_pool_liquidity(snapshot_evm, deployer):
    fee = 500
    # required contracts
    router = uniswap_router_contract(snapshot_evm)
    nft = uniswap_nftpositionmanager(snapshot_evm)

    ta = Token("USDC", 3300)
    tb = Token("WETH", 1)
    pool = Pool(snapshot_evm, ta, tb, fee, router, nft, deployer)
    assert "USDC" == pool.token0.symbol.call()
    assert "WETH" == pool.token1.symbol.call()

    pool.mint_tokens(9900, 3, deployer)

    assert (0, 0) == pool.reserves()

    a0, a1, _ = pool.mint_liquidity_position(3300, 1, 3200, 3400, deployer)
    r0, r1 = pool.reserves()

    assert a0 == 3300000000000000000000
    assert a1 == 994534642988408561
    assert r0 == 3300.0
    assert r1 == 0.9945346429884085


def test_stablecoin_liquidity(snapshot_evm, deployer):
    fee = 500
    router = uniswap_router_contract(snapshot_evm)
    nft = uniswap_nftpositionmanager(snapshot_evm)
    dia = Token("DIA", 1)
    usdc = Token("USDC", 1)

    dia_usdc_pool = Pool(snapshot_evm, dia, usdc, fee, router, nft, deployer)

    dia_usdc_pool.mint_tokens(100, 100, deployer)

    a0, a1, _ = dia_usdc_pool.mint_liquidity_position(1, 1, 0.97, 1.02, deployer)
    assert a0 == 1000000000000000000
    assert a1 == 668331854320855885
    r0, r1 = dia_usdc_pool.reserves()
    assert r0 == 1.0
    assert r1 == 0.668331854320856


def test_pool_swap_0_for_1(snapshot_evm, deployer):
    fee = 500
    router = uniswap_router_contract(snapshot_evm)
    nft = uniswap_nftpositionmanager(snapshot_evm)

    dia = Token("DIA", 1)
    usdc = Token("USDC", 1)
    pool = Pool(snapshot_evm, dia, usdc, fee, router, nft, deployer)

    bob, lp = create_many_accounts(snapshot_evm, 2)
    pool.mint_tokens(100, 0, bob)
    pool.mint_tokens(1000, 1000, lp)

    # concentrated
    a0, a1, _ = pool.mint_liquidity_position(900, 900, 0.98, 1.02, lp)
    assert a0 == 900000000000000000000
    assert a1 == 900000000000000000000

    bob_initial_balance = pool.token_pair_balance(bob)
    assert (100, 0) == bob_initial_balance

    # bob swaps from dia for usdc
    inamount, recv = pool.swap_0_for_1(5, bob)
    assert recv == 4997223911806880660
    assert inamount == 5e18

    bob_new_balance = pool.token_pair_balance(bob)
    assert (95.0, 4.997223911806881) == bob_new_balance

    r0, r1 = pool.reserves()
    assert r0 == 905.0
    assert round(r1) == 895.0


def test_pool_swap_1_for_0(snapshot_evm, deployer):
    fee = 500
    router = uniswap_router_contract(snapshot_evm)
    nft = uniswap_nftpositionmanager(snapshot_evm)

    dia = Token("DIA", 1)
    usdc = Token("USDC", 1)

    pool = Pool(snapshot_evm, dia, usdc, fee, router, nft, deployer)

    bob, lp = create_many_accounts(snapshot_evm, 2)
    pool.mint_tokens(0, 100, bob)
    pool.mint_tokens(1000, 1000, lp)

    # concentrated
    a0, a1, _ = pool.mint_liquidity_position(900, 900, 0.98, 1.02, lp)
    assert a0 == 900000000000000000000
    assert a1 == 900000000000000000000

    bob_initial_balance = pool.token_pair_balance(bob)
    assert (0, 100) == bob_initial_balance

    # bob swaps from usdc for dia
    inamount, recv = pool.swap_1_for_0(5, bob)
    assert recv == 4997223911806880660
    assert inamount == 5e18

    bob_new_balance = pool.token_pair_balance(bob)
    assert (4.997223911806881, 95.0) == bob_new_balance

    r0, r1 = pool.reserves()
    assert round(r0) == 895.0
    assert r1 == 905.0


def test_fee_and_spacing():
    with pytest.raises(Exception):
        get_spacing_for_fee(333)

    assert 200 == get_spacing_for_fee(10_000)
    assert 10 == get_spacing_for_fee(500)

    with pytest.raises(Exception):
        get_fee_for_spacing(15)

    assert 10_000 == get_fee_for_spacing(200)
    assert 500 == get_fee_for_spacing(10)


def test_liq_position(snapshot_evm, deployer):
    fee = 500
    router = uniswap_router_contract(snapshot_evm)
    nft = uniswap_nftpositionmanager(snapshot_evm)

    dia = Token("DIA", 1)
    usdc = Token("USDC", 1)

    pool = Pool(snapshot_evm, dia, usdc, fee, router, nft, deployer)

    lp = create_account(snapshot_evm)
    pool.mint_tokens(1000, 1000, lp)

    _, _, token_id = pool.mint_liquidity_position(0.5, 0.5, 0.98, 1.02, lp)
    assert 1 == token_id

    f, tl, tu, liq = pool.get_liquidity_position(token_id)
    assert f == fee
    assert tl == -200
    assert tu == 200
    assert liq == 50252916603475800015

    lower_price = tick_to_price(tl)
    upper_price = tick_to_price(tu)
    _, p1 = pool.exchange_prices()

    a0, a1 = calculate_liquidity_balance(liq, lower_price, upper_price, p1)

    assert round(a0, 1) == 0.5
    assert round(a1, 1) == 0.5
