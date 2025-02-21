"""
Uniswap v3 pool.  Represents a token pair and fee schedule.
For simplicty, all tokens use 10^18 decimals.
"""

from eth_utils import is_address
from typing import Tuple
from dataclasses import dataclass

from dexsim.abis import uniswap_token
from dexsim.utils import (
    price_to_sqrtp,
    sqrtp_to_price,
    price_to_tick_with_spacing,
    as_18,
    from_18,
    are_sorted_tokens,
)
from simular import PyEvm, Contract, contract_from_inline_abi

# purposely far in the future to make
# sure the trade is within the deadline.
EXECUTE_SWAP_DEADLINE = int(1e32)

# Uniswap v3 fee schedule and spacing
FEE_RANGE = [100, 500, 3000, 10_000]
FEE_TICK_SPACING = [1, 10, 60, 200]


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


@dataclass
class Token:
    """
    Meta information for a token
    """

    symbol: str
    start_price: 1

    @property
    def initial_price(self):
        return as_18(self.start_price)


def pool_contract(evm):
    """helper to provide pool interface"""
    return contract_from_inline_abi(
        evm,
        [
            "function liquidity()(uint128)",
            "function slot0()(uint160,int24,uint16,uint16,uint16,uint8,bool)",
        ],
    )


class Pool:
    """
    Represents a pool in Uniswap v3. Contains the core functionality to interact with the pool:
    - create a pair
    - mint/burn tokens associated with the pool
    - mint an NFT liquidity position
    - add/remove liquidity to a position
    - swap tokens in both directions
    """

    name: str  # auto-generated: e.g. DAI_USDC_500
    step: int  # this is the model step
    token0: Contract
    token1: Contract
    fee: int
    router: Contract
    nftposition: Contract
    pool_contract: Contract

    def __init__(
        self,
        _evm: PyEvm,
        _token_a: Token,
        _token_b: Token,
        _fee: int,
        _router: Contract,
        _nftposition: Contract,
        _deployer_address: str,
    ):
        """
        Create and deploy a new pool.

        This is done automatically by the DEX
        """
        assert _fee in FEE_RANGE, "Not a valid pool fee"
        assert (
            _token_b.start_price == 1
        ), "token b should always have a starting price of 1"

        self.name = f"{_token_a.symbol}_{_token_b.symbol}_{_fee}"
        self.step = 0
        self.fee = _fee
        assert is_address(
            _deployer_address
        ), "Not a valid wallet address for the pool deployer"

        self.deployers_address = _deployer_address
        self.router = _router
        self.nftposition = _nftposition

        _a = uniswap_token(_evm)
        _b = uniswap_token(_evm)
        _a.deploy(_token_a.symbol, caller=_deployer_address)
        _b.deploy(_token_b.symbol, caller=_deployer_address)

        # IMPORTANT: addresses are required to be sorted. If not, it can
        # cause a pool key issue.  We sort the addresses here
        # and re-assign symbol names if needed to match the
        # initial input
        if bytes.fromhex(_a.address[2:]) < bytes.fromhex(_b.address[2:]):
            self.token0 = _a
            self.token1 = _b
        else:
            self.token0 = _b
            self.token0.update_symbol.transact(
                _token_a.symbol, caller=_deployer_address
            )
            self.token1 = _a
            self.token1.update_symbol.transact(
                _token_b.symbol, caller=_deployer_address
            )

        # calculate initial price as SQRTPx96
        sqrtp = price_to_sqrtp(_token_b.initial_price / _token_a.initial_price)

        # create the pool
        pool_address = self.nftposition.createAndInitializePoolIfNecessary.transact(
            self.token0.address,
            self.token1.address,
            _fee,
            sqrtp,
            caller=_deployer_address,
        ).output
        self.pool_contract = pool_contract(_evm).at(pool_address)

    def get_sqrtp_tick(self) -> Tuple[int, int]:
        """
        Returns:
            The current price as sqrtpX96 and the active pool tick.
            sqrtpX96: is the price of token0 in terms of token1 in the X96 format.
            active tick: is the current liquidity pool position.
        """
        slot_info = self.pool_contract.slot0.call()
        return (slot_info[0], slot_info[1])

    def exchange_prices(self) -> Tuple[float, float]:
        """
        Return the exchange prices automatically adjusted for decimals (1e18)
        :return (price of token0, price of token1)
        """
        sqrtp, _ = self.get_sqrtp_tick()
        t1 = sqrtp_to_price(sqrtp)
        t0 = 1e18 / t1 / 1e18
        return (t0, t1)

    def mint_tokens(self, amt_t0: float, amt_t1: float, agent: str):
        """
        Mint tokens in the instruments ERC20 contract.
        This funds the agent. Needed for swaps/liquidity calls, etc...

        For example, if token0 is USDC and token1 is WETH, this will mint
        the respective amount of tokens in both contracts.

        Input amounts are automatically scaled for the token's decimal places.

        Args:
            amt_to: amount of token0
            amt_t1: amount of token1
            agent: wallet address for the tokens
        """
        at0 = as_18(amt_t0)
        at1 = as_18(amt_t1)

        self.token0.mint.transact(agent, at0, caller=agent)
        self.token1.mint.transact(agent, at1, caller=agent)

    def burn_tokens(self, amt_t0: float, amt_t1: float, agent: str):
        """
        Burn tokens for the given agent in the given instruments contracts.
        You can only burn what you own/have control over.

        Args:
            amt_to: float, amount of token0
            amt_t1: float, amount of token1
            agent: str, wallet address for the tokens
        """
        at0 = as_18(amt_t0)
        at1 = as_18(amt_t1)

        bal0 = self.token0.balanceOf.call(agent)
        bal1 = self.token1.balanceOf.call(agent)

        if at0 > 0 and bal0 >= at0:
            self.token0.burn.transact(agent, at0, caller=agent)
        if at1 > 0 and bal1 >= at1:
            self.token1.burn.transact(agent, at1, caller=agent)

    def token_pair_balance(self, owner: str) -> Tuple[int, int]:
        """
        This is a helper function to get the ERC20 token balances for the
        given owner. This is NOT the balance of tokens in a given liquidity position.
        This can be, for example, all the USDC/WETH owned by 'owner'.

        Args:
            owner: str, the wallet address

        Returns:
            (token0, token1) balances for 'owner'.  Balances are automatically scaled down from decimal places
        """
        bal0 = self.token0.balanceOf.call(owner)
        bal1 = self.token1.balanceOf.call(owner)
        return (
            from_18(bal0),
            from_18(bal1),
        )

    def reserves(self) -> Tuple[int, int]:
        """
        Returns the total amount of tokens owned by the pool.

        Returns:
            (token0, token1) balances for the pool.  Balances are automatically scaled down from decimal places
        """
        return self.token_pair_balance(self.pool_contract.address)

    def mint_liquidity_position(
        self,
        token0_amount: float,
        token1_amount: float,
        low_price: float,
        high_price: float,
        agent: str,
    ) -> Tuple[int, int, int]:
        """
        Mint a new position in the pool. In addition to the amounts used, it also
        returns the NFT position ID used to lookup the position.

        Args:
            token0_amount: float, amount of token0 to mint
            token1_amount: float, amount of token1 to mint
            low_price: float, low price range for the position
            high_price: float, high price range for the position
            agent, str, the wallet address of the caller

        Returns:
            int, actual amount used for token0
            int, actual amount used for token1
            int, NFT token ID
        """
        bal0, bal1 = self.token_pair_balance(agent)
        assert bal0 >= token0_amount and bal1 >= token1_amount, "insufficient balance"

        # check token addresses are sorted.  This is done automatically when creating the pool
        assert are_sorted_tokens(
            self.token0.address, self.token1.address
        ), "token pair are not sorted"

        t0amt = as_18(token0_amount)
        t1amt = as_18(token1_amount)

        # adjust and sort ticks
        spacing = get_spacing_for_fee(self.fee)
        lowtick = price_to_tick_with_spacing(1e18 / as_18(low_price), spacing)
        hightick = price_to_tick_with_spacing(1e18 / as_18(high_price), spacing)
        if lowtick > hightick:
            lowtick, hightick = hightick, lowtick

        # approve the nft manager to move tokens on our behalf
        self.token0.approve.transact(self.nftposition.address, t0amt, caller=agent)
        self.token1.approve.transact(self.nftposition.address, t1amt, caller=agent)

        # mint the liquidity
        token_id, _liq, a0, a1 = self.nftposition.mint.transact(
            (
                self.token0.address,
                self.token1.address,
                self.fee,
                lowtick,
                hightick,
                t0amt,
                t1amt,
                0,
                0,
                agent,
                int(2e34),
            ),  # the 2000... number is just a deadline we set high
            caller=agent,
        ).output

        return (a0, a1, token_id)

    def get_liquidity_position(self, token_id: int) -> Tuple[int, int, int, int]:
        """
        Get the liquidity position information for a given LP by the NFT token ID.
        You can extract the actual balances of each token by using the 'calculate_liquidity_balance'
        function in utils.py

        Args:
            token_id: int, the NFT token id for the position.

        Returns:
            int, pool fee
            int, lower tick value in the positions range
            int, upper tick value in the positions range
            int, liquidity as a single value
        """
        _, _, _, _, fee, tl, tu, liq, _, _, _, _ = self.nftposition.positions.call(
            token_id
        )
        return fee, tl, tu, liq

    def increase_liquidity(
        self,
        token_id: int,
        amount0: float,
        amount1: float,
        agent: str,
    ) -> Tuple[int, int, int]:
        """
        Increase the liquidity of a position for a given tokenid.  Tokenid
        corresponds to an existing minted position for the sender (agent).

        Args:
            token_id: int, the NFT token id
            amount0: float, the amount of token0 to increase
            amount1: float, the amount of token1 to increase
            agent: str, the caller address that's the owner of the position

        Returns:
          - liquidity: int, the new amount of liquidity for the position
          - amt0: int, the actual amount of token0 used
          - amt1: int, the actual amount of token1 used
        """
        amt0 = as_18(amount0)
        amt1 = as_18(amount1)

        # approve the nft manager to move tokens on our behalf
        self.token0.approve.transact(self.nftposition.address, amt0, caller=agent)
        self.token1.approve.transact(self.nftposition.address, amt1, caller=agent)

        liq, a0, a1 = self.nftposition.increaseLiquidity.transact(
            (token_id, amt0, amt1, 0, 0, EXECUTE_SWAP_DEADLINE), caller=agent
        ).output
        return (liq, a0, a1)

    def remove_liquidity(
        self, token_id: int, percentage: float, agent: str
    ) -> Tuple[int, int]:
        """
        Remove a percentage amount of liquidity from the position.  This changes the (agent) caller's
        position and 'collects' and transfers tokens back to the caller in the ERC20 contracts.

        Note, percentage is represented as a fractional value in the range of 0.0 - 1.0.
        For example, 0.5 = 50%

        Args:
            token ID: int, the NFT token id for the position
            percentage: float, the percentage of liquidity to remove
            agent: str, the caller's wallet address (the owner of the position)

        Returns:
            Amount of token0 returned
            Amount of token1 returned
        """
        assert percentage > 0 and percentage <= 1, "invalid percentage"

        _, _, _, _, _, _, _, liq, _, _, _, _ = self.nftposition.positions.call(token_id)
        amount = liq * percentage
        self.nftposition.decreaseLiquidity.transact(
            (token_id, int(amount), 0, 0, EXECUTE_SWAP_DEADLINE), caller=agent
        )

        # check position to see how much is owed to agent
        _, _, _, _, _, _, _, _, _, _, t0owed, t1owed = self.nftposition.positions.call(
            token_id
        )

        # call 'collect'
        result = self.nftposition.collect.transact(
            (token_id, agent, t0owed, t1owed), caller=agent
        )

        return result.output

    def swap_0_for_1(self, amount: float, agent: str) -> Tuple[float, float]:
        """
        Swap some 'amount' of token0 for token1.

        Args:
            amount: float, the amount of token0 to use to buy token1
            agent: str, the agent's wallet address

        Returns:
            amount of token0 spent
            amount of token1 received

        NOTE:  Be sure the input amount is in the proper
        format for token0.  For example, if token0 is USDC, and you
        want to spend $3000 worth of USDC for token1, enter 3000. Under
        the covers, this method will offset for the actual decimal format.

        What does that mean?  USDC may have 18 decimal places, so the actual amount
        is 3000 * 1e18.  This method will automatically convert to the decimal places.
        """
        b0, _ = self.token_pair_balance(agent)
        assert b0 >= amount, "insufficient balance!"
        amount_in = as_18(amount)

        # approve the router to move token's on behalf of the agent
        self.token0.approve.transact(self.router.address, amount_in, caller=agent)

        recv = self.router.exactInputSingle.transact(
            (
                self.token0.address,
                self.token1.address,
                self.fee,
                agent,
                EXECUTE_SWAP_DEADLINE,
                amount_in,
                0,
                0,
            ),
            caller=agent,
        )
        return (amount_in, recv.output)

    def swap_1_for_0(self, amount, agent):
        """
        Swap some 'amount' of token1 for token0.

        Args:
            amount: float, the amount of token1 to use to buy token0
            agent: str, the agent's wallet address

        Returns:
            amount of token1 spent
            amount of token0 received

        NOTE:  Be sure the input amount is in the proper
        format for token0.  For example, if token0 is USDC, and you
        want to spend $3000 worth of USDC for token1, enter 3000. Under
        the covers, this method will offset for the actual decimal format.

        What does that mean?  USDC may have 18 decimal places, so the actual amount
        is 3000 * 1e18.  This method will automatically convert to the decimal places.
        """
        _, b1 = self.token_pair_balance(agent)
        assert b1 >= amount, "insufficient balance!"
        amount_in = as_18(amount)

        # approve the router to move token's on behalf of the agent
        self.token1.approve.transact(self.router.address, amount_in, caller=agent)

        recv = self.router.exactInputSingle.transact(
            (
                self.token1.address,
                self.token0.address,
                self.fee,
                agent,
                EXECUTE_SWAP_DEADLINE,
                amount_in,
                0,
                0,
            ),
            caller=agent,
        )

        return (amount_in, recv.output)
