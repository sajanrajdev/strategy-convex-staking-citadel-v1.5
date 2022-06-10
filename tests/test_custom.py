import brownie
from brownie import interface, chain, accounts
from helpers.constants import MaxUint256
import time
from helpers.time import days
from rich.console import Console
from _setup.config import PID
from helpers.SnapshotManager import SnapshotManager

console = Console()

def state_setup(deployer, vault, strategy, want, keeper):
    startingBalance = want.balanceOf(deployer)

    startingBalance = want.balanceOf(deployer)
    depositAmount = int(startingBalance * 0.8)
    assert depositAmount != 0

    want.approve(vault, MaxUint256, {"from": deployer})
    vault.deposit(depositAmount, {"from": deployer})

    chain.sleep(days(1))
    chain.mine()

    vault.earn({"from": keeper})

    chain.sleep(days(3))
    chain.mine()

    ## Reset rewards if they are set to expire within the next 4 days or are expired already
    rewardsPool = interface.IBaseRewardsPool(strategy.baseRewardsPool())
    if rewardsPool.periodFinish() - int(time.time()) < days(4):
        booster = interface.IBooster(strategy.booster())
        booster.earmarkRewards(PID, {"from": deployer})
        console.print("[green]BaseRewardsPool expired or expiring soon - it was reset![/green]")

    chain.sleep(days(1))
    chain.mine()

def test_expected_CVX_rewards_match_minted(deployer, vault, strategy, want, keeper):
    state_setup(deployer, vault, strategy, want, keeper)

    (crv, cvx) = strategy.balanceOfRewards()
    # Check that rewards are accrued
    crv_amount = crv[1]
    cvx_amount = cvx[1]
    assert crv_amount > 0
    assert cvx_amount > 0

    # Check that CVX amount calculating function matches the result
    assert cvx_amount == strategy.getMintableCVXRewards(crv_amount)

    # First Transfer event from harvest() function is emitted by cvx._mint()
    tx = strategy.harvest({"from": keeper})
    assert tx.events["Transfer"][0]["value"] == cvx_amount


def test_different_distribution_split_results(deployer, vault, strategy, want, keeper, governance):
    state_setup(deployer, vault, strategy, want, keeper)

    snap = SnapshotManager(vault, strategy, "StrategySnapshot")

    # Attempt to change ratio to more or less than expected
    with brownie.reverts("Invalid Total Ratio"):
        strategy.setRewardsManagementRatio(9000, 1000, 1000, {"from": governance}) # Add to 11000

    with brownie.reverts("Invalid Total Ratio"):
        strategy.setRewardsManagementRatio(0, 0, 1000, {"from": governance}) # Add to 1000

    # Attempt set emitBPS to higher than allowed (20%)
    with brownie.reverts("Invalid Emit BPS"):
        strategy.setRewardsManagementRatio(5000, 3000, 2000, {"from": governance})

    # Test different distribution cases
    # NOTE: The resolver holds the appropiate checks per case upon harvest.
    splits = [
        [10000, 0, 0],
        [0, 0, 10000],
        [7000, 2000, 1000],
        [0, 2000, 8000]
    ]

    chain.snapshot()
    for split in splits:
        strategy.setRewardsManagementRatio(
            split[0],
            split[1],
            split[2],
            {"from": governance}
        )
        snap.settHarvest({"from": keeper})
        chain.revert()


