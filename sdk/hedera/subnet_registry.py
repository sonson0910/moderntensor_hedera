"""
Subnet Registry Service — SubnetRegistryV2 Contract Integration

Manages subnets, miners, validators, task lifecycle, direct scoring,
reputation portability, and earnings on-chain.

Contract ABI (SubnetRegistryV2.sol):
  Subnet: registerSubnet
  Miners: registerMiner
  Validators: addValidator, removeValidator
  Tasks: createTask, submitResult, expireTask, finalizeTask
  Scoring: validateSubmission
  Earnings: withdrawEarnings, withdrawProtocolFees
  Reputation: portReputation, getValidatorReputation
  Adaptive: getAdaptiveMinValidations
  View: getSubnet, getTask, getSubmissions, getSubmissionCount, isMiner,
    isValidator
  Admin: setProtocolTreasury, setStakingVault, setMinValidations, pause, unpause

For ModernTensor on Hedera — Hello Future Hackathon 2026
"""

import logging
from enum import IntEnum
from typing import Optional, TYPE_CHECKING

from hiero_sdk_python import ContractFunctionParameters

if TYPE_CHECKING:
    from .client import HederaClient
    from hiero_sdk_python import ContractFunctionResult, TransactionReceipt

logger = logging.getLogger(__name__)


class SubnetStatus(IntEnum):
    """Subnet status matching SubnetRegistryV2.sol"""

    ACTIVE = 0
    PAUSED = 1
    DEACTIVATED = 2


