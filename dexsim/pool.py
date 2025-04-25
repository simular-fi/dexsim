"""
Uniswap v3 pool.  Represents a token pair and fee schedule.
For simplicty, all tokens use 10^18 decimals.
"""

from typing import Tuple
from eth_utils import is_address


from . import Address
from .abis import erc20_token, uniswap_quoter
from .utils import (
    sqrtp_to_price,
    price_to_sqrtp,
    price_to_tick_with_spacing,
    as_18,
    from_18,
    get_spacing_for_fee,
    is_valid_tick,
    tick_to_price,
    calculate_liquidity_balance,
)


from simular import PyEvm, Contract, contract_from_inline_abi

# purposely far in the future to make
# sure the trade is within the deadline.
EXECUTE_SWAP_DEADLINE = int(1e32)


def pool_contract(evm):
    """helper to provide pool interface"""
    return contract_from_inline_abi(
        evm,
        [
            "function ticks(int24)(uint128, int128, uint256, uint256, int56, uint160, uint32, bool)",
            "function liquidity()(uint128)",
            "function fee()(uint24)",
            "function token0()(address)",
            "function token1()(address)",
            "function initialize(uint160)",
            "function slot0()(uint160,int24,uint16,uint16,uint16,uint8,bool)",
            "function approve(address,uint256)(bool)",
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

    token0: Address
    token1: Address
    sqrtp: int
    fee: int
    router: Contract
    nftposition: Contract
    pool_contract: Contract

    def __init__(
        self,
        _evm: PyEvm,
        _pool_address: Address,
        _token_a: Address,
        _token_b: Address,
        _fee: int,
        _sqrtp: int,
        _router: Contract,
        _nftposition: Contract,
        _deployer_address: Address,
    ):
        """
        Initialize the new pool.

        This is done automatically by the DEX
        """
        assert is_address(
            _token_a
        ), "Not a valid address for Token A. Check naming in the configuration file"
        assert is_address(
            _token_b
        ), "Not a valid address for Token B. Check naming in the configuration file"
        assert is_address(
            _deployer_address
        ), "Not a valid wallet address for the pool deployer"

        self.fee = _fee
        self.sqrtp = _sqrtp
        self.token0 = _token_a
        self.token1 = _token_b
        self.deployers_address = _deployer_address

        self.router = _router
        self.nftposition = _nftposition

        self.pool_contract = pool_contract(
            _evm,
        ).at(_pool_address)

        self.pool_contract.initialize.transact(
            self.sqrtp, caller=self.deployers_address
        )
        self.token_contract = erc20_token(_evm)
        self.pool_quoter = uniswap_quoter(_evm)

    def get_sqrtp_tick(self) -> Tuple[int, int]:
        """
        Returns:
            The current price as sqrtpX96 and the active pool tick.
            sqrtpX96: is the price of token0 in terms of token1 in the X96 format.
            active tick: is the current liquidity pool position.
        """
        slot_info = self.pool_contract.slot0.call()
        return (slot_info[0], slot_info[1])

    def liquidity(self) -> int:
        """
        Returns the in-range liquidity available to the pool
        This is NOT the total liquidity across all ticks
        """
        return self.pool_contract.liquidity.call()

    def net_liquidity(self, tick: int) -> Tuple[int, bool]:
        """
        Return the net liquidity when crossing the given tick.
        In some cases this may be zero or negative.
        """
        (
            _,
            liqNet,
            _,
            _,
            _,
            _,
            _,
            initialized,
        ) = self.pool_contract.ticks.call(tick)
        return (liqNet, initialized)

    def exchange_rates(self) -> Tuple[float, float]:
        """
        Prices in terms of the other.
        - The first value is the amount of token0 for 1 token1
        - Second value is the amount of token1 for 1 token0
        Example: (0.98, 1.01) means:
        - $0.98 worth of token0 to buy 1 token1
        - $1.01 worth of token1 to buy 1 token 0
        So in this example, token0 is more expensive.
        """
        # this is alway y/x
        sqrtp, _ = self.get_sqrtp_tick()

        t1 = sqrtp_to_price(sqrtp)
        return (1 / t1, t1)

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

        self.token_contract.at(self.token0).mint.transact(agent, at0, caller=agent)
        self.token_contract.at(self.token1).mint.transact(agent, at1, caller=agent)

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

        bal0 = self.token_contract.at(self.token0).balanceOf.call(agent)
        bal1 = self.token_contract.at(self.token1).balanceOf.call(agent)

        if at0 > 0 and bal0 >= at0:
            self.token_contract.at(self.token0).burn.transact(agent, at0, caller=agent)
        if at1 > 0 and bal1 >= at1:
            self.token_contract.at(self.token1).burn.transact(agent, at1, caller=agent)

    def token_pair_balance(self, agent: str) -> Tuple[int, int]:
        """
        This is a helper function to get the ERC20 token balances for the
        given owner. This is NOT the balance of tokens in a given liquidity position.
        This can be, for example, all the USDC/WETH owned by 'owner'.

        Args:
            owner: str, the wallet address

        Returns:
            (token0, token1) balances for 'owner'.  Balances are automatically scaled down from decimal places
        """
        bal0 = self.token_contract.at(self.token0).balanceOf.call(agent)
        bal1 = self.token_contract.at(self.token1).balanceOf.call(agent)
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
        bal0 = self.token_contract.at(self.token0).balanceOf.call(
            self.pool_contract.address
        )
        bal1 = self.token_contract.at(self.token1).balanceOf.call(
            self.pool_contract.address
        )
        return (
            from_18(bal0),
            from_18(bal1),
        )

    def mint_liquidity_position(
        self,
        token0_amount: float,
        token1_amount: float,
        low_price: float,
        high_price: float,
        agent: str,
    ) -> Tuple[int, int, int, int]:
        """
        Mint a new IN RANGE position in the pool. To simplify adding
        liquidity (correctly), it will ensure the price range entered is within
        range of the current price.  An invalid price range will throw an assertion
        error.

        Current price is based on token1/token0. The low and high price range for
        minting, should be based on this ratio.
        For example, if token0 price is 2000 and token1 price is 1. Then a price
        range of 1900 - 2100 would be specified as 1/9000 - 1/2100.

        Args:
            - token0_amount: float, amount of token0 to mint
            - token1_amount: float, amount of token1 to mint
            - low_price: float, low price range for the position
            - high_price: float, high price range for the position
            - agent, str, the wallet address of the caller

        Returns:
            - actual amount used for token0
            - actual amount used for token1
            - amount of liquidity provided
            - NFT token ID
        """
        # check tick range first by converting prices to ticks
        _, current_tick = self.get_sqrtp_tick()

        spacing = get_spacing_for_fee(self.fee)
        lt = price_to_tick_with_spacing(low_price, spacing)
        ht = price_to_tick_with_spacing(high_price, spacing)

        if not is_valid_tick(lt):
            raise Exception(f"Mint position: {lt} is not a valid tick")
        if not is_valid_tick(ht):
            raise Exception(f"Mint position: {ht} is not a valid tick")

        # sort for negative integers
        if lt > ht:
            lowtick = ht
            hightick = lt
        else:
            lowtick = lt
            hightick = ht

        t0amt = as_18(token0_amount)
        t1amt = as_18(token1_amount)

        bal0 = self.token_contract.at(self.token0).balanceOf.call(agent)
        bal1 = self.token_contract.at(self.token1).balanceOf.call(agent)

        assert (
            bal0 >= t0amt and bal1 >= t1amt
        ), "Mint position: Insufficient token balance. You need to mint more tokens"

        self.token_contract.at(self.token0).approve.transact(
            self.nftposition.address, t0amt, caller=agent
        )
        self.token_contract.at(self.token1).approve.transact(
            self.nftposition.address, t1amt, caller=agent
        )

        # mint the liquidity
        token_id, liq, a0, a1 = self.nftposition.mint.transact(
            (
                self.token0,
                self.token1,
                self.fee,
                lowtick,
                hightick,
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

    def get_liquidity_position(self, token_id: int) -> Tuple[int, int, int, int]:
        """
        Get the liquidity position information for a given LP by the NFT token ID.
        You can extract the actual balances of each token by using the 'calculate_liquidity_balance'
        function in utils.py OR see below...

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

    def get_amounts_by_liquidity_position(self, token_id: int):
        """
        Return the amount of tokens (x,y) for a given liquidity position.
        Note: this will not be exact as the pool hold some of the
        liquidity for fees.
        """
        _, tl, tu, liq = self.get_liquidity_position(token_id)
        _, ct = self.get_sqrtp_tick()
        lp = tick_to_price(tl)
        up = tick_to_price(tu)
        cp = tick_to_price(ct)
        return calculate_liquidity_balance(liq, lp, up, cp)

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
        self.token_contract.at(self.token0).approve.transact(
            self.nftposition.address, amt0, caller=agent
        )
        self.token_contract.at(self.token1).approve.transact(
            self.nftposition.address, amt1, caller=agent
        )

        liq, a0, a1 = self.nftposition.increaseLiquidity.transact(
            (token_id, amt0, amt1, 0, 0, EXECUTE_SWAP_DEADLINE), caller=agent
        ).output
        return (liq, from_18(a0), from_18(a1))

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

        # call to collect tokens based on what's owed the caller
        # internally this also interacts with 'pool' contract's collect.
        result = self.nftposition.collect.transact(
            (token_id, agent, t0owed, t1owed), caller=agent
        )

        amt0, amt1 = result.output
        return (from_18(amt0), from_18(amt1))

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
        self.token_contract.at(self.token0).approve.transact(
            self.router.address, amount_in, caller=agent
        )

        recv = self.router.exactInputSingle.transact(
            (
                self.token0,
                self.token1,
                self.fee,
                agent,
                EXECUTE_SWAP_DEADLINE,
                amount_in,
                0,
                0,
            ),
            caller=agent,
        )
        return (from_18(amount_in), from_18(recv.output))

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
        self.token_contract.at(self.token1).approve.transact(
            self.router.address, amount_in, caller=agent
        )

        recv = self.router.exactInputSingle.transact(
            (
                self.token1,
                self.token0,
                self.fee,
                agent,
                EXECUTE_SWAP_DEADLINE,
                amount_in,
                0,
                0,
            ),
            caller=agent,
        )
        return (from_18(amount_in), from_18(recv.output))

    def increase_price_of_token0(
        self, target_price: float, agent: Address
    ) -> Tuple[float, float]:
        """
        Increase the price token0 to `target_price`.

        This method will:
        - calculate how much of token1 needs to be swapped to increase the price
        - attempt to make the swap to move the price.

        This amount received will be token0.

        This will error if there's not enough liquidity or the caller does not
        have enough tokens.

        Args:
            target_price: the future price of token0
            agent: the caller

        Returns:
            (amount of token1 spent, amount of token0 recv)
        """
        liquidity = self.liquidity()
        target = price_to_sqrtp(target_price)
        current, _ = self.get_sqrtp_tick()

        assert (
            target > current
        ), "Cannot increase the price. The target_price is <= current"

        diff = target - current
        amount_t1_to_swap = int(liquidity * diff / 2**96)

        if amount_t1_to_swap <= 0:
            return (0.0, 0.0)

        return self.swap_1_for_0(from_18(amount_t1_to_swap), agent)

    def decrease_price_of_token0(self, target_price, agent):
        """
        Decrease the price token0 to `target_price`.

        This method will:
        - calculate how much of token0 needs to be swapped to decrease the price
        - attempt to make the swap to move the price.

        This amount received will be token1.

        This will error if there's not enough liquidity or the caller does not
        have enough tokens.

        Args:
            target_price: the future price of token0
            agent: the caller

        Returns:
            (amount of token0 spent, amount of token1 recv)
        """
        liquidity = self.liquidity()
        target = price_to_sqrtp(target_price)
        current, _ = self.get_sqrtp_tick()

        assert (
            current > target
        ), "Cannot decrease the price. The target_price is > current"

        diff = current - target
        amount_t0_to_swap = int(liquidity * diff / 2**96)
        if amount_t0_to_swap <= 0:
            # this shouldn't happen
            return (0.0, 0.0)

        return self.swap_0_for_1(from_18(amount_t0_to_swap), agent)
