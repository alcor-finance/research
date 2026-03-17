// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IAavePoolMinimal} from "../interfaces/IAavePoolMinimal.sol";
import {SafeERC20Ops} from "../lib/SafeERC20Ops.sol";

abstract contract AaveModule {
    using SafeERC20Ops for address;

    event PoolUpdated(address indexed oldPool, address indexed newPool);
    event AaveSupplied(address indexed asset, uint256 amount);
    event AaveBorrowed(address indexed asset, uint256 amount, uint256 rateMode);
    event AaveRepaid(address indexed asset, uint256 amount, uint256 rateMode);
    event AaveWithdrawn(address indexed asset, uint256 amount);

    address public aavePool;

    constructor(address aavePool_) {
        aavePool = aavePool_;
    }

    function _setAavePool(address newPool) internal {
        address old = aavePool;
        aavePool = newPool;
        emit PoolUpdated(old, newPool);
    }

    function _aaveSupply(address asset, uint256 amount) internal {
        asset.forceApprove(aavePool, amount);
        IAavePoolMinimal(aavePool).supply(asset, amount, address(this), 0);
        emit AaveSupplied(asset, amount);
    }

    function _aaveBorrow(address asset, uint256 amount, uint256 interestRateMode) internal {
        IAavePoolMinimal(aavePool).borrow(asset, amount, interestRateMode, 0, address(this));
        emit AaveBorrowed(asset, amount, interestRateMode);
    }

    function _aaveRepay(address asset, uint256 amount, uint256 interestRateMode) internal {
        asset.forceApprove(aavePool, amount);
        IAavePoolMinimal(aavePool).repay(asset, amount, interestRateMode, address(this));
        emit AaveRepaid(asset, amount, interestRateMode);
    }

    function _aaveWithdraw(address asset, uint256 amount) internal {
        IAavePoolMinimal(aavePool).withdraw(asset, amount, address(this));
        emit AaveWithdrawn(asset, amount);
    }
}
