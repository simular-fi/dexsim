from dexsim.abis import (
    uniswap_factory_contract,
    uniswap_router_contract,
    uniswap_nftpositionmanager,
)


def test_base_snapshot(snapshot_evm):
    # check factory state
    factory = uniswap_factory_contract(snapshot_evm)
    assert 1 == factory.feeAmountTickSpacing.call(100)
    assert 10 == factory.feeAmountTickSpacing.call(500)
    assert 60 == factory.feeAmountTickSpacing.call(3000)
    assert 200 == factory.feeAmountTickSpacing.call(10_000)

    # check router
    router = uniswap_router_contract(snapshot_evm)
    assert factory.address.lower() == router.factory.call()

    # check position manager
    nft = uniswap_nftpositionmanager(snapshot_evm)
    assert factory.address.lower() == nft.factory.call()
