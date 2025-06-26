from typing import List
from eth_utils import is_address
from omegaconf import OmegaConf, DictConfig
from simular import create_account, create_many_accounts

from .pool import Pool
from .utils import price_to_sqrtp
from .snapshot import evm_from_pool_snapshot, load_token_pair_state
from .abis import uniswap_router_contract, uniswap_nftpositionmanager

from .lender import Lender


def load_configuration(fn: str) -> DictConfig:
    if fn[-5:] != ".yaml":
        raise ValueError("Expected a YAML file: .yaml")

    try:
        config = OmegaConf.load(fn)
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
            raise AttributeError(
                f"PoolHelper: 'DEX' has no pool or lending function named: '{key}'. Check the configuration file"
            )

    def __setattr__(self, key, value):
        self[key] = value


class DEX:
    """
    Represents Uniswap exchange with 1 or more pools. Use this class
    to setup and interact with pools in a model.

    Pools are created/configured via the YAML configuration file.
    The DEX has a Dict of pools keyed by the token names and fee.

    To interact with a pool you use the name of the pool configured in the yaml file.
    For example,   `dex.pools.eth_usdc_500`. You can see the list of all pool names: `dex.list_pools()`
    You can interact with all the pool functionality. LP, swaps, etc...

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
        self.__evm = evm_from_pool_snapshot()

        # load information about deployed pools
        pairs = load_token_pair_state()

        # load the config file
        self.config = load_configuration(conf_file)
        self.pools = PoolsHelper()
        self.lending = PoolsHelper()

        # initialize pools
        self.__router = uniswap_router_contract(self.__evm)
        self.__nft = uniswap_nftpositionmanager(self.__evm)
        self.deployer = create_account(self.__evm)

        for p, vals in self.config.pools.items():
            token_pair = pairs.get(p, None)
            if not token_pair:
                raise KeyError(f"Config file: '{token_pair}' is not a recognized pool")
            if len(vals) < 2:
                raise Exception(
                    "Price values in the config file should be in the format '[price, price]'"
                )
            # calculate and set the SQRTP
            sqrtp = price_to_sqrtp(vals[1] / vals[0])

            self.pools[p] = Pool(
                self.__evm,
                token_pair.pool,
                token_pair.token0.address,
                token_pair.token1.address,
                token_pair.fee,
                sqrtp,
                self.__router,
                self.__nft,
                self.deployer,
            )

        if self.config.get("lending"):
            # Configure any lending pools IF the lending is specified in the config file
            for k, v in self.config.lending.items():
                pool_pair = pairs.get(k, None)
                if pool_pair.token0.symbol == v:
                    pair = (pool_pair.token0.address, pool_pair.token1.address, 0)
                else:
                    pair = (pool_pair.token1.address, pool_pair.token0.address, 1)
                pool_address = pool_pair.pool

                self.lending[k] = Lender(
                    self.__evm, pair[0], pair[1], pair[2], pool_address, self.deployer
                )
        else:
            print("INFO: No 'lending' configured in the configuration file")

    def create_wallet(self, address: str = None, wei: float = int(1e18)) -> str:
        """Create a single account
        Args:
            address: optional, If set will create the wallet with the given address
            wei: optional, (default: 1e18): funds the wallet with the amount of wei.

        Returns:
            wallet address
        """
        if address:
            assert is_address(address), f"{address} is not a valid wallet address"

        return create_account(self.__evm, address=address, value=wei)

    def create_many_wallets(self, num, wei=int(1e18)) -> List[str]:
        """Create `num` of wallets in the EVM.

        Args:
            num: optional (default: 1): the number of wallets to create
            wei: optional (default: 1e18): amount to fund the account with

        Returns:
            a list of wallet addresses
        """
        return create_many_accounts(self.__evm, num, value=wei)

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
