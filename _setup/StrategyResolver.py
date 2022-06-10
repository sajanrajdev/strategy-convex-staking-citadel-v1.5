from helpers.StrategyCoreResolver import StrategyCoreResolver
from rich.console import Console
from brownie import interface

console = Console()


class StrategyResolver(StrategyCoreResolver):
    def get_strategy_destinations(self):
        """
        Track balances for all strategy implementations
        (Strategy Must Implement)
        """
        strategy = self.manager.strategy
        return {}

    def hook_after_confirm_withdraw(self, before, after, params):
        """
        Specifies extra check for ordinary operation on withdrawal
        Use this to verify that balances in the get_strategy_destinations are properly set
        """
        assert True

    def hook_after_confirm_deposit(self, before, after, params):
        """
        Specifies extra check for ordinary operation on deposit
        Use this to verify that balances in the get_strategy_destinations are properly set
        """
        assert True  ## Done in earn

    def hook_after_earn(self, before, after, params):
        """
        Specifies extra check for ordinary operation on earn
        Use this to verify that balances in the get_strategy_destinations are properly set
        """
        assert True

    def confirm_harvest(self, before, after, tx):
        """
        Verfies that the Harvest produced yield and fees
        NOTE: This overrides default check, use only if you know what you're doing
        """
        console.print("=== Compare Harvest ===")
        self.manager.printCompare(before, after)
        self.confirm_harvest_state(before, after, tx)

        strategy = self.manager.strategy
        autocompoundBps = strategy.autocompoundBps()
        emitBps = strategy.emitBps()
        treasuryBps = strategy.treasuryBps()

        if autocompoundBps > 0:
            # Check that we autocompounded
            assert after.get("sett.getPricePerFullShare") > before.get(
                "sett.getPricePerFullShare"
            )
            # Check that we re-deposit tokens
            assert after.balances("convexLpToken", "baseRewardsPool") > before.balances(
                "convexLpToken", "baseRewardsPool"
            )
            # Check event
            event = tx.events["Harvested"][0]
            assert event["token"] == strategy.want()
            assert event["amount"] > 0

        else:
            # Check that we autocompounded
            assert after.get("sett.getPricePerFullShare") == before.get(
                "sett.getPricePerFullShare"
            )
            # Check that we re-deposit tokens
            assert after.balances("convexLpToken", "baseRewardsPool") == before.balances(
                "convexLpToken", "baseRewardsPool"
            )
            event = tx.events["Harvested"][0]
            assert event["token"] == strategy.want()
            assert event["amount"] == 0
        
        if emitBps > 0:
            # Check that wBTC was distributed to Locker
            assert after.balances("wbtc", "xCitadelLocker") > before.balances(
                "wbtc", "xCitadelLocker"
            )
            # Check events
            event = tx.events["RewardAdded"][0]
            assert event["account"] == strategy.address
            assert event["_token"] == strategy.wbtc()
            assert event["_reward"] > 0
            assert event["_dataTypeHash"] == "0xaf388c3c3157dbb1999fecd2348a129dd286852ceddb9352feabbffbac7ca99b"

            event = tx.events["TokenDistribution"][0]
            assert event["token"] == strategy.wbtc()
            assert event["destination"] == strategy.xCitadelLocker()
            assert event["amount"] > 0

        if treasuryBps > 0:
            # Check that wBTC was distributed to Citadel's treasury
            assert after.balances("wbtc", "citadelTreasury") > before.balances(
                "wbtc", "citadelTreasury"
            )

            # Check event
            if emitBps > 0:
                event = tx.events["TokenDistribution"][1]
            else:
                event = tx.events["TokenDistribution"][0]
            assert event["token"] == strategy.wbtc()
            assert event["destination"] == strategy.citadelTreasury()
            assert event["amount"] > 0

        # Ensure that fees are processed
        assert after.balances("wbtc", "treasury") > before.balances(
            "wbtc", "treasury"
        )

        assert True

    def confirm_tend(self, before, after, tx):
        """
        Tend Should;
        - Increase the number of staked tended tokens in the strategy-specific mechanism
        - Reduce the number of tended tokens in the Strategy to zero

        (Strategy Must Implement)
        """
        assert True

    def add_entity_balances_for_tokens(self, calls, tokenKey, token, entities):
        entities["strategy"] = self.manager.strategy.address
        entities["baseRewardsPool"] = self.manager.strategy.baseRewardsPool()
        entities["xCitadelLocker"] = self.manager.strategy.xCitadelLocker()
        entities["citadelTreasury"] = self.manager.strategy.citadelTreasury()

        super().add_entity_balances_for_tokens(calls, tokenKey, token, entities)
        return calls

    def add_balances_snap(self, calls, entities):
        super().add_balances_snap(calls, entities)
        strategy = self.manager.strategy

        crv = interface.IERC20(strategy.crv())
        cvx = interface.IERC20(strategy.cvx())
        wbtc = interface.IERC20(strategy.wbtc())
        ctdl = interface.IERC20(strategy.ctdl())

        ## Get the booster for this strat
        booster = interface.IBooster(strategy.booster())
        ## So we can get the lpToken associated
        convexLpToken = interface.IERC20(booster.poolInfo(strategy.pid())["token"])

        calls = self.add_entity_balances_for_tokens(
            calls, "convexLpToken", convexLpToken, entities
        )
        calls = self.add_entity_balances_for_tokens(calls, "crv", crv, entities)
        calls = self.add_entity_balances_for_tokens(calls, "cvx", cvx, entities)
        calls = self.add_entity_balances_for_tokens(calls, "wbtc", wbtc, entities)
        calls = self.add_entity_balances_for_tokens(calls, "ctdl", ctdl, entities)

        return calls
