# DEXSim

An API to create and interact with a local version of Uniswap v3. Configure and deploy a number of token pools for trading and experimentation.

Built on [Simular](https://simular.readthedocs.io/en/latest/)


## Install
```console
> pip install dexsim
```

## Quick Start

### Configuration
You can setup pools and any other additional information in a YAML file. This file is passed as a parameter to the `DEX` constructor.

**Example:**
File: *config.yaml*
```yaml
simulator:
  pools:
    eth_usdc:
      tokens:
        0: "usdc"
        1: "eth"
      fee: 0.30
      price: 3000.00
    dia_usdc:
      tokens:
        0: "dia"
        1: "usdc"
      fee: 0.05
      price: 1.0
```

### Create an interact with a Uniswap DEX

```python
from dexsim.dex import DEX

# Create the Unswap DEX based on the configuration file
dex = DEX('./config.yaml')

assert 2 == dex.total_number_of_pools()

# create a wallet for Bob
bob = dex.create_wallet()

# mint 9000 USDC and 3 WETH for bob
dex.pools.eth_usdc_pool.mint_tokens(9000, 3, bob)

# Add some liquidity to the pool and get the NFT position token id
 _, _, tokenid =  dex.pools.eth_usdc_pool.mint_liquidity_position(3000, 1, 2900, 3100, bob)

```

See `tests/` for several examples of use.

