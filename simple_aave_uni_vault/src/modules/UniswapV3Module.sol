// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IUniswapV3SwapRouter} from "../interfaces/IUniswapV3SwapRouter.sol";
import {SafeERC20Ops} from "../lib/SafeERC20Ops.sol";

abstract contract UniswapV3Module {
    using SafeERC20Ops for address;

    event RouterUpdated(address indexed oldRouter, address indexed newRouter);
    event UniswapSwapped(address indexed tokenIn, address indexed tokenOut, uint24 fee, uint256 amountIn, uint256 amountOut);

    address public uniswapV3Router;

    constructor(address uniswapV3Router_) {
        uniswapV3Router = uniswapV3Router_;
    }

    function _setUniswapV3Router(address newRouter) internal {
        address old = uniswapV3Router;
        uniswapV3Router = newRouter;
        emit RouterUpdated(old, newRouter);
    }

    function _uniswapV3SwapExactInputSingle(
        address tokenIn,
        address tokenOut,
        uint24 fee,
        uint256 amountIn,
        uint256 amountOutMinimum,
        uint160 sqrtPriceLimitX96,
        uint256 deadline
    ) internal returns (uint256 amountOut) {
        tokenIn.forceApprove(uniswapV3Router, amountIn);

        IUniswapV3SwapRouter.ExactInputSingleParams memory params = IUniswapV3SwapRouter.ExactInputSingleParams({
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            fee: fee,
            recipient: address(this),
            deadline: deadline,
            amountIn: amountIn,
            amountOutMinimum: amountOutMinimum,
            sqrtPriceLimitX96: sqrtPriceLimitX96
        });

        amountOut = IUniswapV3SwapRouter(uniswapV3Router).exactInputSingle(params);
        emit UniswapSwapped(tokenIn, tokenOut, fee, amountIn, amountOut);
    }
}
