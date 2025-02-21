from typing import List
from eth_utils import is_address
from omegaconf import OmegaConf, DictConfig
from simular import create_account, create_many_accounts, PyEvm

from dexsim.pool import Pool, Token, FEE_RANGE
from dexsim.snapshot import load_evm_from_snapshot
from dexsim.abis import uniswap_router_contract, uniswap_nftpositionmanager

# Fixed fees recognized by Uniswap v3
UNISWAP_FEES = [0.01, 0.05, 0.3, 1.0]


def load_configuration(evm: PyEvm, fn: str) -> DictConfig:
    if fn[-5:] != ".yaml":
        raise ValueError("Expected a YAML file: .yaml")

    try:
        config = OmegaConf.load(fn)
        config.simulator.pool_fees = UNISWAP_FEES
        return config.simulator
    except Exception as e:
        raise ValueError(
            f"Could not load config file. Please check path and file type. Error message is {str(e)}"
        )


class PoolsHelper(dict):
    """
    Used by DEX. Provides attribute access to pools.  For example, if a pool
    is configured with the name 'usdc_eth', it can be accessed as
    'dex.pools.usdc_eth'
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'Pools' has no pool named: '{key}'")

    def __setattr__(self, key, value):
        self[key] = value


class DEX:
    """
    Represents Uniswap exchange with 1 or more pools. Use this class
    to setup and interact with pools in a model.

    Pools are created/configured via the YAML configuration file.
    The DEX has a Dict of pools keyed by the name specified in the
    configuration file.

    To interact with a pool you use the name of the pool configured in the yaml file.
    For example,   `dex.pools.eth_usdc`.  At his point, you can interact
    with all the pool functionality. LP, swaps, etc...

    Attributes:
        config (DictConfig): The configuration object
        pools (PoolHelper): attribute level access to the pools by name
    """

    def __init__(self, conf_file: str):
        """Create the DEX.

        Args:
            conf_file: the path/name of the yaml configuration file
        """
        # setup the EVM and needed Uniswap contracts
        self.__evm = load_evm_from_snapshot()

        # load the config file
        self.config = load_configuration(self.__evm, conf_file)
        self.pools = PoolsHelper()

        # load core contracts
        self.__router = uniswap_router_contract(self.__evm)
        self.__nft = uniswap_nftpositionmanager(self.__evm)

        for n, pc in self.config.pools.items():
            price = pc.price
            f = pc.get("fee", 0.05)

            fee = int(f * 10_000)
            assert fee in FEE_RANGE, "Invalid Unswap v3 fee"

            deployer = create_account(self.__evm)

            t0 = Token(pc.tokens[0], price)
            t1 = Token(pc.tokens[1], 1.0)

            self.pools[n] = Pool(
                self.__evm, t0, t1, fee, self.__router, self.__nft, deployer
            )

    def create_one_or_more_addresses(
        self, address=None, num=1, wei=int(1e18)
    ) -> List[str] | str:
        """Create 1 or more wallet addresses in the EVM.  If you pass 'address' it will only
        create 1 wallet entry for that address.

        Args:
            address: optional (default: None): the address you want to create in the EVM
            num: optional (default: 1): the number of wallets to create
            wei: optional (default: 1e18): amount to fund the account with

        Returns:
            Either a list or single wallet address
        """
        if num > 1:
            return create_many_accounts(self.__evm, num, value=wei)

        if address:
            assert is_address(address), f"{address} is not a valid wallet address"

        return create_account(self.__evm, address=address, value=wei)

    def list_pools(self) -> List[str]:
        """List all pools by name
        Returns:
            a list all pool names know to the DEX
        """
        return [name for name in self.pools.keys()]

    def total_number_of_pools(self) -> int:
        """The number of pools in the exchange
        Returns:
            the number of pools in the exchange
        """
        return len(self.pools)
