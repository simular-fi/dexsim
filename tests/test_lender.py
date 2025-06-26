import pytest

from dexsim import DEX


# borrow USDC with Weth collat
BORROW_AMOUNT = 10_000
WETH_REQUIRED = 2.5


def _take_loan_helper(dex, agent):
    """
    Take loan helper
    """
    assert 0 == dex.lending.usdc_weth_500.collateral_token_balance(agent)

    weth_needed = dex.lending.usdc_weth_500.collateral_required(BORROW_AMOUNT)
    assert WETH_REQUIRED == weth_needed

    # mint weth for the user
    dex.lending.usdc_weth_500.mint_collateral_token(weth_needed, agent)
    assert WETH_REQUIRED == dex.lending.usdc_weth_500.collateral_token_balance(agent)

    # supply the weth collateral for the loan
    dex.lending.usdc_weth_500.provide_collateral(weth_needed, agent)

    # take loan
    dex.lending.usdc_weth_500.borrow(BORROW_AMOUNT, agent)

    # check loan information
    assert [
        2500000000000000000,
        10000000000000000000000,
        True,
    ] == dex.lending.usdc_weth_500.loan_information(agent)

    # check we got the loan
    assert 10_000 == dex.lending.usdc_weth_500.lending_token_balance(agent)


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


def test_initial_lending_supply(config_filename):
    dex = DEX(config_filename)
    assert 1000000000.0 == dex.lending.usdc_weth_500.available_to_loan()


def test_borrow(config_filename):
    """
    given borrow price
    - how much is needed?
    - user's mints amount
    - supply collateral
    - take loan
    - check loan status

    collateral is WETH, borrowing USDC
    """
    dex = DEX(config_filename)
    agent = dex.create_wallet()

    assert 0 == dex.lending.usdc_weth_500.collateral_token_balance(agent)

    weth_needed = dex.lending.usdc_weth_500.collateral_required(BORROW_AMOUNT)
    assert WETH_REQUIRED == weth_needed

    # mint weth for the user
    dex.lending.usdc_weth_500.mint_collateral_token(weth_needed, agent)
    assert WETH_REQUIRED == dex.lending.usdc_weth_500.collateral_token_balance(agent)

    # supply the weth collateral for the loan
    dex.lending.usdc_weth_500.provide_collateral(weth_needed, agent)

    # take loan
    dex.lending.usdc_weth_500.borrow(BORROW_AMOUNT, agent)

    # check loan information
    assert [
        2500000000000000000,
        10000000000000000000000,
        True,
    ] == dex.lending.usdc_weth_500.loan_information(agent)

    # check we got the loan
    assert BORROW_AMOUNT == dex.lending.usdc_weth_500.lending_token_balance(agent)

    # is the loan healthy?
    assert dex.lending.usdc_weth_500.is_loan_healthy(agent)


def test_payback_loan(config_filename):
    """
    - pay back
    """
    dex = DEX(config_filename)
    agent = dex.create_wallet()
    _take_loan_helper(dex, agent)

    assert 0 == dex.lending.usdc_weth_500.collateral_token_balance(agent)

    # repay the loan
    dex.lending.usdc_weth_500.repay_loan(BORROW_AMOUNT, agent)
    assert [
        0,
        0,
        True,
    ] == dex.lending.usdc_weth_500.loan_information(agent)

    # got collateral back
    assert 2.5 == dex.lending.usdc_weth_500.collateral_token_balance(agent)


