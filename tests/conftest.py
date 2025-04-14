import pytest
from pathlib import Path

from simular import create_account
from dexsim.snapshot import evm_from_pool_snapshot

PACKAGEDIR = Path(__file__).parent.absolute()
TEST_CONFIG_FILE = PACKAGEDIR.joinpath("testconfig.yaml")

"""
Fixtures
"""


@pytest.fixture
def config_filename():
    return str(TEST_CONFIG_FILE)


@pytest.fixture
def evm():
    return evm_from_pool_snapshot()
