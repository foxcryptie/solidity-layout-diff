// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract VaultV1 {
    address public owner;
    uint96 public feeBps;
    mapping(address => uint256) public balance;
}

contract VaultV2Append {
    address public owner;
    uint96 public feeBps;
    mapping(address => uint256) public balance;
    uint256 public withdrawalDelay;
}

contract VaultV2Reordered {
    uint96 public feeBps;
    address public owner;
    mapping(address => uint256) public balance;
}

contract VaultV2MappingType {
    address public owner;
    uint96 public feeBps;
    mapping(address => uint128) public balance;
}

contract GapV1 {
    address public owner;
    uint256[50] private __gap;
}

contract GapV2 {
    address public owner;
    uint256 public withdrawalDelay;
    uint256[49] private __gap;
}

contract PositionV1 {
    struct Position { uint128 collateral; uint128 debt; }
    mapping(address => Position) public positions;
}

contract PositionV2Changed {
    struct Position { uint128 collateral; uint64 debt; }
    mapping(address => Position) public positions;
}
