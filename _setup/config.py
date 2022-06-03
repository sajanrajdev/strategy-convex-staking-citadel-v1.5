## Token deposited in the vault
WANT = "0x137469B55D1f15651BA46A89D0588e97dD0B6562" # Using BADGER/wBTC CRV Lp for testing

## Curve parameters
SWAP = "0x50f3752289e1456BfA505afd37B241bca23e685d"
WBTC_POSITION = 1
NUM_ELEMENTS = 2

## Convex parameters
PID = 74

## Citadel parameters
CITADEL_GOVERNANCE = "0xA967Ba66Fb284EC18bbe59f65bcf42dD11BA8128"
CITADEL_TREASURY = "0x38724146C8dc1Aa49c3395091cf86B789c37F52c"
XCITADEL_LOCKER = "0xB1c38253aD6Ab3e2A2D53A094692fcf1321b12d4" # Test locker

## Account that has a lot of want (we will "borrow it" for testing)
WHALE_ADDRESS = "0x02246583870b36Be0fEf2819E1d3A771d6C07546" # Curve Gauge

## Address for Badger Registry, used to fill in default addresses
## See: https://github.com/Badger-Finance/badger-registry
REGISTRY = "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f"

PERFORMANCE_FEE_GOVERNANCE = 1_500 ## 15%
PERFORMANCE_FEE_STRATEGIST = 0 ## 0%
WITHDRAWAL_FEE = 0 ## 0%
MANAGEMENT_FEE = 0 ## 0%

