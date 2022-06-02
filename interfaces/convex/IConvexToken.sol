// SPDX-License-Identifier: MIT
pragma solidity >=0.7.0 <0.9.0;

interface IConvexToken {
    event Approval(
        address indexed owner,
        address indexed spender,
        uint256 value
    );
    event Transfer(address indexed from, address indexed to, uint256 value);

    function allowance(address owner, address spender)
        external
        view
        returns (uint256);

    function approve(address spender, uint256 amount) external returns (bool);

    function balanceOf(address account) external view returns (uint256);

    function decimals() external view returns (uint8);

    function decreaseAllowance(address spender, uint256 subtractedValue)
        external
        returns (bool);

    function increaseAllowance(address spender, uint256 addedValue)
        external
        returns (bool);

    function maxSupply() external view returns (uint256);

    function mint(address _to, uint256 _amount) external;

    function name() external view returns (string memory);

    function operator() external view returns (address);

    function reductionPerCliff() external view returns (uint256);

    function symbol() external view returns (string memory);

    function totalCliffs() external view returns (uint256);

    function totalSupply() external view returns (uint256);

    function transfer(address recipient, uint256 amount)
        external
        returns (bool);

    function transferFrom(
        address sender,
        address recipient,
        uint256 amount
    ) external returns (bool);

    function updateOperator() external;

    function vecrvProxy() external view returns (address);
}