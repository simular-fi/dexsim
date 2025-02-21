# DEXSim

An API to to create and interact with a Uniswap v3 based decentralized exchange.
Configure and deploy a number of token pools for trading and experimentation.


## Install
*Not current available on PyPi.  You can install with pip via Github:*

```console
> pip install git+https://github.com/davebryson/dexsim.git#egg=dexsim
```

## Quick Start

### Configuration
You can setup all pools and any other additional information in a YAML. This file is passed as a parameter to the `DEX` constructor.

**Format:**
File: *config.yaml*
```yaml
# required
simulator:
  # Do not change. Only valid Uniswap v3 fee range
  fees:
    - 0.01
    - 0.05
    - 0.30
    - 1.0

# required. you can configure 1 or more pools here using the following structure
  pools:
    eth_usdc: # name of the pool and used for lookup
      tokens: # token name used by the pool
        0: "usdc"
        1: "eth"
     #fee (this example uses interpolation to get the fee from 'fees' above)
      fee: ${simulator.fees[2]}
      # starting price.  May need 2 of these in some cases
      price: 3000.00
    dia_usdc:
      tokens:
        0: "dia"
        1: "usdc"
      fee: ${simulator.fees[0]}
      price: 1.0

# everything below is optional and you can add what you want.  But this is the 
# recommended way to configure your model/simulation
  model:
    steps: 500

  agents:
    lp:
      num: 10
      fund:
        dia: 10_000
        usdc: 10_000
      initial_position:
        dia: 1000
        usdc: 1000
        range: [[0.98, 1.0], [0.99, 1.1]]
      liquidity_range: [500, 100]

```

### Creating a DEX

Using the example configuration file above, here's how to create a DEX:
```python
dex = DEX('./config.yaml')
```

**Interact with a pool**
```python
# create a wallet for Bob
bob = dex.create_one_or_more_addresses()

# mint 9000 USDC and 3 WETH for bob
dex.pools.eth_usdc_pool.mint_tokens(9000, 3, bob)
```

