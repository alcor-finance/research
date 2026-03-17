// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20Minimal} from "../interfaces/IERC20Minimal.sol";

library SafeERC20Ops {
    error ERC20OpFailed();

    function safeTransfer(address token, address to, uint256 amount) internal {
        bool ok = IERC20Minimal(token).transfer(to, amount);
        if (!ok) revert ERC20OpFailed();
    }

    function safeTransferFrom(address token, address from, address to, uint256 amount) internal {
        bool ok = IERC20Minimal(token).transferFrom(from, to, amount);
        if (!ok) revert ERC20OpFailed();
    }

    function forceApprove(address token, address spender, uint256 amount) internal {
        bool ok0 = IERC20Minimal(token).approve(spender, 0);
        bool ok1 = IERC20Minimal(token).approve(spender, amount);
        if (!ok0 || !ok1) revert ERC20OpFailed();
    }
}
