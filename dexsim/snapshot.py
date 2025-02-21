import os
from pathlib import Path
from simular import PyEvm, create_account

from dexsim.abis import (
    uniswap_factory_contract,
    uniswap_nftpositionmanager,
    uniswap_router_contract,
)
from dexsim.pool import FEE_RANGE

PACKAGEDIR = Path(__file__).parent.absolute()
BASE_STATE = PACKAGEDIR.joinpath("base.json")


def load_evm_from_snapshot(path_fn: str = BASE_STATE) -> PyEvm:
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
