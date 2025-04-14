"""
Calculate liquidy in tick ranges.  Work towards target price
"""

from dexsim.dex import DEX
from dexsim.utils import (
    tick_to_price,
    price_to_tick,
    price_to_sqrtp,
    Q96,
    price_to_tick_with_spacing,
    tick_to_sqrtx96,
)


def show_liquidity(dex: DEX):
    pass


def test1():
    dex = DEX("./liqconfig.yaml")
    bob = dex.create_wallet()
    dex.pools.eth_usdc.mint_tokens(1_000_000, 1_000_000, bob)

    sqrtp, ct = dex.pools.eth_usdc.get_sqrtp_tick()

    _, _, tokenid = dex.pools.eth_usdc.mint_liquidity_position(1, 5000, 4900, 5100, bob)
    # _, _, tokenid = dex.pools.eth_usdc.mint_liquidity_position(
    #    10000, 10000, 4900, 5100, bob
    # )
    # _, _, tokenid = dex.pools.eth_usdc.mint_liquidity_position(
    #    10000, 10000, 5100, 5300, bob
    # )

    # _, _, _, liqA = dex.pools.eth_usdc.get_liquidity_position(tokenid)
    # print(liqA)
    e, u = dex.pools.eth_usdc.exchange_prices()
    print(f"SQRTP: {sqrtp}")
    print(f"current tick: {ct}")
    print(f"prices: ETH: {e} {u}")
    print(f"active liq:  {dex.pools.eth_usdc.liquidity()}")

    ## TODO: I can't seem to figure out how to get liquidity amounts
    ## out of the thing!  Use liquidity() ???
    # _, got = dex.pools.eth_usdc.swap_1_for_0(1, bob)
    # print(f"got {got}")
    # _, ct1 = dex.pools.eth_usdc.get_sqrtp_tick()
    # print(ct1)

    a, v = dex.pools.eth_usdc.get_amount_to_target(85370)
    print(a)

    """
    for t in range(84980, 85370, 10):
        amt, inited = dex.pools.eth_usdc.get_amount_to_target(t)
        if inited:
            print("found one")
        if amt > 0:
            print(amt)
    """


### Experiments ###
def liquidity0(amount, pa, pb):
    if pa > pb:
        pa, pb = pb, pa
    return (amount * (pa * pb) / Q96) / (pb - pa)


def liquidity1(amount, pa, pb):
    if pa > pb:
        pa, pb = pb, pa
    return amount * Q96 / (pb - pa)


def calc_amount0(liq, pa, pb):
    if pa > pb:
        pa, pb = pb, pa
    return int(liq * Q96 * (pb - pa) / pa / pb)


def calc_amount1(liq, pa, pb):
    if pa > pb:
        pa, pb = pb, pa
    return int(liq * (pb - pa) / Q96)


def run_basic():
    sqrtp_low = price_to_sqrtp(4900)
    sqrtp_cur = price_to_sqrtp(5000)
    sqrtp_upp = price_to_sqrtp(5100)

    # eth = 10**18
    amount_eth = 1e18
    amount_usdc = 5000e18

    liq0 = liquidity0(amount_eth, sqrtp_cur, sqrtp_upp)
    liq1 = liquidity1(amount_usdc, sqrtp_cur, sqrtp_low)
    liq = int(min(liq0, liq1))

    print(f"sqrtp {sqrtp_cur}")
    print(f"liquidity: {liq}")

    amount0 = calc_amount0(liq, sqrtp_upp, sqrtp_cur)
    amount1 = calc_amount1(liq, sqrtp_low, sqrtp_cur)
    print((amount0, amount1))


def with_pool_mechanics():
    """
    Experiments with my setting to see what the liquidity amount
    should be.  See how NFTPosition manager calculates liquidity
    that's passed to pool.mint()

    1. Calcluate sqrt price for target price
    2. Calculate current tick.  Get price_to_tick. then find nearest usable by spacing
    3. Calculate amount of liquidity for tick/price range given amounts
    """

    def get_tick_from_sqrtp(price: float, spacing=10):
        sp = price_to_sqrtp(price)
        return price_to_tick(sp)

    price = 5000.00
    amount_eth = 1e18
    amount_usdc = 5000e18

    sqrtp_cur = price_to_sqrtp(price)
    current_tick = price_to_tick(price)
    lowtick = price_to_tick_with_spacing(4900)
    hightick = price_to_tick_with_spacing(5100)

    print("-------------------")

    print(f"SQRTP: {sqrtp_cur}")
    print(f"lowtick: {lowtick}")
    print(f"current tick: {current_tick}")
    print(f"hightick: {hightick}")

    amount_eth = 1e18
    amount_usdc = 5000e18

    liq0 = liquidity0(amount_eth, sqrtp_cur, tick_to_sqrtx96(hightick))
    liq1 = liquidity1(amount_usdc, sqrtp_cur, tick_to_sqrtx96(lowtick))
    liq = int(min(liq0, liq1))

    print(f"liquidity: {liq}")
    print("------------------------------")


### End ###


if __name__ == "__main__":
    # run_basic()
    # with_pool_mechanics()
    test1()
