from dexsim import DEX


def test_minting_balances(config_filename):
    dex = DEX(config_filename)

    acct = dex.create_wallet()
    dex.lending.usdc_weth_500.mint_collateral_token(3, acct)
    r = dex.lending.usdc_weth_500.collateral_token_balance(acct)
    assert r == 3.0

    dex.lending.usdc_weth_500.mint_lending_token(1, acct)
    r1 = dex.lending.usdc_weth_500.lending_token_balance(acct)
    assert r1 == 1.0


def test_supply_collateral(config_filename):
    dex = DEX(config_filename)

    agent = dex.create_wallet()

    # mint some collateral tokens for the user
    dex.lending.usdc_weth_500.mint_collateral_token(3, agent)
    # check the erc20 balance
    r = dex.lending.usdc_weth_500.collateral_token_balance(agent)
    assert r == 3.0

    # provide collateral to the lending contract
    dex.lending.usdc_weth_500.provide_collateral(2, agent)

    # check loan information
    info = dex.lending.usdc_weth_500.loan_information(agent)
    assert info == [2000000000000000000, 0, True]

    # How much weth is required to borrow 5000 usdc?
    c = dex.lending.usdc_weth_500.collateral_required(5000)
    assert c == 1.25

    # does the agent have an active loan?
    a1 = dex.lending.usdc_weth_500.is_active_loan(agent)
    assert a1 == False

    # we haven't supplied any lending token to the loan contract
    assert 0 == dex.lending.usdc_weth_500.available_to_loan()
