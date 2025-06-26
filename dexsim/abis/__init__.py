from simular import PyAbi, Contract, contract_from_raw_abi
from pathlib import Path

PATH = Path(__file__).parent

# Remote live contracts.  These addresses are needed as the
# EVM snapshot has the contract information stored by these accounts
UNISWAP_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
UNISWAP_SWAP_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAP_NFPOSTION_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
UNISWAP_QUOTER_V2 = "0x41FAd82191A1660fFEf92995f7Ff3d2f91B8E3cb"


def erc20_token(evm):
    """
    Generic ERC20 contract to be used for tokens
    """
    with open(f"{PATH}/PoolToken.json") as f:
        full = f.read()
    return contract_from_raw_abi(evm, full)


def uniswap_nftpositionmanager(evm):
    """
    Uniswap 3 NFT manager to track LP positions
    """
    with open(f"{PATH}/NonFungPosition.abi") as f:
        abi = f.read()
    abi = PyAbi.from_abi_bytecode(abi, None)
    return Contract(evm, abi).at(UNISWAP_NFPOSTION_MANAGER)


def uniswap_factory_contract(evm):
    """
    Uniswap 3 factory
    """
    with open(f"{PATH}/UniswapV3Factory.abi") as f:
        abi = f.read()
    abi = PyAbi.from_abi_bytecode(abi, None)
    return Contract(evm, abi).at(UNISWAP_FACTORY)


def uniswap_router_contract(evm):
    """
    Uniswap 3 router
    """
    with open(f"{PATH}/SwapRouter.abi") as f:
        abi = f.read()
    abi = PyAbi.from_abi_bytecode(abi, None)
    return Contract(evm, abi).at(UNISWAP_SWAP_ROUTER)


def uniswap_pool_contract(evm, pool_address):
    """
    Uniswap 3 pool
    """
    with open(f"{PATH}/UniswapV3Pool.abi") as f:
        abi = f.read()
    abi = PyAbi.from_abi_bytecode(abi, None)
    return Contract(evm, abi).at(pool_address)


def uniswap_quoter(evm):
    """
    V2 Uniswap quoter
    """
    with open(f"{PATH}/QuoterV2.abi") as f:
        abi = f.read()
    abi = PyAbi.from_abi_bytecode(abi, None)
    return Contract(evm, abi).at(UNISWAP_QUOTER_V2)


def lending_pool(evm):
    """
    Create a lending pool contract instance
    """
    with open(f"{PATH}/Lender.json") as f:
        abi = f.read()
    return contract_from_raw_abi(evm, abi)
