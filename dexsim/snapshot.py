"""
Used to create snapshots.  You should only use this
if you intend to *rebuild* snapshots.
"""

import os
from pathlib import Path
from omegaconf import OmegaConf, DictConfig
from simular import PyEvm, create_account


from dexsim import (
    FEE_RANGE,
    uniswap_factory_contract,
    uniswap_nftpositionmanager,
    uniswap_router_contract,
    uniswap_quoter,
    erc20_token,
)

PACKAGEDIR = Path(__file__).parent.absolute()

BASE_STATE = PACKAGEDIR.joinpath("state", "base.json")
POOL_STATE = PACKAGEDIR.joinpath("state", "pool_snapshot.json")
QUOTER_STATE = PACKAGEDIR.joinpath("state", "quoter_pool_snapshot.json")
TOKENS = PACKAGEDIR.joinpath("state", "tokens.yaml")
PAIRS = PACKAGEDIR.joinpath("state", "pairs.yaml")


def load_token_state() -> DictConfig:
    return OmegaConf.load(TOKENS)


def load_token_pair_state() -> DictConfig:
    return OmegaConf.load(PAIRS)


def evm_from_snapshot(path_fn: str = BASE_STATE) -> PyEvm:
    """
    Load EVM with saved chain state.

    Args:
        pathfn: path and filename of snapshot (json) file
    Returns:
        PyEVM: instance of the EVM
    """
    with open(path_fn) as b:
        state = b.read()
    return PyEvm.from_snapshot(state)


def evm_from_pool_snapshot() -> PyEvm:
    """Load EVM state with pre-deployed pools from a snapshot"""
    with open(QUOTER_STATE) as fh:
        return PyEvm.from_snapshot(fh.read())


def create_uniswap_snapshot():
    """
    Pull base contract state from a remote Ethereum node on main chain.
    This doesn't pull all the state in each contract. It primarily focuses
    on contract bytecode which is what's needed to create a local instance
    of the contract in our modeling environment.

    You shouldn't need to use this unless you want to recreate 'base.json'
    """

    if BASE_STATE.is_file():
        raise Warning(
            "base snapshot already exists. Are you sure you want to overwrite it?"
        )

    # TODO: change to a more generic env var
    alchemyurl = os.getenv("ALCHEMY")
    assert alchemyurl, "Missing ALCHEMY rpc node token key"

    # create vm that pulls from remote node
    evm = PyEvm.from_fork(url=alchemyurl)

    create_account(evm, address="0x1a9c8182c09f50c8318d769245bea52c32be35bc")

    # factory
    factory = uniswap_factory_contract(evm)
    for fee in FEE_RANGE:
        factory.feeAmountTickSpacing.call(fee)
    factory.owner.call()

    # router
    router = uniswap_router_contract(evm)
    router.factory.call()
    router.WETH9.call()

    # nft
    nft = uniswap_nftpositionmanager(evm)
    nft.factory.call()
    nft.WETH9.call()

    print(" ... saving base state ...")
    snap = evm.create_snapshot()
    with open(f"{BASE_STATE}", "w") as f:
        f.write(snap)


def create_tokens_and_pools():
    """
    Create a snapshot with a pre-deployed set of tokens and pools

    1. Start with base snapshop
    2. Create all the tokens needed (capture addresses)
    3. Create a pool for each pair and fee
       1. sort pair address
       2. create pool with factory.  (capture/store pool address and pair names / fee)
    4. snapshot new state

    Python dict:
    'eth_usdc_500' => 0x1234.... (address)
    """
    evm = evm_from_snapshot()
    deployer = create_account(evm)

    tokens = {}
    # deploy base tokens
    for sym in ["usdc", "dai", "weth", "wbtc"]:
        addy = erc20_token(evm).deploy(sym, caller=deployer)
        tokens[sym] = {"symbol": sym, "address": addy}

    with open("./tokens.yaml", "w") as fp:
        config = OmegaConf.create(tokens)
        OmegaConf.save(config=config, f=fp)

    # recognized pairs
    pairs = [
        ("usdc", "dai", 100),
        ("usdc", "dai", 500),
        ("usdc", "weth", 500),
        ("dai", "weth", 500),
        ("wbtc", "weth", 500),
        ("wbtc", "dai", 500),
        ("wbtc", "usdc", 500),
    ]

    poolpairs = {}
    for ta, tb, fee in pairs:
        if bytes.fromhex(tokens[ta]["address"][2:]) < bytes.fromhex(
            tokens[tb]["address"][2:]
        ):
            pair = {"token0": tokens[ta], "token1": tokens[tb], "fee": fee, "pool": ""}
        else:
            pair = {"token0": tokens[tb], "token1": tokens[ta], "fee": fee, "pool": ""}

        pool_address = uniswap_factory_contract(evm).createPool.transact(
            pair["token0"]["address"], pair["token1"]["address"], fee, caller=deployer
        )
        pair["pool"] = pool_address.output
        name = f"{pair['token0']['symbol']}_{pair['token1']['symbol']}_{fee}"
        poolpairs[name] = pair

    with open("./pairs.yaml", "w") as fp:
        config = OmegaConf.create(poolpairs)
        OmegaConf.save(config=config, f=fp)

    # save snapshot
    print(" ... saving base state ...")
    snappools = evm.create_snapshot()
    with open(f"{POOL_STATE}", "w") as f:
        f.write(snappools)


def deploy_quoter():
    """
    Deploy quoter contract to existing pool snapshot
    """
    factory = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
    weth = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    with open("./abis/QuoterV2.bin") as f:
        bits = bytes.fromhex(f.read())

    evm = evm_from_pool_snapshot()
    deployer = create_account(evm)

    qouter = uniswap_quoter(evm, bits)
    addy = qouter.deploy(factory, weth, caller=deployer)
    print(addy)

    print(" ... saving state ...")
    snap = evm.create_snapshot()
    with open(f"{QUOTER_STATE}", "w") as f:
        f.write(snap)
