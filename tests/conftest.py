import time
from helpers.time import days
from brownie import (
    StrategyConvexStakingCitadel,
    TheVault,
    interface,
    accounts,
)
from _setup.config import (
    WANT, 
    WHALE_ADDRESS,
    SWAP,
    WBTC_POSITION,
    NUM_ELEMENTS,
    PID,
    XCITADEL_LOCKER,
    CITADEL_GOVERNANCE,
    CITADEL_TREASURY,
    PERFORMANCE_FEE_GOVERNANCE,
    PERFORMANCE_FEE_STRATEGIST,
    WITHDRAWAL_FEE,
    MANAGEMENT_FEE,
)
from helpers.constants import MaxUint256
from rich.console import Console

console = Console()

from dotmap import DotMap
import pytest


## Accounts ##
@pytest.fixture
def deployer():
    return accounts[0]

@pytest.fixture
def user():
    return accounts[9]

@pytest.fixture
def citadelTreasury():
    return accounts.at(CITADEL_TREASURY, force=True)

## Fund the account
@pytest.fixture
def want(deployer):
    """
        TODO: Customize this so you have the token you need for the strat
    """
    token = interface.IERC20Detailed(WANT)
    WHALE = accounts.at(WHALE_ADDRESS, force=True) ## Address with tons of token

    token.transfer(deployer, token.balanceOf(WHALE)/8, {"from": WHALE}) # Only transfer a portion
    return token

@pytest.fixture
def strategist():
    return accounts[1]


@pytest.fixture
def keeper():
    return accounts[2]


@pytest.fixture
def guardian():
    return accounts[3]


@pytest.fixture
def governance():
    return accounts.at(CITADEL_GOVERNANCE, force=True)

@pytest.fixture
def treasury():
    return accounts[5]


@pytest.fixture
def proxyAdmin():
    return accounts[6]


@pytest.fixture
def randomUser():
    return accounts[7]


@pytest.fixture
def badgerTree():
    return accounts[8]


@pytest.fixture
def xCitadelLocker():
    return interface.IStakedCitadelLocker(XCITADEL_LOCKER)



@pytest.fixture
def deployed(
    want,
    deployer,
    strategist,
    keeper,
    guardian,
    governance,
    proxyAdmin,
    randomUser, 
    badgerTree,
    citadelTreasury,
    xCitadelLocker,
):
    """
    Deploys, vault and test strategy, mock token and wires them up.
    """
    want = want


    vault = TheVault.deploy({"from": deployer})
    vault.initialize(
        want,
        governance,
        keeper,
        guardian,
        governance,
        strategist,
        badgerTree,
        "",
        "",
        [
            PERFORMANCE_FEE_GOVERNANCE,
            PERFORMANCE_FEE_STRATEGIST,
            WITHDRAWAL_FEE,
            MANAGEMENT_FEE,
        ],
    )
    vault.setStrategist(deployer, {"from": governance})
    # NOTE: TheVault starts unpaused

    strategy = StrategyConvexStakingCitadel.deploy({"from": deployer})
    strategy.initialize(
        vault,
        want,
        citadelTreasury.address,
        xCitadelLocker.address,
        PID,
        [
            SWAP,
            WBTC_POSITION,
            NUM_ELEMENTS
        ]
    )
    # NOTE: Strategy starts unpaused

    vault.setStrategy(strategy, {"from": governance})

    # Approve strategy as reward distributor on Locker
    xCitadelLocker.approveRewardDistributor(
        strategy.wbtc(),
        strategy.address,
        True,
        {"from": governance}
    )

    ## Reset rewards if they are set to expire within the next 4 days or are expired already
    rewardsPool = interface.IBaseRewardsPool(strategy.baseRewardsPool())
    if rewardsPool.periodFinish() - int(time.time()) < days(4):
        booster = interface.IBooster(strategy.booster())
        booster.earmarkRewards(PID, {"from": deployer})
        console.print("[green]BaseRewardsPool expired or expiring soon - it was reset![/green]")

    return DotMap(
        deployer=deployer,
        vault=vault,
        strategy=strategy,
        want=want,
        governance=governance,
        proxyAdmin=proxyAdmin,
        randomUser=randomUser,
        performanceFeeGovernance=PERFORMANCE_FEE_GOVERNANCE,
        performanceFeeStrategist=PERFORMANCE_FEE_STRATEGIST,
        withdrawalFee=WITHDRAWAL_FEE,
        managementFee=MANAGEMENT_FEE,
        badgerTree=badgerTree,
        citadelTreasury=citadelTreasury,
        xCitadelLocker=xCitadelLocker
    )


## Contracts ##
@pytest.fixture
def vault(deployed):
    return deployed.vault


@pytest.fixture
def strategy(deployed):
    return deployed.strategy


@pytest.fixture
def wbtc(deployed):
    return interface.IERC20Detailed(deployed.strategy.wbtc())


@pytest.fixture
def tokens(deployed):
    return [deployed.want]

### Fees ###
@pytest.fixture
def performanceFeeGovernance(deployed):
    return deployed.performanceFeeGovernance


@pytest.fixture
def performanceFeeStrategist(deployed):
    return deployed.performanceFeeStrategist


@pytest.fixture
def withdrawalFee(deployed):
    return deployed.withdrawalFee


@pytest.fixture
def setup_share_math(deployer, vault, want, governance):

    depositAmount = int(want.balanceOf(deployer) * 0.5)
    assert depositAmount > 0
    want.approve(vault.address, MaxUint256, {"from": deployer})
    vault.deposit(depositAmount, {"from": deployer})

    vault.earn({"from": governance})

    return DotMap(depositAmount=depositAmount)


## Forces reset before each test
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass
