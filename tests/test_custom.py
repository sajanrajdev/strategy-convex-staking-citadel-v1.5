import brownie
from brownie import interface, chain, accounts
from helpers.constants import MaxUint256
import time
from helpers.time import days
from rich.console import Console
from _setup.config import PID

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

    # First transfer from Harvest function is emitted by cvx._mint()
    tx = strategy.harvest({"from": keeper})
    assert tx.events["Transfer"][0]["value"] == cvx_amount