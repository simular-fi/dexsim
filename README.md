# DEXSim

An API to create and interact with a local version of Uniswap v3.  This library
use a pre-deployed version of Uniswap v3 along with a set of pre-deployed pools. It's intended for use in agent-based modeling or other simulation environments. It's also a useful tool in learning about how Uniswap works.

Under the covers, `dexsim` is built on [Simular](https://simular.readthedocs.io/en/latest/) that uses a production-grade EVM. Uniswap v3 is deployed from a snapshot from the main Ethereun chain. However, it does not include any state other than currently supported pools.

The pools are only deployed, not initialized with an starting price. You can set the starting price via the configuration file described below. 

## Install
```console
> pip install dexsim
```

## Getting started

The following pools can be configured and used:
| pool | fee | pool name | 
|------|-----|-----------|
| **usdc/dai** | 100 (0.01) | usdc_dai_100 | 
| **usdc/dai** | 500 (0.05) | usdc_dai_500 | 
| **usdc/weth** | 500 (0.05) | usdc_weth_500 | 
| **dai/weth** | 500 (0.05) | dai_weth_500 |
| **wbtc/weth** | 500 (0.05) | wbtc_weth_500 |
| **wbtc/dai** | 500 (0.05) | wbtc_dai_500 |
| **wbtc/usdc** | 500 (0.05) | wbtc_usdc_500

The pools must be initialized with a starting price via the YAML configuration file. You only need to configure the pools you intend to use.  Here's an example of the file format:

Example config file: `example.yaml`
```yaml
simulator:
  pools:
    usdc_dai_100: [1, 1]
    usdc_weth_500: [5000, 1]
```
This configures 2 pools with there exchange prices: 
* `usdc_dai_100` = 1 usdc for 1 dai
* `usdc_weth_500` = 5000 usdc for 1 weth.

Here's an example of creating and using the pools:

```python
from dexsim import DEX

# Create the Unswap DEX based on the configuration file
dex = DEX('./example.yaml')
assert 2 == dex.total_number_of_pools()
assert (5000, 0.0002) == dex.pools.usdc_weth_500.exchange_rates()

# create a wallet for Bob
bob = dex.create_wallet()

# mint some ERC20 tokens for bob
dex.pools.usdc_weth_500.mint_tokens(10000, 2, bob)

# mint a liquidity position for bob in the price range of $4900 - $5100 by 
# providing 10_000 usdc and 2 weth.  
# Note the prices are specified in terms of the y token (weth)
_, _, _, nft_id = dex.pools.usdc_weth_500.mint_liquidity_position(
        10000, 2, 1 / 4900, 1 / 5100, bob
    )
```

See `tests/` for several examples of use.

