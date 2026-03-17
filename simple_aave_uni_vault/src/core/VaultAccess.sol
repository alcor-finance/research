// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

abstract contract VaultAccess {
    error NotDepositor();
    error NotOperator();
    error NotManager();
    error ManagerDestinationNotWhitelisted();
    error EthTransferFailed();

    event ManagerUpdated(address indexed oldManager, address indexed newManager);
    event WhitelistUpdated(address indexed target, bool allowed);

    address public immutable DEPOSITOR;
    address public manager;
    mapping(address => bool) public whitelist;

    modifier onlyDepositor() {
        if (msg.sender != DEPOSITOR) revert NotDepositor();
        _;
    }

    modifier onlyManager() {
        if (msg.sender != manager) revert NotManager();
        _;
    }

    modifier onlyOperator() {
        if (msg.sender != manager && msg.sender != DEPOSITOR) revert NotOperator();
        _;
    }

    constructor(address depositor_, address manager_) {
        DEPOSITOR = depositor_;
        manager = manager_;
    }

    function _setManager(address newManager) internal {
        address old = manager;
        manager = newManager;
        emit ManagerUpdated(old, newManager);
    }

    function _setWhitelist(address target, bool allowed) internal {
        whitelist[target] = allowed;
        emit WhitelistUpdated(target, allowed);
    }

    function _enforceManagerWhitelist(address to) internal view {
        if (!whitelist[to]) revert ManagerDestinationNotWhitelisted();
    }

    function _transferEth(address payable to, uint256 amount) internal {
        (bool ok,) = to.call{value: amount}("");
        if (!ok) revert EthTransferFailed();
    }
}
