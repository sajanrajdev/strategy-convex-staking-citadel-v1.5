// SPDX-License-Identifier: MIT

pragma solidity ^0.6.11;
pragma experimental ABIEncoderV2;

import {IERC20Upgradeable} from "@openzeppelin-contracts-upgradeable/token/ERC20/IERC20Upgradeable.sol";
import {SafeMathUpgradeable} from "@openzeppelin-contracts-upgradeable/math/SafeMathUpgradeable.sol";
import {MathUpgradeable} from "@openzeppelin-contracts-upgradeable/math/MathUpgradeable.sol";
import {AddressUpgradeable} from "@openzeppelin-contracts-upgradeable/utils/AddressUpgradeable.sol";
import {SafeERC20Upgradeable} from "@openzeppelin-contracts-upgradeable/token/ERC20/SafeERC20Upgradeable.sol";

import "interfaces/convex/IBooster.sol";
import "interfaces/convex/IBaseRewardsPool.sol";
import "interfaces/convex/IConvexToken.sol";

import "deps/libraries/CurveSwapper.sol";
import "deps/libraries/UniswapSwapper.sol";
import "deps/libraries/TokenSwapPathRegistry.sol";

import {BaseStrategy} from "@badger-finance/BaseStrategy.sol";
import {IVault} from "interfaces/badger/IVault.sol";
import {IStakedCitadelLocker} from "interfaces/citadel/IStakedCitadelLocker.sol";

