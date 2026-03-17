"""
Staking Vault Service — StakingVaultV2 Contract Integration

Manages MDT token staking for miners, validators, and holders.
Contract ABI (StakingVaultV2.sol):
  Core: stake(uint256, StakeRole), requestUnstake(), withdraw()
  Rewards: depositRewards(uint256), claimRewards(), pendingRewards(address)
  Slashing: slash(address, uint256, string)
  View: isStaked, isValidator, isMiner, getStakeInfo, getStakeAmount, getPoolStats
  Fee: getCurrentRegFee()
  Admin: setMinMinerStake, setMinValidatorStake, setMinHolderStake,
    setUnstakeCooldown, setRegFeeFloor, setRegFeeCeiling, setDecayInterval,
    pause, unpause

For ModernTensor on Hedera — Hello Future Hackathon 2026
"""

import logging
from typing import Optional, TYPE_CHECKING
from enum import IntEnum

from hiero_sdk_python import ContractFunctionParameters

if TYPE_CHECKING:
    from .client import HederaClient
    from hiero_sdk_python import ContractFunctionResult, TransactionReceipt

logger = logging.getLogger(__name__)


class StakeRole(IntEnum):
    """Staking role matching StakingVaultV2.sol"""

    NONE = 0
    MINER = 1
    VALIDATOR = 2
    HOLDER = 3


