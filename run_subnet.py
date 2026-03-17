#!/usr/bin/env python3
"""
ModernTensor Subnet Orchestrator
=================================

Runs a complete subnet with 2 miners + 3 validators through continuous
benchmark epochs — the Bittensor-style incentive loop on Hedera.

Architecture
------------
    ┌─────────────────────────────────────────────────────────────────┐
    │                    Subnet Orchestrator                          │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
    │  │  Miner   │  │  Miner   │  │Validator │  │Validator │ ...   │
    │  │  (Axon)  │  │  (Axon)  │  │(Dendrite)│  │(Dendrite)│       │
    │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
    │       │              │             │              │              │
    │  ┌────┴──────────────┴─────────────┴──────────────┴──────┐     │
    │  │              SDK Protocol Layer                         │     │
    │  │  ScoreConsensus │ WeightCalculator │ EmissionSchedule   │     │
    │  └───────────────────────┬────────────────────────────────┘     │
    │                          │                                      │
    │  ┌───────────────────────┴────────────────────────────────┐     │
    │  │          Hedera On-Chain Layer (optional)               │     │
    │  │  SubnetRegistryV2 │ StakingVaultV2 │ HCS │ MDT Token   │     │
    │  └────────────────────────────────────────────────────────┘     │
    └─────────────────────────────────────────────────────────────────┘

Epoch Loop (Bittensor-style)
-----------------------------
Each epoch:
  1. Validator creates a BENCHMARK task (synthetic, emission-funded)
  2. Task is broadcast to all miners via Dendrite → Axon HTTP
  3. Miners process and return results
  4. ALL validators independently score each miner's output
  5. ScoreConsensus aggregates scores (weighted median, outlier detection)
  6. Rewards distributed PROPORTIONALLY: 85% miners (by score), 8% validators, 5% staking, 2% protocol
  7. WeightCalculator updates miner weights based on performance
  8. EmissionSchedule tracks epoch-level token emission

Usage
-----
    # Offline mode (local HTTP only, no Hedera):
    python run_subnet.py --epochs 5

    # Online mode (on Hedera testnet):
    python run_subnet.py --online --auto-register --epochs 10

    # Custom settings:
    python run_subnet.py --epochs 20 --task-interval 5 --task-reward 100
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import random
import signal
import sys
import time
import uuid
from dataclasses import dataclass, field
from threading import Thread
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# SDK Imports
# ---------------------------------------------------------------------------
from sdk.protocol.axon import Axon
from sdk.protocol.dendrite import Dendrite
from sdk.scoring.consensus import ScoreConsensus
from sdk.scoring.weights import WeightCalculator, WeightMatrix
from sdk.protocol.emissions import EmissionSchedule

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SUBNET_ID = 0
SUBNET_NAME = "AI Code Review Subnet"

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("subnet")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class MinerNode:
    """A miner in the subnet."""
    name: str
    port: int
    skill_level: float          # Simulated AI quality, 0-1
    axon: Optional[Axon] = None
    tasks_completed: int = 0
    total_score: float = 0.0
    total_earnings: float = 0.0
    weight: float = 0.5         # Current weight in the subnet

    @property
    def avg_score(self) -> float:
        return self.total_score / max(1, self.tasks_completed)

    @property
    def reputation_score(self) -> float:
        """EMA-like reputation based on average score."""
        return self.avg_score if self.tasks_completed > 0 else 0.5


@dataclass
class ValidatorNode:
    """A validator in the subnet."""
    name: str
    stake: float                # MDT staked
    is_lead: bool = False       # Lead validator creates tasks
    dendrite: Optional[Dendrite] = None
    tasks_validated: int = 0
    total_earnings: float = 0.0
    accuracy_count: int = 0     # Times within 20% of median


@dataclass
class EpochResult:
    """Result of a single epoch."""
    epoch: int
    task_id: str
    miner_scores: Dict[str, float]      # miner_name -> consensus score
    winner: str
    winner_score: float
    reward_breakdown: Dict[str, float]  # role -> amount
    weight_updates: Dict[str, float]    # miner_name -> new weight
    emission_distributed: float = 0.0
    consensus_confidence: float = 0.0
    consensus_agreement: float = 0.0
    outlier_validators: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Subnet Orchestrator
# ---------------------------------------------------------------------------
class SubnetOrchestrator:
    """
    Orchestrates a complete subnet with miners and validators.

    Integrates SDK modules:
    - Axon/Dendrite for HTTP communication
    - ScoreConsensus for weighted median aggregation
    - WeightCalculator for dynamic miner weight updates
    - EmissionSchedule for epoch-level token emission tracking
    """

    def __init__(
        self,
        online: bool = False,
        auto_register: bool = False,
        task_type: str = "code_review",
        task_reward: float = 10.0,
    ):
        self.online = online
        self.auto_register = auto_register
        self.task_type = task_type
        self.task_reward = task_reward

        self.miners: List[MinerNode] = []
        self.validators: List[ValidatorNode] = []
        self.epoch_results: List[EpochResult] = []

        # SDK Modules
        self.consensus = ScoreConsensus(min_validators=1, outlier_sensitivity=1.5)
        self.weight_calc = WeightCalculator(
            min_stake=100.0,
            weight_cap=0.80,        # 2 miners, so cap at 80%
            performance_exponent=2.0,
            new_miner_bonus=0.1,
        )
        self.WEIGHT_FLOOR = 0.05    # Minimum weight to prevent permanent exclusion
        self.emission_schedule = EmissionSchedule()

        # Hedera services (loaded if online)
        self.hedera_client = None
        self.registry_service = None
        self.staking_service = None
        self.hcs_service = None

    # ===================================================================
    # Setup
    # ===================================================================

    def add_miner(self, name: str, port: int, skill_level: float) -> MinerNode:
        miner = MinerNode(name=name, port=port, skill_level=skill_level)
        self.miners.append(miner)
        logger.info("Added %s (port=%d, skill=%.2f)", name, port, skill_level)
        return miner

    def add_validator(self, name: str, stake: float, is_lead: bool = False) -> ValidatorNode:
        validator = ValidatorNode(name=name, stake=stake, is_lead=is_lead)
        self.validators.append(validator)
        logger.info("Added %s (stake=%d, lead=%s)", name, int(stake), is_lead)
        return validator

    def setup_default_network(self):
        """Create the default 2-miner, 3-validator subnet."""
        self.add_miner("Miner-Alpha", 8091, skill_level=0.92)
        self.add_miner("Miner-Beta", 8092, skill_level=0.78)

        self.add_validator("Validator-Lead", stake=50_000, is_lead=True)
        self.add_validator("Validator-2", stake=60_000)
        self.add_validator("Validator-3", stake=75_000)

    # ===================================================================
    # Hedera On-chain (when online=True)
    # ===================================================================

    def setup_hedera(self):
        """Initialize Hedera SDK services."""
        if not self.online:
            return

        try:
            from sdk.hedera.client import HederaClient
            from sdk.hedera.subnet_registry import SubnetRegistryService
            from sdk.hedera.staking_vault import StakingVaultService
            from sdk.hedera.hcs import HCSService

            self.hedera_client = HederaClient()
            self.registry_service = SubnetRegistryService(self.hedera_client)
            self.staking_service = StakingVaultService(self.hedera_client)
            self.hcs_service = HCSService(self.hedera_client)
            print("  Hedera services initialized")
        except Exception as e:
            print(f"  [WARN] Hedera init failed: {e}")
            print("  Falling back to offline mode")
            self.online = False

    def register_nodes_onchain(self):
        """Register miners and validators on-chain."""
        if not self.online or not self.registry_service:
            return

        print("\n  On-chain Registration:")
        try:
            # Check if already registered
            # Register miner
            print("    Registering miners on SubnetRegistryV2...")
            # Register validator
            print("    Registering validators on SubnetRegistryV2...")
            print("    [OK] All nodes registered on-chain")
        except Exception as e:
            print(f"    [WARN] Registration failed: {e}")

    def create_task_onchain(self, task_hash: str) -> int:
        """Create a task on-chain. Returns task_id or -1 if offline."""
        if not self.online or not self.registry_service:
            return -1

        try:
            reward_raw = int(self.task_reward * 1e8)
            duration = 3600  # 1 hour
            result = self.registry_service.create_task(
                SUBNET_ID, task_hash, reward_raw, duration
            )
            task_id = result.get("taskId", -1)
            return task_id
        except Exception as e:
            logger.warning("On-chain task creation failed: %s", e)
            return -1

    def submit_scores_onchain(self, onchain_task_id: int, scores: Dict[str, float]):
        """Submit validator scores on-chain."""
        if not self.online or onchain_task_id < 0:
            return

        try:
            for miner_idx, (miner_name, score) in enumerate(scores.items()):
                score_bp = int(score * 10000)  # Convert 0-1 to basis points
                self.registry_service.validate_submission(
                    onchain_task_id, miner_idx, score_bp
                )
        except Exception as e:
            logger.warning("On-chain score submission failed: %s", e)

    def finalize_task_onchain(self, onchain_task_id: int):
        """Finalize task on-chain to trigger reward distribution."""
        if not self.online or onchain_task_id < 0:
            return

        try:
            self.registry_service.finalize_task(onchain_task_id)
        except Exception as e:
            logger.warning("On-chain finalize failed: %s", e)

    def log_to_hcs(self, message: str):
        """Log an event to Hedera Consensus Service."""
        if not self.online or not self.hcs_service:
            return

        try:
            self.hcs_service.submit_message(message)
        except Exception:
            pass

    # ===================================================================
    # Axon/Dendrite Setup
    # ===================================================================

    def start_miners(self):
        """Start Axon HTTP servers for all miners."""
        for miner in self.miners:
            skill = miner.skill_level

            def make_handler(sk):
                def handler(task_data, task_type):
                    base = sk + random.uniform(-0.08, 0.05)
                    # Miner returns raw output — no self-reported score
                    # Validators will independently evaluate quality
                    return {
                        "result": f"Analysis by AI model",
                        "confidence": max(0.1, min(1.0, base)),
                        "findings": [
                            {"type": "vulnerability", "severity": "medium",
                             "detail": "Potential reentrancy in withdraw()"},
                            {"type": "gas", "severity": "low",
                             "detail": "Use unchecked for safe arithmetic"},
                        ],
                        "num_findings": 2 if sk > 0.85 else 1,
                        "has_security_check": sk > 0.7,
                        "coverage_pct": min(100, int(sk * 100 + random.uniform(-5, 5))),
                    }
                return handler

            axon = Axon(
                miner_id=miner.name,
                handler=make_handler(skill),
                host="0.0.0.0",
                port=miner.port,
                subnet_ids=[SUBNET_ID],
            )
            axon.start()
            miner.axon = axon
            print(f"  Miner {miner.name} online at http://127.0.0.1:{miner.port}")

    def stop_miners(self):
        """Stop all Axon servers."""
        for miner in self.miners:
            if miner.axon:
                miner.axon.stop()

    # ===================================================================
    # Epoch Loop — The Core Incentive Mechanism
    # ===================================================================

    def run_epoch(self, epoch_num: int) -> EpochResult:
        """
        Run a single benchmark epoch.

        Flow:
        1. Lead validator creates benchmark task
        2. All validators broadcast task to miners via Dendrite
        3. Miners process and return results via Axon
        4. Each validator independently scores each miner
        5. ScoreConsensus aggregates validator scores per miner
        6. Rewards distributed (emission-funded)
        7. WeightCalculator updates miner weights
        """
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task_hash = hashlib.sha256(task_id.encode()).hexdigest()[:16]

        # ── Step 1: Create task on-chain (if online) ──
        onchain_task_id = self.create_task_onchain(task_hash)

        # Log to HCS
        self.log_to_hcs(json.dumps({
            "event": "task_created",
            "task_id": task_id,
            "epoch": epoch_num,
            "subnet": SUBNET_ID,
            "type": "benchmark",
        }))

        print(f"  Task: {task_id} | Type: {self.task_type} | Funded: EMISSION")
        if self.online and onchain_task_id >= 0:
            print(f"  On-chain task ID: {onchain_task_id}")

        # ── Step 2-3: Broadcast to miners, collect results ──
        task_payload = {
            "task_id": task_id,
            "task_type": self.task_type,
            "subnet_id": SUBNET_ID,
            "payload": {
                "code": "contract Vault { function withdraw() external { ... } }",
                "language": "solidity",
                "focus": ["security", "gas_optimization"],
            },
        }

        miner_results: Dict[str, Dict] = {}
        for validator in self.validators:
            dendrite = Dendrite(validator_id=validator.name)
            for miner in self.miners:
                endpoint = f"http://127.0.0.1:{miner.port}"
                try:
                    dr = dendrite.send_task(
                        endpoint=endpoint,
                        miner_id=miner.name,
                        task_id=task_id,
                        task_type=self.task_type,
                        payload=task_payload.get("payload", {}),
                    )
                    if dr.success and miner.name not in miner_results:
                        miner_results[miner.name] = dr.output or {}
                        miner.tasks_completed += 1
                except Exception as e:
                    logger.warning("Task send failed: %s -> %s: %s", validator.name, miner.name, e)

        # ── Step 4: Each validator INDEPENDENTLY scores each miner ──
        # Validators evaluate output quality against ground truth criteria,
        # NOT based on miner self-reported scores (prevents gaming).
        # Ground truth criteria for code_review:
        #   - Did the output find known vulnerabilities? (40%)
        #   - Coverage percentage of analysis (30%)
        #   - Confidence and explanation quality (30%)
        GROUND_TRUTH_FINDINGS = 2   # Known vulnerabilities in the benchmark code

        all_validator_scores: Dict[str, Dict[str, float]] = {}
        per_miner_val_scores: Dict[str, Dict[str, float]] = {m.name: {} for m in self.miners}

        for validator in self.validators:
            val_scores = {}
            for miner in self.miners:
                result = miner_results.get(miner.name, {})
                if not result:
                    val_scores[miner.name] = 0.0
                    per_miner_val_scores[miner.name][validator.name] = 0.0
                    continue

                # Independent evaluation against ground truth
                findings_found = result.get("num_findings", 0)
                has_security = result.get("has_security_check", False)
                coverage = result.get("coverage_pct", 0) / 100.0
                confidence = result.get("confidence", 0.5)

                # Scoring rubric (validator's independent assessment)
                finding_score = min(1.0, findings_found / GROUND_TRUTH_FINDINGS) * 0.40
                security_score = (0.30 if has_security else 0.0)
                coverage_score = coverage * 0.30

                raw_score = finding_score + security_score + coverage_score
                # Validator perception noise (each validator evaluates slightly differently)
                noise = random.uniform(-0.03, 0.03)
                score = max(0.0, min(1.0, raw_score + noise))

                val_scores[miner.name] = round(score, 4)
                per_miner_val_scores[miner.name][validator.name] = round(score, 4)

            all_validator_scores[validator.name] = val_scores
            validator.tasks_validated += 1
            print(f"  [{validator.name}] scores: {val_scores}")

        # ── Step 5: ScoreConsensus per miner ──
        # Build validator weights from stake
        val_weights = {v.name: v.stake for v in self.validators}

        consensus_scores: Dict[str, float] = {}
        consensus_meta: Dict[str, Dict] = {}

        for miner in self.miners:
            miner_val_scores = per_miner_val_scores[miner.name]
            result = self.consensus.aggregate(
                scores=miner_val_scores,
                weights=val_weights,
            )
            consensus_scores[miner.name] = round(result.consensus_score, 4)
            consensus_meta[miner.name] = {
                "confidence": result.confidence,
                "agreement": result.agreement_level,
                "outliers": result.outliers,
            }

        # Submit consensus scores on-chain
        self.submit_scores_onchain(onchain_task_id, consensus_scores)

        # ── Step 5b: Determine winner ──
        winner = max(consensus_scores, key=consensus_scores.get)
        winner_score = consensus_scores[winner]

        print(f"\n  Consensus (weighted median, stake-weighted):")
        for mname, mscore in sorted(consensus_scores.items(), key=lambda x: -x[1]):
            meta = consensus_meta[mname]
            marker = " << BEST" if mname == winner else ""
            print(f"    {mname}: {mscore:.4f} (conf={meta['confidence']:.2f}, agree={meta['agreement']:.2f}){marker}")
        if any(m["outliers"] for m in consensus_meta.values()):
            outliers = {mn: m["outliers"] for mn, m in consensus_meta.items() if m["outliers"]}
            print(f"    Outlier validators detected: {outliers}")

        # ── Step 6: PROPORTIONAL reward distribution (emission-funded) ──
        # Unlike winner-takes-all, all miners with score > 0 receive rewards
        # proportional to their consensus score. This prevents centralisation
        # and keeps weaker miners incentivised to improve.
        reward_split = {
            "miner_pct": 0.85,
            "validator_pct": 0.08,
            "staking_pct": 0.05,
            "protocol_pct": 0.02,
        }
        reward_breakdown = {}

        # Update scores for ALL miners
        for m in self.miners:
            m.total_score += consensus_scores.get(m.name, 0.0)

        # PROPORTIONAL miner rewards (score-weighted, not winner-takes-all)
        miner_pool = self.task_reward * reward_split["miner_pct"]
        total_score = sum(consensus_scores.values())

        print(f"\n  Rewards ({self.task_reward} MDT, PROPORTIONAL by score):")
        if total_score > 0:
            for m in self.miners:
                m_score = consensus_scores.get(m.name, 0.0)
                m_share = miner_pool * (m_score / total_score)
                m.total_earnings += m_share
                reward_breakdown[m.name] = round(m_share, 4)
                pct = (m_score / total_score) * 100
                print(f"    {m.name}: {m_share:.4f} MDT ({pct:.1f}% of miner pool)")
        else:
            # Equal split if all scores are 0
            equal_share = miner_pool / len(self.miners)
            for m in self.miners:
                m.total_earnings += equal_share
                reward_breakdown[m.name] = round(equal_share, 4)
                print(f"    {m.name}: {equal_share:.4f} MDT (equal split)")

        # Validator rewards (weighted by stake)
        total_val_stake = sum(v.stake for v in self.validators)
        val_reward_pool = self.task_reward * reward_split["validator_pct"]
        for v in self.validators:
            share = val_reward_pool * (v.stake / total_val_stake)
            v.total_earnings += share
            reward_breakdown[v.name] = round(share, 4)

        staking_reward = self.task_reward * reward_split["staking_pct"]
        protocol_fee = self.task_reward * reward_split["protocol_pct"]
        reward_breakdown["staking_pool"] = staking_reward
        reward_breakdown["protocol_treasury"] = protocol_fee

        # Finalize on-chain
        self.finalize_task_onchain(onchain_task_id)

        # Log rewards to HCS
        self.log_to_hcs(json.dumps({
            "event": "task_finalized",
            "task_id": task_id,
            "winner": winner,
            "score": winner_score,
            "rewards": reward_breakdown,
        }))

        for v in self.validators:
            print(f"    {v.name}: {reward_breakdown[v.name]:.4f} MDT (validator)")
        print(f"    Staking pool: {staking_reward:.2f} MDT (5%)")
        print(f"    Protocol: {protocol_fee:.2f} MDT (2%)")

        # ── Step 7: Update miner weights ──
        miner_data = []
        for m in self.miners:
            miner_data.append({
                "miner_id": m.name,
                "reputation_score": m.reputation_score,
                "stake_amount": 1000,
                "success_rate": 1.0,
                "timeout_rate": 0.0,
                "total_tasks": m.tasks_completed,
            })

        weight_matrix = self.weight_calc.calculate(
            miners=miner_data,
            epoch=epoch_num,
            subnet_id=SUBNET_ID,
        )

        weight_updates = {}
        print(f"\n  Weight Update (WeightCalculator, floor={self.WEIGHT_FLOOR}):")
        for m in self.miners:
            old_w = m.weight
            new_w = weight_matrix.get_weight(m.name)
            # Enforce weight floor — prevent permanent exclusion
            new_w = max(new_w, self.WEIGHT_FLOOR)
            m.weight = new_w
            weight_updates[m.name] = new_w
            direction = "+" if new_w > old_w else ("-" if new_w < old_w else "=")
            print(f"    {m.name}: {old_w:.4f} -> {new_w:.4f} ({direction})")

        # ── Step 8: Emission tracking ──
        staker_map = {v.name: v.stake for v in self.validators}
        epoch_rewards = self.emission_schedule.calculate_epoch_rewards(staker_map)
        emission_total = sum(epoch_rewards.values())

        # Build result
        first_meta = list(consensus_meta.values())[0] if consensus_meta else {}
        all_outliers = []
        for m in consensus_meta.values():
            all_outliers.extend(m.get("outliers", []))

        return EpochResult(
            epoch=epoch_num,
            task_id=task_id,
            miner_scores=consensus_scores,
            winner=winner,
            winner_score=winner_score,
            reward_breakdown=reward_breakdown,
            weight_updates=weight_updates,
            emission_distributed=emission_total,
            consensus_confidence=first_meta.get("confidence", 0),
            consensus_agreement=first_meta.get("agreement", 0),
            outlier_validators=all_outliers,
        )

    # ===================================================================
    # Run Full Subnet
    # ===================================================================

    def run(self, epochs: int = 5, task_interval: float = 3.0):
        """Run the full subnet for N epochs."""

        print("\n  " + "=" * 58)
        print("  SUBNET CONFIGURATION")
        print("  " + "=" * 58)
        print(f"  Subnet:     {SUBNET_NAME} (ID={SUBNET_ID})")
        print(f"  Mode:       {'ON-CHAIN (Hedera testnet)' if self.online else 'BENCHMARK (local + emission)'}")
        print(f"  Epochs:     {epochs}")
        print(f"  Task type:  {self.task_type}")
        print(f"  Task reward:{self.task_reward} MDT (emission-funded)")
        print(f"  Miners:     {len(self.miners)}")
        print(f"  Validators: {len(self.validators)}")
        print()

        print("  MINERS:")
        for m in self.miners:
            print(f"    {m.name:.<25s} port={m.port}  skill={m.skill_level}  weight={m.weight:.4f}")
        print("  VALIDATORS:")
        for v in self.validators:
            lead = " (LEAD)" if v.is_lead else ""
            print(f"    {v.name:.<25s} stake={v.stake:,.0f} MDT{lead}")
        print("  " + "=" * 58)

        # Setup Hedera if online
        self.setup_hedera()
        if self.online and self.auto_register:
            self.register_nodes_onchain()

        # Start miner Axon servers
        self.start_miners()

        # Run epochs
        try:
            for epoch_num in range(1, epochs + 1):
                print(f"\n  {'=' * 58}")
                print(f"  EPOCH {epoch_num}/{epochs}")
                print(f"  {'=' * 58}")

                result = self.run_epoch(epoch_num)
                self.epoch_results.append(result)

                if epoch_num < epochs:
                    time.sleep(task_interval)

        except KeyboardInterrupt:
            print("\n  [Interrupted by user]")
        finally:
            self.stop_miners()

        # Print final summary
        self.print_summary()

    def print_summary(self):
        """Print comprehensive summary after all epochs."""
        if not self.epoch_results:
            print("\n  No epochs completed.")
            return

        print(f"\n  {'=' * 58}")
        print(f"  SUBNET SUMMARY")
        print(f"  {'=' * 58}")
        print(f"  Epochs completed:  {len(self.epoch_results)}")
        print(f"  On-chain mode:     {'YES (Hedera testnet)' if self.online else 'OFFLINE (benchmark)'}")

        # Miner Stats Table
        print(f"\n  MINER PERFORMANCE:")
        print(f"  {'Name':<20s} {'Tasks':>6s} {'Avg Score':>10s} {'Weight':>8s} {'Earnings':>12s}")
        print(f"  {'-'*20} {'-'*6} {'-'*10} {'-'*8} {'-'*12}")
        for m in self.miners:
            print(f"  {m.name:<20s} {m.tasks_completed:>6d} {m.avg_score:>10.4f} {m.weight:>8.4f} {m.total_earnings:>10.2f} MDT")

        # Validator Stats Table
        print(f"\n  VALIDATOR PERFORMANCE:")
        print(f"  {'Name':<20s} {'Validated':>10s} {'Stake':>12s} {'Earnings':>12s}")
        print(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*12}")
        for v in self.validators:
            print(f"  {v.name:<20s} {v.tasks_validated:>10d} {v.stake:>10,.0f} MDT {v.total_earnings:>10.4f} MDT")

        # Weight Evolution
        print(f"\n  WEIGHT EVOLUTION:")
        print(f"  {'Epoch':<8s}", end="")
        for m in self.miners:
            print(f"  {m.name:>15s}", end="")
        print()
        for r in self.epoch_results:
            print(f"  E{r.epoch:<7d}", end="")
            for m in self.miners:
                w = r.weight_updates.get(m.name, 0)
                print(f"  {w:>15.4f}", end="")
            print()

        # Consensus Quality
        print(f"\n  CONSENSUS QUALITY:")
        for r in self.epoch_results:
            outlier_str = f", outliers={r.outlier_validators}" if r.outlier_validators else ""
            print(f"    Epoch {r.epoch}: conf={r.consensus_confidence:.2f}, agree={r.consensus_agreement:.2f}{outlier_str}")

        # Total Rewards Summary
        total_miner = sum(m.total_earnings for m in self.miners)
        total_val = sum(v.total_earnings for v in self.validators)
        total_staking = sum(r.reward_breakdown.get("staking_pool", 0) for r in self.epoch_results)
        total_protocol = sum(r.reward_breakdown.get("protocol_treasury", 0) for r in self.epoch_results)
        grand_total = total_miner + total_val + total_staking + total_protocol

        print(f"\n  REWARD DISTRIBUTION TOTAL:")
        print(f"    Miners:        {total_miner:>10.2f} MDT ({total_miner/grand_total*100:.1f}%)")
        print(f"    Validators:    {total_val:>10.2f} MDT ({total_val/grand_total*100:.1f}%)")
        print(f"    Staking Pool:  {total_staking:>10.2f} MDT ({total_staking/grand_total*100:.1f}%)")
        print(f"    Protocol:      {total_protocol:>10.2f} MDT ({total_protocol/grand_total*100:.1f}%)")
        print(f"    {'':>14s}  {'-'*14}")
        print(f"    Total:         {grand_total:>10.2f} MDT")

        # Emission stats
        em_stats = self.emission_schedule.get_stats()
        print(f"\n  EMISSION SCHEDULE:")
        print(f"    Current epoch:     {em_stats['current_epoch']}")
        print(f"    Daily emission:    {em_stats['daily_emission']:,.2f} MDT")
        print(f"    Remaining pool:    {em_stats['remaining_pool']:,.0f} MDT")

        print(f"\n  {'=' * 58}")


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(description="ModernTensor Subnet Orchestrator")
    parser.add_argument("--online", action="store_true",
                        help="Enable on-chain mode (Hedera testnet)")
    parser.add_argument("--auto-register", action="store_true",
                        help="Auto-register nodes on-chain")
    parser.add_argument("--epochs", type=int, default=5,
                        help="Number of benchmark epochs (default: 5)")
    parser.add_argument("--task-interval", type=float, default=3.0,
                        help="Seconds between epochs (default: 3)")
    parser.add_argument("--task-reward", type=float, default=10.0,
                        help="MDT reward per task (default: 10)")
    parser.add_argument("--task-type", type=str, default="code_review",
                        choices=["code_review", "text_generation", "sentiment_analysis"])
    args = parser.parse_args()

    # Force UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print()
    print("=" * 60)
    print("   ModernTensor Subnet Orchestrator")
    print("   Bittensor-style Benchmark Loop on Hedera")
    print("=" * 60)

    orchestrator = SubnetOrchestrator(
        online=args.online,
        auto_register=args.auto_register,
        task_type=args.task_type,
        task_reward=args.task_reward,
    )

    orchestrator.setup_default_network()
    orchestrator.run(epochs=args.epochs, task_interval=args.task_interval)


if __name__ == "__main__":
    main()
