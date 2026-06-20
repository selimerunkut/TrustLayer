// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);

    function transferFrom(address from, address to, uint256 amount) external returns (bool);

    function allowance(address owner, address spender) external view returns (uint256);
}

contract InsuranceManager {
    enum PolicyStatus {
        Pending,
        Active,
        Rejected,
        Refunded,
        PayoutApproved,
        PayoutPaid
    }

    struct PolicyRecord {
        address customerWallet;
        uint256 escrowedUsdc;
        uint256 refundUsdc;
        uint256 researchFeeUsdc;
        uint256 premiumUsdc;
        uint256 payoutUsdc;
        uint256 delayThresholdMinutes;
        uint256 policyStart;
        uint256 policyEnd;
        bytes32 flightHash;
        bytes32 recommendationHash;
        bytes32 x402Reference;
        PolicyStatus status;
    }

    IERC20 public immutable usdcToken;
    address public immutable premiumVault;

    mapping(bytes32 => PolicyRecord) public policies;

    event PolicyPurchased(bytes32 indexed policyId, address indexed customerWallet, uint256 escrowedUsdc);
    event PremiumTransferred(
        bytes32 indexed policyId,
        address indexed payer,
        address indexed vault,
        uint256 premiumUsdc
    );
    event PolicyRejected(bytes32 indexed policyId);
    event PolicyRefunded(bytes32 indexed policyId, uint256 refundUsdc);
    event PolicyPayoutApproved(bytes32 indexed policyId, uint256 payoutUsdc);
    event PolicyPayoutPaid(bytes32 indexed policyId, uint256 payoutUsdc);

    constructor(address usdcTokenAddress, address premiumVaultAddress) {
        require(usdcTokenAddress != address(0), "usdc token required");
        require(premiumVaultAddress != address(0), "premium vault required");
        usdcToken = IERC20(usdcTokenAddress);
        premiumVault = premiumVaultAddress;
    }

    function _policyMatches(
        PolicyRecord storage existing,
        address customerWallet,
        uint256 escrowedUsdc,
        uint256 researchFeeUsdc,
        uint256 premiumUsdc,
        uint256 payoutUsdc,
        uint256 delayThresholdMinutes,
        uint256 policyStart,
        uint256 policyEnd,
        bytes32 flightHash,
        bytes32 recommendationHash,
        bytes32 x402Reference
    ) private view returns (bool) {
        return
            existing.customerWallet == customerWallet &&
            existing.escrowedUsdc == escrowedUsdc &&
            existing.researchFeeUsdc == researchFeeUsdc &&
            existing.premiumUsdc == premiumUsdc &&
            existing.payoutUsdc == payoutUsdc &&
            existing.delayThresholdMinutes == delayThresholdMinutes &&
            existing.policyStart == policyStart &&
            existing.policyEnd == policyEnd &&
            existing.flightHash == flightHash &&
            existing.recommendationHash == recommendationHash &&
            existing.x402Reference == x402Reference;
    }

    function purchasePolicy(
        bytes32 policyId,
        address customerWallet,
        uint256 budgetLockedUsdc,
        uint256 researchFeeUsdc,
        uint256 premiumUsdc,
        uint256 payoutUsdc,
        uint256 delayThresholdMinutes,
        uint256 policyStart,
        uint256 policyEnd,
        bytes32 flightHash,
        bytes32 recommendationHash,
        bytes32 x402Reference
    ) external {
        PolicyRecord storage existing = policies[policyId];
        if (existing.customerWallet != address(0)) {
            if (
                !_policyMatches(
                    existing,
                    customerWallet,
                    budgetLockedUsdc,
                    researchFeeUsdc,
                    premiumUsdc,
                    payoutUsdc,
                    delayThresholdMinutes,
                    policyStart,
                    policyEnd,
                    flightHash,
                    recommendationHash,
                    x402Reference
                )
            ) {
                revert("policy already written with different contents");
            }
            return;
        }

        require(premiumUsdc > 0, "premium required");
        require(
            usdcToken.transferFrom(msg.sender, premiumVault, premiumUsdc),
            "premium transfer failed"
        );
        emit PremiumTransferred(policyId, msg.sender, premiumVault, premiumUsdc);

        policies[policyId] = PolicyRecord({
            customerWallet: customerWallet,
            escrowedUsdc: budgetLockedUsdc,
            refundUsdc: 0,
            researchFeeUsdc: researchFeeUsdc,
            premiumUsdc: premiumUsdc,
            payoutUsdc: payoutUsdc,
            delayThresholdMinutes: delayThresholdMinutes,
            policyStart: policyStart,
            policyEnd: policyEnd,
            flightHash: flightHash,
            recommendationHash: recommendationHash,
            x402Reference: x402Reference,
            status: PolicyStatus.Active
        });
        emit PolicyPurchased(policyId, customerWallet, budgetLockedUsdc);
    }

    function rejectPolicy(bytes32 policyId) external {
        PolicyRecord storage policy = policies[policyId];
        require(policy.customerWallet != address(0), "unknown policy");
        require(policy.status == PolicyStatus.Active || policy.status == PolicyStatus.Pending, "policy not open");
        policy.status = PolicyStatus.Rejected;
        emit PolicyRejected(policyId);
    }

    function refundPolicy(bytes32 policyId) external {
        PolicyRecord storage policy = policies[policyId];
        require(policy.customerWallet != address(0), "unknown policy");
        require(policy.status == PolicyStatus.Rejected, "policy not rejected");
        policy.status = PolicyStatus.Refunded;
        policy.refundUsdc = policy.escrowedUsdc;
        emit PolicyRefunded(policyId, policy.refundUsdc);
    }

    function resolvePolicy(bytes32 policyId, bool delayQualified) external {
        PolicyRecord storage policy = policies[policyId];
        require(policy.customerWallet != address(0), "unknown policy");
        require(policy.status == PolicyStatus.Active, "policy not active");
        if (delayQualified) {
            policy.status = PolicyStatus.PayoutApproved;
            emit PolicyPayoutApproved(policyId, policy.payoutUsdc);
        }
    }

    function payOut(bytes32 policyId) external {
        PolicyRecord storage policy = policies[policyId];
        require(policy.customerWallet != address(0), "unknown policy");
        require(policy.status == PolicyStatus.PayoutApproved, "payout not approved");
        require(
            usdcToken.transfer(policy.customerWallet, policy.payoutUsdc),
            "payout transfer failed"
        );
        policy.status = PolicyStatus.PayoutPaid;
        emit PolicyPayoutPaid(policyId, policy.payoutUsdc);
    }
}
