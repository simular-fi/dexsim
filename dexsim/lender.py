"""
Provides support for a simple lending pool.  Each DEX pool can have one.

Lending is configured in the configuation file.
See tests/testconfig.yaml for an example.
"""

from . import Address
from .utils import sqrtp_to_price, as_18, from_18
from .abis import lending_pool, uniswap_pool_contract

from simular import Contract, create_account, contract_from_inline_abi


def token_contract(evm):
    """helper to provide erc20 token interface"""
    return contract_from_inline_abi(
        evm,
        [
            "function mint(address,uint256)",
            "function approve(address,uint256)(bool)",
            "function balanceOf(address)(uint256)",
        ],
    )


# initial lending capital in the lending pool
LENDING_CAPITAL = as_18(1_000_000_000)


class Lender:
    collateral: Address
    lending: Address
    pool: Address
    which_is_collateral: int
    lending_contract: Contract
    lending_address: Address

    def __init__(
        self,
        evm,
        _collateral: Address,
        _lending: Address,
        _ctoken: int,
        _pool: Address,
        deployer,
    ):
        self.collateral = _collateral
        self.lending = _lending
        self.which_is_collateral = _ctoken
        self.pool = _pool
        self.evm = evm
        self.lending_contract = lending_pool(self.evm)

        self.deployer = create_account(evm, value=int(2e18))
        self.lending_contract.deploy(_lending, _collateral, caller=deployer)
        self.lending_address = self.lending_contract.address

        self._bootstrap_lending_capital(deployer)

    def _bootstrap_lending_capital(self, agent: Address):
        """
        Provide lending capital for the pool
        """
        self.mint_lending_token.transact(LENDING_CAPITAL, caller=agent)

        token_contract(self.evm).at(self.lending).approve.transact(
            self.lending_contract.address, LENDING_CAPITAL, caller=agent
        )
        self.lending_contract.supplyLendingToken.transact(LENDING_CAPITAL, caller=agent)

    def _update_collateral_price(self):
        """
        Call the pool for collateral exchange price.  must be
        in 1e18 format for lending contract. Update Price in
        Lending Contract
        """
        slots = uniswap_pool_contract(self.evm, self.pool).slot0.call()
        p = sqrtp_to_price(slots[0])

        if self.which_is_collateral == 0:
            price = as_18(1 / p)
        else:
            price = as_18(p)

        self.lending_contract.setPrice.transact(price, caller=self.deployer)

    def mint_collateral_token(self, amount: int, agent: Address):
        """
        Helper to mint collateral tokens to the associated ERC20 token. This is NOT
        the token balance in the lending contract.
        """
        token_contract(self.evm).at(self.collateral).mint.transact(
            agent, as_18(amount), caller=agent
        )

    def collateral_token_balance(self, agent: Address):
        """
        Helper to check the collateral token balance int the associated ERC20 token. This is NOT
        the token balance in the lending contract.
        """
        bal = token_contract(self.evm).at(self.collateral).balanceOf.call(agent)
        return from_18(bal)

    def mint_lending_token(self, amount: int, agent: Address):
        """
        Helper to mint collateral tokens to the associated ERC20 token. This is NOT
        the token balance in the lending contract.
        """
        token_contract(self.evm).at(self.lending).mint.transact(
            agent, as_18(amount), caller=agent
        )

    def lending_token_balance(self, agent: Address):
        """
        Helper to check the collateral token balance int the associated ERC20 token. This is NOT
        the token balance in the lending contract.
        """
        bal = token_contract(self.evm).at(self.lending).balanceOf.call(agent)
        return from_18(bal)

    def get_collateral_price(self):
        """
        Return the current price of collateral. This is in 1e18 format.
        """
        self._update_collateral_price()
        return self.lending_contract.getCurrentCollateralPrice.call()

    def provide_collateral(self, amount: int, agent: Address):
        """
        Provide collateral to the lending contract for a loan.
        """
        amt18 = as_18(amount)
        # Approve the lending contract to move money on agent's behalf
        token_contract(self.evm).at(self.collateral).approve.transact(
            self.lending_contract.address, amt18, caller=agent
        )
        self.lending_contract.supplyCollateral.transact(amt18, caller=agent)

    def borrow(self, amount: int, agent: Address):
        """
        Borrow 'amount' of the lending token.
        """
        self._update_collateral_price()
        self.lending_contract.borrow.transact(as_18(amount), caller=agent)
        return True

    def withdraw_collateral(self, agent: Address):
        """
        Withdraw all collateral.  You can only withdraw collateral if the
        loan is paid in full. Collateral is transfer backed to the token
        account of the caller.
        """
        self.lending_contract.withdrawCollateral.transact(caller=agent)
        return True

    def repay_loan(self, amount: int, agent: Address):
        """
        Repay 'amount' towards the loan
        """
        amt18 = as_18(amount)
        # Approve the loan contract to move money on agent's behalf
        token_contract(self.evm).at(self.lending).approve.transact(
            self.lending_contract.address, amt18, caller=agent
        )
        self.lending_contract.repayLoan.transact(amt18, caller=agent)
        pass

    def liquidate_loan(self, amount: int, agent: Address):
        """
        Liquidate a loan.
        """
        amt18 = as_18(amount)
        # Approve the loan contract to move money on agent's behalf
        token_contract(self.evm).at(self.lending).approve.transact(
            self.lending_contract.address, amt18, caller=agent
        )
        self.lending_contract.liquidateLoan.transact(amount, caller=agent)
        return True

    def loan_information(self, agent: Address):
        """
        Return information about a loan account for the given agent
        """
        self._update_collateral_price()
        return self.lending_contract.loanInformation.call(agent)

    def available_to_loan(self):
        """
        How much of the lending token is avaiable for loans?
        """
        amt = self.lending_contract.availableToLend.call()
        return from_18(amt)

    def collateral_required(self, amount: int):
        """
        How much collateral is require for a loan of 'amount'?
        """
        self._update_collateral_price()
        amt18 = as_18(amount)
        return from_18(self.lending_contract.collateralNeeded.call(amt18))

    def is_active_loan(self, borrower: Address):
        """
        Does the 'borrower' have a loan?
        """
        return self.lending_contract.isActiveLoan.call(borrower)
