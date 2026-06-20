// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../contracts/InsuranceManager.sol";

contract InsuranceManagerTest {
    InsuranceManager private manager;

    function setUp() public {
        manager = new InsuranceManager();
    }

    function _policyId() private pure returns (bytes32) {
        return keccak256("policy-1");
    }

    function _seedPolicy() private {
        manager.purchasePolicy(
            _policyId(),
            address(0xBEEF),
            1000,
            25,
            40,
            300,
            180,
            1718832000,
            1718918400,
            bytes32("flight"),
            bytes32("recommendation"),
            bytes32("x402")
        );
    }

    function _policyIdentity(bytes32 policyId)
        private
        view
        returns (address customerWallet, uint256 escrowedUsdc, uint256 refundUsdc, InsuranceManager.PolicyStatus status)
    {
        (
            customerWallet,
            escrowedUsdc,
            refundUsdc,
            ,
            ,
            ,
            ,
            ,
            ,
            ,
            ,
            ,
            status
        ) = manager.policies(policyId);
    }

    function _policyEconomics(bytes32 policyId)
        private
        view
        returns (uint256 researchFeeUsdc, uint256 premiumUsdc, uint256 payoutUsdc)
    {
        InsuranceManager.PolicyStatus ignoredStatus;
        (
            ,
            ,
            ,
            researchFeeUsdc,
            premiumUsdc,
            payoutUsdc,
            ,
            ,
            ,
            ,
            ,
            ,
            ignoredStatus
        ) = manager.policies(policyId);
    }

    function _policyTiming(bytes32 policyId)
        private
        view
        returns (uint256 delayThresholdMinutes, uint256 policyStart, uint256 policyEnd)
    {
        InsuranceManager.PolicyStatus ignoredStatus;
        (
            ,
            ,
            ,
            ,
            ,
            ,
            delayThresholdMinutes,
            policyStart,
            policyEnd,
            ,
            ,
            ,
            ignoredStatus
        ) = manager.policies(policyId);
    }

    function _policyHashes(bytes32 policyId)
        private
        view
        returns (bytes32 flightHash, bytes32 recommendationHash, bytes32 x402Reference)
    {
        InsuranceManager.PolicyStatus ignoredStatus;
        (
            ,
            ,
            ,
            ,
            ,
            ,
            ,
            ,
            ,
            flightHash,
            recommendationHash,
            x402Reference,
            ignoredStatus
        ) = manager.policies(policyId);
    }

    function testPurchaseStoresEscrowAndCanBeCalledIdempotently() public {
        _seedPolicy();

        (
            address customerWallet,
            uint256 escrowedUsdc,
            uint256 refundUsdc,
            InsuranceManager.PolicyStatus status
        ) = _policyIdentity(_policyId());
        (
            uint256 researchFeeUsdc,
            uint256 premiumUsdc,
            uint256 payoutUsdc
        ) = _policyEconomics(_policyId());
        (
            uint256 delayThresholdMinutes,
            uint256 policyStart,
            uint256 policyEnd
        ) = _policyTiming(_policyId());
        (
            bytes32 flightHash,
            bytes32 recommendationHash,
            bytes32 x402Reference
        ) = _policyHashes(_policyId());
        require(customerWallet == address(0xBEEF), "wallet");
        require(escrowedUsdc == 1000, "escrow");
        require(refundUsdc == 0, "refund");
        require(researchFeeUsdc == 25, "fee");
        require(premiumUsdc == 40, "premium");
        require(payoutUsdc == 300, "payout");
        require(delayThresholdMinutes == 180, "delay");
        require(policyStart == 1718832000, "start");
        require(policyEnd == 1718918400, "end");
        require(flightHash == bytes32("flight"), "flight");
        require(recommendationHash == bytes32("recommendation"), "recommendation");
        require(x402Reference == bytes32("x402"), "x402");
        require(status == InsuranceManager.PolicyStatus.Active, "status");

        manager.purchasePolicy(
            _policyId(),
            address(0xBEEF),
            1000,
            25,
            40,
            300,
            180,
            1718832000,
            1718918400,
            bytes32("flight"),
            bytes32("recommendation"),
            bytes32("x402")
        );

        (
            ,
            uint256 idempotentEscrowedUsdc,
            ,
            InsuranceManager.PolicyStatus idempotentStatus
        ) = _policyIdentity(_policyId());
        require(idempotentEscrowedUsdc == 1000, "idempotent escrow");
        require(idempotentStatus == InsuranceManager.PolicyStatus.Active, "idempotent status");
    }

    function testRejectThenRefundTransitionsAndCopiesEscrow() public {
        _seedPolicy();

        manager.rejectPolicy(_policyId());
        (, , , InsuranceManager.PolicyStatus rejectedStatus) = _policyIdentity(_policyId());
        require(rejectedStatus == InsuranceManager.PolicyStatus.Rejected, "rejected");

        manager.refundPolicy(_policyId());
        (
            ,
            uint256 refundEscrowedUsdc,
            uint256 refundUsdc,
            InsuranceManager.PolicyStatus refundedStatus
        ) = _policyIdentity(_policyId());
        require(refundedStatus == InsuranceManager.PolicyStatus.Refunded, "refunded");
        require(refundUsdc == refundEscrowedUsdc, "refund amount");
    }

    function testResolveAndPayOutRequiresApproval() public {
        _seedPolicy();

        (bool beforeApproval, ) = address(manager).call(abi.encodeWithSelector(manager.payOut.selector, _policyId()));
        require(!beforeApproval, "payout should fail before approval");

        manager.resolvePolicy(_policyId(), false);
        (, , , InsuranceManager.PolicyStatus activeStatus) = _policyIdentity(_policyId());
        require(activeStatus == InsuranceManager.PolicyStatus.Active, "still active");

        manager.resolvePolicy(_policyId(), true);
        (, , , InsuranceManager.PolicyStatus approvedStatus) = _policyIdentity(_policyId());
        require(approvedStatus == InsuranceManager.PolicyStatus.PayoutApproved, "approved");

        manager.payOut(_policyId());
        (, , , InsuranceManager.PolicyStatus paidStatus) = _policyIdentity(_policyId());
        require(paidStatus == InsuranceManager.PolicyStatus.PayoutPaid, "paid");
    }
}
