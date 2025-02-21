import pytest
from pathlib import Path

from simular import create_account
from dexsim.snapshot import load_evm_from_snapshot

PACKAGEDIR = Path(__file__).parent.absolute()
TEST_CONFIG_FILE = PACKAGEDIR.joinpath("testconfig.yaml")

"""
Fixtures
"""


@pytest.fixture
def config_filename():
    return str(TEST_CONFIG_FILE)


@pytest.fixture
def snapshot_evm():
    return load_evm_from_snapshot()


@pytest.fixture
def deployer(snapshot_evm):
    return create_account(snapshot_evm, value=int(1000e18))