contract StrategyConvexStakingCitadel is
    BaseStrategy,
    CurveSwapper,
    UniswapSwapper,
    TokenSwapPathRegistry
{
    using SafeERC20Upgradeable for IERC20Upgradeable;
    using AddressUpgradeable for address;
    using SafeMathUpgradeable for uint256;

    // ===== Token Registry ===== // 
    IERC20Upgradeable public constant wbtc =
        IERC20Upgradeable(0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599);
    IERC20Upgradeable public constant ctdl =
        IERC20Upgradeable(0xaF0b1FDf9c6BfeC7b3512F207553c0BA00D7f1A2); // Using testCTDL for now
    IERC20Upgradeable public constant weth =
        IERC20Upgradeable(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);
    IERC20Upgradeable public constant crv =
        IERC20Upgradeable(0xD533a949740bb3306d119CC777fa900bA034cd52);
    IERC20Upgradeable public constant cvx =
        IERC20Upgradeable(0x4e3FBD56CD56c3e72c1403e103b45Db9da5B9D2B);
    IERC20Upgradeable public constant cvxCrv =
        IERC20Upgradeable(0x62B9c7356A2Dc64a1969e19C23e4f579F9810Aa7);

    // ===== Convex Registry ===== //
    IBooster public constant booster =
        IBooster(0xF403C135812408BFbE8713b5A23a04b3D48AAE31);
    IBaseRewardsPool public baseRewardsPool;
    IConvexToken public constant cvx_minter = 
        IConvexToken(0x4e3FBD56CD56c3e72c1403e103b45Db9da5B9D2B);
     uint256 public pid;

    // ======== Constants ======== //
    uint256 public constant MAX_EMIT_BPS = 2_000;
    uint256 public constant MAX_UINT_256 = uint256(-1);

    // ==== Manager Settings ==== //
    uint256 public autocompoundBps; // Initial: 90% - Sell for more want and re-stake
    uint256 public emitBps; // Initial: 10% - Sell for wBTC and send to CTDL locker
    uint256 public treasuryBps; // Initial: 0% - Send to CTDL treasury
    uint256 public stableSwapSlippageTolerance; // Initial: 95%
    address public citadelTreasury; // Where treasury rewards will be directed
    IStakedCitadelLocker public xCitadelLocker; // Where locking rewards will be distributed

    // ===== Curve Settings ===== //
    struct CurvePoolConfig {
        address swap;
        uint256 wbtcPosition;
        uint256 numElements;
    }
    CurvePoolConfig public curvePool;

    /// @dev Initialize the Strategy with security settings as well as tokens
    /// @notice Proxies will set any non constant variable you declare as default value
    /// @dev add any extra changeable variable at end of initializer as shown
    function initialize(
        address _vault,
        address _want,
        address _citadelTreasury,
        address _xCitadelLocker,
        uint256 _pid,
        CurvePoolConfig memory _curvePool
    ) public initializer {
        __BaseStrategy_init(_vault);
        want = _want;
        citadelTreasury = _citadelTreasury;
        xCitadelLocker = IStakedCitadelLocker(_xCitadelLocker);

        pid = _pid; // Core staking pool ID
        IBooster.PoolInfo memory poolInfo = booster.poolInfo(pid);
        baseRewardsPool = IBaseRewardsPool(poolInfo.crvRewards);

        curvePool = CurvePoolConfig(_curvePool.swap, _curvePool.wbtcPosition, _curvePool.numElements);

        // Set inital rewards management ratio (treasuryBps = 0)
        autocompoundBps = 9_000;
        emitBps = 1_000;

        // Set default slippage value (95%)
        stableSwapSlippageTolerance = 9_500;

        // Set token swap paths
        address[] memory path = new address[](3);
        path[0] = address(crv);
        path[1] = address(weth);
        path[2] = address(wbtc);
        _setTokenSwapPath(
            address(crv),
            address(wbtc),
            path
        );

        path[0] = address(cvx);
        _setTokenSwapPath(
            address(cvx),
            address(wbtc),
            path
        );

        // Approvals
        crv.safeApprove(sushiswap, MAX_UINT_256);
        cvx.safeApprove(sushiswap, MAX_UINT_256);
        wbtc.safeApprove(_curvePool.swap, MAX_UINT_256);
        wbtc.safeApprove(_xCitadelLocker, MAX_UINT_256);
    }

    // === Permissioned Functions === //
    function setPid(uint256 _pid) external {
        _onlyGovernance();
        pid = _pid; // LP token pool ID
        IBooster.PoolInfo memory poolInfo = booster.poolInfo(pid);
        baseRewardsPool = IBaseRewardsPool(poolInfo.crvRewards);
    }

    function setstableSwapSlippageTolerance(uint256 _sl) external {
        _onlyGovernance();
        stableSwapSlippageTolerance = _sl;
    }

    function setCitadelTreasury(address _citadelTreasury) external {
        _onlyGovernance();
        citadelTreasury = _citadelTreasury;
    }

    function setXCitadelLocker(address _xCitadelLocker) external {
        _onlyGovernance();
        xCitadelLocker = IStakedCitadelLocker(_xCitadelLocker);
    }

    function setRewardsManagementRatio(
        uint256 _autocompoundBps,
        uint256 _emitBps,
        uint256 _treasuryBps
    ) external {
        _onlyGovernance();
        require(
            _autocompoundBps + _emitBps + _treasuryBps <= MAX_BPS,
            "Invalid Total Ratio" 
        );
        require(_emitBps < MAX_EMIT_BPS, "Invalid Emit BPS");
        autocompoundBps = _autocompoundBps;
        emitBps = _emitBps;
        treasuryBps = _treasuryBps;
    }
    
    /// @dev Return the name of the strategy
    function getName() external pure override returns (string memory) {
        return "StrategyConvexStakingCitadel";
    }

    /// @dev Return a list of protected tokens
    /// @notice It's very important all tokens that are meant to be in the strategy to be marked as protected
    /// @notice this provides security guarantees to the depositors they can't be sweeped away
    function getProtectedTokens() public view virtual override returns (address[] memory) {
        address[] memory protectedTokens = new address[](5);
        protectedTokens[0] = want;
        protectedTokens[1] = address(wbtc);
        protectedTokens[2] = address(ctdl);
        protectedTokens[3] = address(crv);
        protectedTokens[4] = address(cvx);
        return protectedTokens;
    }

    /// @dev Deposit `_amount` of want, investing it to earn yield
    function _deposit(uint256 _amount) internal override {
        booster.deposit(pid, _amount, true);
    }

    /// @dev Withdraw all funds, this is used for migrations, most of the time for emergency reasons
    function _withdrawAll() internal override {
        baseRewardsPool.withdrawAndUnwrap(balanceOfPool(), false);
    }

    /// @dev Withdraw `_amount` of want, so that it can be sent to the vault / depositor
    /// @notice just unlock the funds and return the amount you could unlock
    function _withdrawSome(uint256 _amount) internal override returns (uint256) {
        // Get idle want in the strategy
        uint256 _preWant = balanceOfWant();

        // If we lack sufficient idle want, withdraw the difference from the strategy position
        if (_preWant < _amount) {
            uint256 _toWithdraw = _amount.sub(_preWant);
            baseRewardsPool.withdrawAndUnwrap(_toWithdraw, false);
        }

        // Confirm how much want we actually end up with
        uint256 _postWant = balanceOfWant();

        // Return the actual amount withdrawn if less than requested
        return MathUpgradeable.min(_postWant, _amount);
    }


    /// @dev Does this function require `tend` to be called?
    function _isTendable() internal override pure returns (bool) {
        return false; // Change to true if the strategy should be tended
    }

    function _harvest() internal override returns (TokenAmount[] memory harvested) {
        harvested = new TokenAmount[](2);

        uint256 totalWantBefore = balanceOfWant();

        // Harvest rewards
        baseRewardsPool.getReward(address(this), true);
        uint256 crvRewards = crv.balanceOf(address(this));
        uint256 cvxRewards = cvx.balanceOf(address(this));

        // Swap all CRV for wBTC
        if (crvRewards > 0) {
            // TODO: Route swaps through UNIV3 or external swap optimizer
            _swapExactTokensForTokens(
                sushiswap,
                address(crv),
                crvRewards,
                getTokenSwapPath(address(crv), address(wbtc))
            );
        }

        // Swap all CVX for wBTC
        if (cvxRewards > 0) {
            // TODO: Route swaps through UNIV3 or external swap optimizer
            _swapExactTokensForTokens(
                sushiswap,
                address(cvx),
                cvxRewards,
                getTokenSwapPath(address(cvx), address(wbtc))
            );
        }

        // Report total wBTC acquired
        uint256 wbtcBalance = wbtc.balanceOf(address(this));
        harvested[1] = TokenAmount(address(wbtc), wbtcBalance);

        // Take performance fee on total harvested wBTC
        // NOTE:Can't use reportExtraToken() because it transfers the token to the Badger Tree
        uint256 governanceRewardsFee = _calculateFee(
            wbtcBalance,
            IVault(vault).performanceFeeGovernance()
        );
        uint256 strategistRewardsFee = _calculateFee(
            wbtcBalance,
            IVault(vault).performanceFeeStrategist()
        );
        if (governanceRewardsFee != 0) {
            wbtc.safeTransfer(
                IVault(vault).treasury(),
                governanceRewardsFee
            );
        }

        if (strategistRewardsFee != 0) {
            wbtc.safeTransfer(
                IVault(vault).strategist(),
                strategistRewardsFee
            );
        }

        // Get wBTC balance after fees
        wbtcBalance = wbtc.balanceOf(address(this));

        // If autocompound is enabled, autocompound set %
        if (autocompoundBps > 0) {
            uint256 autocompoundAmount = wbtcBalance.mul(autocompoundBps).div(MAX_BPS);
            _add_liquidity_single_coin(
                curvePool.swap, 
                want, 
                address(wbtc),
                autocompoundAmount,
                curvePool.wbtcPosition,
                curvePool.numElements, 
                0
            );
            uint256 totalWantAfter = balanceOfWant();
            // Stake all want sitting in the strat
            booster.deposit(pid, totalWantAfter, true);
            harvested[0] = TokenAmount(want, totalWantAfter.sub(totalWantBefore));
        }

        // If distribute to lockers is enabled, distribute %
        if (emitBps > 0) {
            uint256 emitAmount = wbtcBalance.mul(emitBps).div(MAX_BPS);
            // NOTE: Strategy must be added as a reward distributor on the Locker
            xCitadelLocker.notifyRewardAmount(address(wbtc), emitAmount);
        }

        // If ditribute to Citadel treasury is enabled, distribute %
        if (treasuryBps > 0) {
            uint256 treasuryAmount = wbtcBalance.mul(treasuryBps).div(MAX_BPS);
            wbtc.safeTransfer(citadelTreasury, treasuryAmount);
        }

        // keep this to get paid!
        _reportToVault(0);

        return harvested;
    }


    // Example tend is a no-op which returns the values, could also just revert
    function _tend() internal override returns (TokenAmount[] memory tended){
        revert("no op");
    }

    /// @dev Return the balance (in want) that the strategy has invested somewhere
    function balanceOfPool() public view override returns (uint256) {
        return baseRewardsPool.balanceOf(address(this));
    }

    /// @dev Return the balance of rewards that the strategy has accrued
    /// @notice Used for offChain APY and Harvest Health monitoring
    function balanceOfRewards() external view override returns (TokenAmount[] memory rewards) {
        rewards = new TokenAmount[](2);

        // Get CRV rewards amount
        uint256 crvAmount = baseRewardsPool.earned(address(this));

        rewards[0] = TokenAmount(address(crv), crvAmount);
        rewards[1] = TokenAmount(address(cvx), getMintableCVXRewards(crvAmount)); 
        return rewards;
    }

    // Reference: https://docs.convexfinance.com/convexfinanceintegration/cvx-minting
    function getMintableCVXRewards(uint256 _amount) public view returns (uint256) {
        uint256 cliffSize = cvx_minter.reductionPerCliff();
        uint256 cliffCount = cvx_minter.totalCliffs();
        uint256 maxSupply = cvx_minter.maxSupply();

        // Get total supply
        uint256 totalSupply = cvx_minter.totalSupply();

        // Get current cliff
        uint256 currentCliff = totalSupply.div(cliffSize);

        if (currentCliff < cliffCount) {
            // Get remaining Cliffs
            uint256 remaining = cliffCount.sub(currentCliff);
            // Multiply ratio of remaining cliffs to total cliffs against amount CRV received
            uint256 cvxEarned = _amount.mul(remaining).div(cliffCount);
            //double check we have not gone over the max supply
            uint256 amountTillMax = maxSupply.sub(totalSupply);
            if(cvxEarned >  amountTillMax){
                cvxEarned = amountTillMax;
            }
            return cvxEarned;
        }
        return 0;
    }

    /// @dev Helper function to calculate fees.
    /// @param amount Amount to calculate fee on.
    /// @param feeBps The fee to be charged in basis points.
    /// @return Amount of fees to take.
    /// @notice Taken from TheVault contract
    function _calculateFee(uint256 amount, uint256 feeBps)
        internal
        pure
        returns (uint256)
    {
        if (feeBps == 0) {
            return 0;
        }
        uint256 fee = (amount * feeBps) / MAX_BPS;
        return fee;
    }
}