class SubnetRegistryService:
    """
    Service for SubnetRegistryV2 contract operations.

    Full subnet lifecycle: register subnets, enroll miners/validators,
    create tasks, submit/score/finalize, withdraw earnings,
    reputation portability across subnets.

    Usage:
        from sdk.hedera.subnet_registry import SubnetRegistryService
        registry = SubnetRegistryService(client)
        registry.contract_id = "0.0.8046035"

        registry.register_subnet("AI Code Review", "Review Solidity code", 300)
        registry.register_miner(subnet_id=0)
        registry.create_task(0, "QmTaskHash...", 100*10**8, 86400)
    """

    def __init__(self, client: "HederaClient"):
        self.client = client
        self._contract_id: Optional[str] = None

    @property
    def contract_id(self) -> Optional[str]:
        if self._contract_id:
            return self._contract_id
        import os

        cid = os.getenv("HEDERA_SUBNET_REGISTRY_CONTRACT_ID")
        if cid and cid != "None":
            return cid
        return None

    @contract_id.setter
    def contract_id(self, value: str):
        self._contract_id = value

    def _require_contract(self):
        if not self.contract_id:
            raise ValueError("SubnetRegistry contract not set.")

    # ── Subnet Management ────────────────────────────────────────

    def register_subnet(
        self,
        name: str,
        description: str,
        fee_rate: int,
        gas: int = 800_000,
    ) -> "TransactionReceipt":
        """Register a new subnet. fee_rate in basis points (e.g. 300 = 3%)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_string(name)
        params.add_string(description)
        params.add_uint256(fee_rate)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="registerSubnet",
            params=params,
            gas=gas,
        )

    # ── Miner Management ─────────────────────────────────────────

    def register_miner(
        self, subnet_id: int, gas: int = 150_000
    ) -> "TransactionReceipt":
        """Register as a miner in a subnet. Must have staked in StakingVault first."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(subnet_id)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="registerMiner",
            params=params,
            gas=gas,
        )

    # ── Validator Management ─────────────────────────────────────

    def add_validator(
        self, subnet_id: int, validator_address: str, gas: int = 150_000
    ) -> "TransactionReceipt":
        """Add a validator to a subnet. Must have staked in StakingVault first."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(subnet_id)
        params.add_address(validator_address)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="addValidator",
            params=params,
            gas=gas,
        )

    def remove_validator(
        self, subnet_id: int, validator_address: str, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Remove a validator from a subnet (subnet owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(subnet_id)
        params.add_address(validator_address)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="removeValidator",
            params=params,
            gas=gas,
        )

    # ── Task Lifecycle ───────────────────────────────────────────

    def create_task(
        self,
        subnet_id: int,
        task_hash: str,
        reward_amount: int,
        duration: int,
        gas: int = 800_000,
    ) -> "TransactionReceipt":
        """Create a task within a subnet. Caller must approve MDT first."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(subnet_id)
        params.add_string(task_hash)
        params.add_uint256(reward_amount)
        params.add_uint256(duration)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="createTask",
            params=params,
            gas=gas,
        )

    def submit_result(
        self, task_id: int, result_hash: str, gas: int = 200_000
    ) -> "TransactionReceipt":
        """Submit a result for a task (miner)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(task_id)
        params.add_string(result_hash)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="submitResult",
            params=params,
            gas=gas,
        )

    def expire_task(self, task_id: int, gas: int = 500_000) -> "TransactionReceipt":
        """Expire a timed-out task and refund requester."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(task_id)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="expireTask",
            params=params,
            gas=gas,
        )

    def finalize_task(self, task_id: int, gas: int = 800_000) -> "TransactionReceipt":
        """Finalize task: determine winner, distribute rewards."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(task_id)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="finalizeTask",
            params=params,
            gas=gas,
        )

    # ── Scoring (Direct — V2 removes commit-reveal) ──────────────

    def validate_submission(
        self, task_id: int, miner_index: int, score: int, gas: int = 200_000
    ) -> "TransactionReceipt":
        """Score a submission directly (0-10000 bps). Validator only."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(task_id)
        params.add_uint256(miner_index)
        params.add_uint256(score)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="validateSubmission",
            params=params,
            gas=gas,
        )

    # ── Earnings ─────────────────────────────────────────────────

    def withdraw_earnings(self, gas: int = 500_000) -> "TransactionReceipt":
        """Withdraw accumulated earnings (miners/validators/subnet owners)."""
        self._require_contract()
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="withdrawEarnings",
            gas=gas,
        )

    def withdraw_protocol_fees(self, gas: int = 500_000) -> "TransactionReceipt":
        """Withdraw protocol fees (protocol owner only)."""
        self._require_contract()
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="withdrawProtocolFees",
            gas=gas,
        )

    # ── Reputation ───────────────────────────────────────────────

    def port_reputation(
        self, from_subnet_id: int, to_subnet_id: int, gas: int = 150_000
    ) -> "TransactionReceipt":
        """Port reputation between subnets (50% decay, 1-day cooldown)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(from_subnet_id)
        params.add_uint256(to_subnet_id)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="portReputation",
            params=params,
            gas=gas,
        )

    def get_validator_reputation(
        self, validator_address: str, gas: int = 80_000
    ) -> "ContractFunctionResult":
        """Get validator reputation (totalValidations, accurateValidations, reputationScore, lastActiveAt)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_address(validator_address)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="getValidatorReputation",
            params=params,
            gas=gas,
        )

    # ── Admin Functions ──────────────────────────────────────────

    def set_min_validations(
        self, subnet_id: int, min_validations: int, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Set minimum validators required for consensus (owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(subnet_id)
        params.add_uint256(min_validations)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="setMinValidations",
            params=params,
            gas=gas,
        )

    def set_protocol_treasury(
        self, new_treasury: str, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Set protocol treasury address (owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_address(new_treasury)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="setProtocolTreasury",
            params=params,
            gas=gas,
        )

    def set_staking_vault(
        self, vault_address: str, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Set StakingVault address for cross-contract verification (owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_address(vault_address)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="setStakingVault",
            params=params,
            gas=gas,
        )

    def pause(self, gas: int = 50_000) -> "TransactionReceipt":
        """Pause contract (owner only)."""
        self._require_contract()
        return self.client.execute_contract(
            contract_id=self.contract_id, function_name="pause", gas=gas
        )

    def unpause(self, gas: int = 50_000) -> "TransactionReceipt":
        """Unpause contract (owner only)."""
        self._require_contract()
        return self.client.execute_contract(
            contract_id=self.contract_id, function_name="unpause", gas=gas
        )

    # ── View / Query Functions ───────────────────────────────────

    def get_subnet_count(self, gas: int = 50_000) -> "ContractFunctionResult":
        """Get total number of registered subnets (reads public uint256 subnetCount)."""
        self._require_contract()
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="subnetCount",
            gas=gas,
        )

    def get_subnet(self, subnet_id: int, gas: int = 80_000) -> "ContractFunctionResult":
        """Get subnet info by ID."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(subnet_id)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="getSubnet",
            params=params,
            gas=gas,
        )

    def get_task(self, task_id: int, gas: int = 100_000) -> "ContractFunctionResult":
        """Get task info by ID (id, subnetId, requester, status, etc.)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(task_id)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="getTask",
            params=params,
            gas=gas,
        )

    def get_submissions(
        self, task_id: int, gas: int = 80_000
    ) -> "ContractFunctionResult":
        """Get all submissions for a task."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(task_id)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="getSubmissions",
            params=params,
            gas=gas,
        )

    def get_submission_count(
        self, task_id: int, gas: int = 50_000
    ) -> "ContractFunctionResult":
        """Get number of submissions for a task."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(task_id)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="getSubmissionCount",
            params=params,
            gas=gas,
        )

    def is_miner(
        self, subnet_id: int, miner_address: str, gas: int = 50_000
    ) -> "ContractFunctionResult":
        """Check if address is a registered miner in a subnet."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(subnet_id)
        params.add_address(miner_address)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="isMiner",
            params=params,
            gas=gas,
        )

    def is_validator(
        self, subnet_id: int, validator_address: str, gas: int = 50_000
    ) -> "ContractFunctionResult":
        """Check if address is a registered validator in a subnet."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(subnet_id)
        params.add_address(validator_address)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="isValidator",
            params=params,
            gas=gas,
        )

    def get_adaptive_min_validations(
        self, subnet_id: int, reward_amount: int, gas: int = 50_000
    ) -> "ContractFunctionResult":
        """Get adaptive minimum validations based on task reward value."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(subnet_id)
        params.add_uint256(reward_amount)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="getAdaptiveMinValidations",
            params=params,
            gas=gas,
        )

    def __repr__(self) -> str:
        return f"<SubnetRegistryService contract={self.contract_id}>"
