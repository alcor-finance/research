// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20Minimal} from "./interfaces/IERC20Minimal.sol";
import {SafeERC20Ops} from "./lib/SafeERC20Ops.sol";
import {VaultAccess} from "./core/VaultAccess.sol";
import {AaveModule} from "./modules/AaveModule.sol";
import {UniswapV3Module} from "./modules/UniswapV3Module.sol";

/// @title ManagerAaveUniVault
/// @notice Vault with two operational roles and strategy actions for Aave + Uniswap.
/// @dev Responsibility split:
///      - VaultAccess: role and whitelist control
///      - AaveModule: supply/borrow/repay/withdraw logic
///      - UniswapV3Module: exactInputSingle swap logic
contract ManagerAaveUniVault is VaultAccess, AaveModule, UniswapV3Module {
    using SafeERC20Ops for address;

    event DepositedToken(address indexed token, address indexed from, uint256 amount);
    event DepositedEth(address indexed from, uint256 amount);
    event ManagerWithdrawToken(address indexed token, address indexed to, uint256 amount);
    event ManagerWithdrawEth(address indexed to, uint256 amount);
    event DepositorWithdrawToken(address indexed token, address indexed to, uint256 amount);
    event DepositorWithdrawEth(address indexed to, uint256 amount);

    constructor(address depositor_, address manager_, address aavePool_, address uniswapV3Router_)
        VaultAccess(depositor_, manager_)
        AaveModule(aavePool_)
        UniswapV3Module(uniswapV3Router_)
    {}

    receive() external payable {
        emit DepositedEth(msg.sender, msg.value);
    }

    // ----- Funding -----

    function depositToken(address token, uint256 amount) external {
        token.safeTransferFrom(msg.sender, address(this), amount);
        emit DepositedToken(token, msg.sender, amount);
    }

    // ----- Admin controls (depositor only) -----

    function setManager(address newManager) external onlyDepositor {
        _setManager(newManager);
    }

    function setWhitelist(address target, bool allowed) external onlyDepositor {
        _setWhitelist(target, allowed);
    }

    function setUniswapV3Router(address newRouter) external onlyDepositor {
        _setUniswapV3Router(newRouter);
    }

    function setAavePool(address newPool) external onlyDepositor {
        _setAavePool(newPool);
    }

    // ----- Withdraw logic -----

    function managerWithdrawToken(address token, address to, uint256 amount) external onlyManager {
        _enforceManagerWhitelist(to);
        token.safeTransfer(to, amount);
        emit ManagerWithdrawToken(token, to, amount);
    }

    function managerWithdrawEth(address payable to, uint256 amount) external onlyManager {
        _enforceManagerWhitelist(to);
        _transferEth(to, amount);
        emit ManagerWithdrawEth(to, amount);
    }

    function depositorWithdrawToken(address token, address to, uint256 amount) external onlyDepositor {
        token.safeTransfer(to, amount);
        emit DepositorWithdrawToken(token, to, amount);
    }

    function depositorWithdrawEth(address payable to, uint256 amount) external onlyDepositor {
        _transferEth(to, amount);
        emit DepositorWithdrawEth(to, amount);
    }

    // ----- Strategy actions (manager or depositor) -----

    function aaveSupply(address asset, uint256 amount) external onlyOperator {
        _aaveSupply(asset, amount);
    }

    function aaveBorrow(address asset, uint256 amount, uint256 interestRateMode) external onlyOperator {
        _aaveBorrow(asset, amount, interestRateMode);
    }

    function aaveRepay(address asset, uint256 amount, uint256 interestRateMode) external onlyOperator {
        _aaveRepay(asset, amount, interestRateMode);
    }

    function aaveWithdraw(address asset, uint256 amount) external onlyOperator {
        _aaveWithdraw(asset, amount);
    }

    function uniswapV3SwapExactInputSingle(
        address tokenIn,
        address tokenOut,
        uint24 fee,
        uint256 amountIn,
        uint256 amountOutMinimum,
        uint160 sqrtPriceLimitX96,
        uint256 deadline
    ) external onlyOperator returns (uint256 amountOut) {
        return _uniswapV3SwapExactInputSingle(
            tokenIn,
            tokenOut,
            fee,
            amountIn,
            amountOutMinimum,
            sqrtPriceLimitX96,
            deadline
        );
    }

    // ----- Views -----

    function tokenBalance(address token) external view returns (uint256) {
        return IERC20Minimal(token).balanceOf(address(this));
    }
}