class StakingVaultService:
    """
    Service for StakingVaultV2 contract operations.
    Manages MDT token staking, unstaking, rewards, slashing, and role queries.

    Usage:
        from sdk.hedera.staking_vault import StakingVaultService, StakeRole
        staking = StakingVaultService(client)
        staking.contract_id = "0.0.8046039"

        staking.stake(amount=100*10**8, role=StakeRole.MINER)
        staking.stake(amount=50*10**8, role=StakeRole.HOLDER)
        staking.request_unstake()
        staking.withdraw()
    """

    def __init__(self, client: "HederaClient"):
        self.client = client
        self._contract_id: Optional[str] = None

    @property
    def contract_id(self) -> Optional[str]:
        if self._contract_id:
            return self._contract_id
        import os

        cid = os.getenv("HEDERA_STAKING_VAULT_CONTRACT_ID")
        if cid and cid != "None":
            return cid
        return None

    @contract_id.setter
    def contract_id(self, value: str):
        self._contract_id = value

    def _require_contract(self):
        if not self.contract_id:
            raise ValueError("StakingVault contract not set.")

    # ── Core Staking Operations ──────────────────────────────────

    def stake(
        self, amount: int, role: int = StakeRole.MINER, gas: int = 500_000
    ) -> "TransactionReceipt":
        """Stake MDT tokens. role: MINER(1), VALIDATOR(2), or HOLDER(3)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(amount)
        params.add_uint8(int(role))
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="stake",
            params=params,
            gas=gas,
        )

    def request_unstake(self, gas: int = 100_000) -> "TransactionReceipt":
        """Request unstake (starts 7-day cooldown)."""
        self._require_contract()
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="requestUnstake",
            gas=gas,
        )

    def withdraw(self, gas: int = 500_000) -> "TransactionReceipt":
        """Withdraw staked tokens after cooldown period."""
        self._require_contract()
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="withdraw",
            gas=gas,
        )

    def slash(
        self,
        user_address: str,
        basis_points: int,
        reason: str,
        gas: int = 200_000,
    ) -> "TransactionReceipt":
        """Slash a staker (owner only). basis_points: 1-10000 (100% = 10000)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_address(user_address)
        params.add_uint256(basis_points)
        params.add_string(reason)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="slash",
            params=params,
            gas=gas,
        )

    # ── Reward Pool Operations (V2) ──────────────────────────────

    def deposit_rewards(self, amount: int, gas: int = 200_000) -> "TransactionReceipt":
        """Deposit MDT into the reward pool for staker distributions."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(amount)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="depositRewards",
            params=params,
            gas=gas,
        )

    def claim_rewards(self, gas: int = 300_000) -> "TransactionReceipt":
        """Claim accumulated staking rewards."""
        self._require_contract()
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="claimRewards",
            gas=gas,
        )

    def pending_rewards(
        self, user_address: str, gas: int = 50_000
    ) -> "ContractFunctionResult":
        """Check pending reward amount for an address."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_address(user_address)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="pendingRewards",
            params=params,
            gas=gas,
        )

    # ── Fee Query (V2) ───────────────────────────────────────────

    def get_current_reg_fee(self, gas: int = 50_000) -> "ContractFunctionResult":
        """Get current dynamic registration fee (decays over time)."""
        self._require_contract()
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="getCurrentRegFee",
            gas=gas,
        )

    # ── View / Query Functions ───────────────────────────────────

    def is_staked(
        self, user_address: str, gas: int = 50_000
    ) -> "ContractFunctionResult":
        """Check if address is staked."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_address(user_address)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="isStaked",
            params=params,
            gas=gas,
        )

    def is_validator(
        self, user_address: str, gas: int = 50_000
    ) -> "ContractFunctionResult":
        """Check if address is a staked validator."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_address(user_address)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="isValidator",
            params=params,
            gas=gas,
        )

    def is_miner(
        self, user_address: str, gas: int = 50_000
    ) -> "ContractFunctionResult":
        """Check if address is a staked miner."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_address(user_address)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="isMiner",
            params=params,
            gas=gas,
        )

    def get_stake_info(
        self, user_address: str, gas: int = 50_000
    ) -> "ContractFunctionResult":
        """Get stake info (amount, role, unstakeRequestedAt, slashed)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_address(user_address)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="getStakeInfo",
            params=params,
            gas=gas,
        )

    def get_stake_amount(
        self, user_address: str, gas: int = 50_000
    ) -> "ContractFunctionResult":
        """Get raw stake amount for an address."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_address(user_address)
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="getStakeAmount",
            params=params,
            gas=gas,
        )

    def get_pool_stats(self, gas: int = 80_000) -> "ContractFunctionResult":
        """Get reward pool stats (totalStaked, rewardPool, accRewardPerShare, etc.)."""
        self._require_contract()
        return self.client.call_contract(
            contract_id=self.contract_id,
            function_name="getPoolStats",
            gas=gas,
        )

    # ── Admin Functions ──────────────────────────────────────────

    def set_min_miner_stake(
        self, min_stake: int, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Set minimum miner stake (owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(min_stake)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="setMinMinerStake",
            params=params,
            gas=gas,
        )

    def set_min_validator_stake(
        self, min_stake: int, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Set minimum validator stake (owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(min_stake)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="setMinValidatorStake",
            params=params,
            gas=gas,
        )

    def set_min_holder_stake(
        self, min_stake: int, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Set minimum holder stake (owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(min_stake)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="setMinHolderStake",
            params=params,
            gas=gas,
        )

    def set_unstake_cooldown(
        self, cooldown: int, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Set unstake cooldown period in seconds (owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(cooldown)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="setUnstakeCooldown",
            params=params,
            gas=gas,
        )

    def set_reg_fee_floor(
        self, floor: int, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Set registration fee floor (owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(floor)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="setRegFeeFloor",
            params=params,
            gas=gas,
        )

    def set_reg_fee_ceiling(
        self, ceiling: int, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Set registration fee ceiling (owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(ceiling)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="setRegFeeCeiling",
            params=params,
            gas=gas,
        )

    def set_decay_interval(
        self, interval: int, gas: int = 100_000
    ) -> "TransactionReceipt":
        """Set fee decay interval in seconds (owner only)."""
        self._require_contract()
        params = ContractFunctionParameters()
        params.add_uint256(interval)
        return self.client.execute_contract(
            contract_id=self.contract_id,
            function_name="setDecayInterval",
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

    def __repr__(self) -> str:
        return f"<StakingVaultService contract={self.contract_id}>"