def test_withdraw_collateral_with_no_loan(config_filename):
    """
    - mint weth for user
    - add collateral
    - withdraw collateral
    you can withdraw when you don't have an outstanding loan balance
    """
    dex = DEX(config_filename)
    agent = dex.create_wallet()

    # mint for the agent
    dex.lending.usdc_weth_500.mint_collateral_token(WETH_REQUIRED, agent)
    assert WETH_REQUIRED == dex.lending.usdc_weth_500.collateral_token_balance(agent)

    # supply collateral
    dex.lending.usdc_weth_500.provide_collateral(WETH_REQUIRED, agent)
    # erc20 balance = 0 all funds transfered to loan contract
    assert 0 == dex.lending.usdc_weth_500.collateral_token_balance(agent)

    # check the loan is NOT active (haven't borrowed)
    assert False == dex.lending.usdc_weth_500.is_active_loan(agent)

    # check loan information
    assert [
        2500000000000000000,
        0,
        True,
    ] == dex.lending.usdc_weth_500.loan_information(agent)

    # withdraw
    dex.lending.usdc_weth_500.withdraw_collateral(agent)

    # check erc20 balance
    # collateral xfered back to erc20 account
    assert WETH_REQUIRED == dex.lending.usdc_weth_500.collateral_token_balance(agent)

    # check loan information
    assert [
        0,
        0,
        True,
    ] == dex.lending.usdc_weth_500.loan_information(agent)


def test_error_withdraw_collateral_with_loan(config_filename):
    """
    - take loan
    - try to withdraw without paying back loan
    """
    dex = DEX(config_filename)
    agent = dex.create_wallet()
    _take_loan_helper(dex, agent)

    # reverts
    with pytest.raises(RuntimeError):
        dex.lending.usdc_weth_500.withdraw_collateral(agent)

    # loan information is still there...
    assert [
        2500000000000000000,
        10000000000000000000000,
        True,
    ] == dex.lending.usdc_weth_500.loan_information(agent)


def test_error_borrow_with_existing_loan(config_filename):
    """
    - take loan
    - mint more to erc20
    - add more collateral
    - try to take another loan (reverts)
    """
    dex = DEX(config_filename)
    agent = dex.create_wallet()

    _take_loan_helper(dex, agent)

    borrower_more_amount = 5000
    collateral_required = dex.lending.usdc_weth_500.collateral_required(
        borrower_more_amount
    )

    dex.lending.usdc_weth_500.mint_collateral_token(collateral_required, agent)

    # supply collateral
    dex.lending.usdc_weth_500.provide_collateral(collateral_required, agent)

    # try to take another loan (reverts)
    with pytest.raises(RuntimeError):
        dex.lending.usdc_weth_500.borrow(borrower_more_amount, agent)


def test_error_cant_liquidate_healthy_loan(config_filename):
    """
    - take loan
    - mint lending token to liquidator
    - try to liquidate healthy loan (revert)
    """
    dex = DEX(config_filename)
    agent = dex.create_wallet()
    liquidator = dex.create_wallet()

    _take_loan_helper(dex, agent)

    # mint erc20 to liquidator
    dex.lending.usdc_weth_500.mint_lending_token(WETH_REQUIRED, liquidator)

    # loan is healthy - reverts
    with pytest.raises(RuntimeError):
        dex.lending.usdc_weth_500.liquidate_loan(agent, liquidator)


def test_liquidate_loan(config_filename):
    """
    need liquidator agent
    - mint weth to liquidator
    - change collateral price to make loan unhealthy
    - liquidate
    """
    dex = DEX(config_filename)
    agent = dex.create_wallet()
    liquidator = dex.create_wallet()

    _take_loan_helper(dex, agent)

    # change price to make borrower under-collateralized
    new_price = 6000
    dex.lending.usdc_weth_500.set_price_for_testing(new_price)

    # calculate how much the liquidator needs
    new_amount_weth_needed = dex.lending.usdc_weth_500.collateral_required(
        BORROW_AMOUNT
    )

    # mint erc20 tokens to the liquidator
    dex.lending.usdc_weth_500.mint_lending_token(new_amount_weth_needed, liquidator)

    # liquidate!
    dex.lending.usdc_weth_500.liquidate_loan(agent, liquidator)

    # Check loan is cleared!
    assert [
        0,
        0,
        True,
    ] == dex.lending.usdc_weth_500.loan_information(agent)

    # Check liqudator's balance - they bought out the collateral
    assert BORROW_AMOUNT == dex.lending.usdc_weth_500.lending_token_balance(agent)
