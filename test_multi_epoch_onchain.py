#!/usr/bin/env python3
"""
=================================================================
  ModernTensor — Multi-Epoch On-Chain Integration Test
=================================================================

Tests a realistic multi-epoch lifecycle on Hedera testnet:

  Epoch 1: Subnet bootstrap + first task cycle
  Epoch 2: Second task with same subnet + miner/validator
  Epoch 3: Third task with updated fee rate & validation

Each epoch runs the FULL task lifecycle:
  create_task → submit_result → validate_submission → finalize_task

Tracks:
  - Cumulative TX hashes for HashScan verification
  - Task IDs per epoch
  - Earnings across epochs
  - Per-epoch scoring & finalization

Usage:
    python test_multi_epoch_onchain.py

For ModernTensor on Hedera — Hello Future Apex Hackathon 2026
=================================================================
"""

import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from sdk.hedera.config import load_hedera_config
from sdk.hedera.client import HederaClient
from sdk.hedera.staking_vault import StakingVaultService, StakeRole
from sdk.hedera.subnet_registry import SubnetRegistryService
from sdk.hedera.hcs import HCSService, ScoreSubmission

# ── Formatting ──
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
C = "\033[96m"
B = "\033[1m"
X = "\033[0m"

TX_LOG: list[dict] = []
PHASE = 0
NUM_EPOCHS = 3


def hdr(title):
    global PHASE
    PHASE += 1
    print(f"\n{'=' * 68}")
    print(f"  Phase {PHASE}  {B}{title}{X}")
    print(f"{'=' * 68}")


def ok(msg):
    print(f"  {G}[OK]{X} {msg}")


def warn(msg):
    print(f"  {Y}[!!]{X} {msg}")


def fail(msg):
    print(f"  {R}[FAIL]{X} {msg}")


def log_tx(label: str, receipt):
    tx_id = None
    if receipt:
        tx_id = getattr(receipt, "transaction_id", None)
        if tx_id:
            tx_id = str(tx_id)
    entry = {"phase": PHASE, "label": label, "tx_id": tx_id}
    TX_LOG.append(entry)
    if tx_id:
        ok(f"{label}  TX: {tx_id}")
    else:
        ok(f"{label}  (receipt logged)")
    return tx_id


def run_epoch(
    epoch: int,
    registry: SubnetRegistryService,
    hcs: HCSService,
    subnet_id: int,
    operator_id: str,
    operator_evm: str,
    score: int,
    reward_mdt: int,
):
    """Run a single epoch: create_task → submit → validate → finalize → withdraw."""
    epoch_label = f"Epoch {epoch}"

    # ── Create Task ──
    hdr(f"{epoch_label} — Create Task")
    task_hash = f"QmEpoch{epoch}_{int(time.time())}"
    try:
        receipt = registry.create_task(
            subnet_id=subnet_id,
            task_hash=task_hash,
            reward_amount=int(reward_mdt * 1e8),
            duration=86400,
        )
        log_tx(f"[E{epoch}] createTask(hash={task_hash[:24]}...)", receipt)
    except Exception as e:
        warn(f"[E{epoch}] createTask: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": f"[E{epoch}] createTask", "tx_id": f"ERR: {e}"}
        )

    # Infer task ID: epoch - 1 (0-indexed, sequential)
    task_id = epoch - 1

    # ── Submit Result ──
    hdr(f"{epoch_label} — Submit Result (miner)")
    result_hash = f"QmResult_E{epoch}_{int(time.time())}"
    try:
        receipt = registry.submit_result(task_id, result_hash)
        log_tx(f"[E{epoch}] submitResult(task={task_id})", receipt)
    except Exception as e:
        warn(f"[E{epoch}] submitResult: {e}")
        TX_LOG.append(
            {
                "phase": PHASE,
                "label": f"[E{epoch}] submitResult",
                "tx_id": f"ERR: {e}",
            }
        )

    # ── Validate Submission ──
    hdr(f"{epoch_label} — Validate Submission (score={score})")
    try:
        receipt = registry.validate_submission(
            task_id=task_id,
            miner_index=0,
            score=score,
        )
        log_tx(
            f"[E{epoch}] validateSubmission(task={task_id}, s={score})", receipt
        )
    except Exception as e:
        warn(f"[E{epoch}] validateSubmission: {e}")
        TX_LOG.append(
            {
                "phase": PHASE,
                "label": f"[E{epoch}] validateSubmission",
                "tx_id": f"ERR: {e}",
            }
        )

    # ── HCS Score Log ──
    hdr(f"{epoch_label} — HCS Score Log")
    try:
        score_sub = ScoreSubmission(
            task_id=f"onchain-epoch{epoch}-task{task_id}",
            miner_id="0.0.miner",
            validator_id=operator_id,
            score=score / 100.0,
            confidence=0.95,
            metrics={"epoch": epoch, "task_id": task_id},
        )
        hcs.submit_score(score_sub)
        ok(f"[E{epoch}] HCS score submitted")
        TX_LOG.append(
            {
                "phase": PHASE,
                "label": f"[E{epoch}] HCS.submitScore",
                "tx_id": "HCS message",
            }
        )
    except Exception as e:
        warn(f"[E{epoch}] HCS score: {e}")

    # ── Finalize Task ──
    hdr(f"{epoch_label} — Finalize Task")
    try:
        receipt = registry.finalize_task(task_id)
        log_tx(f"[E{epoch}] finalizeTask(task={task_id})", receipt)
    except Exception as e:
        warn(f"[E{epoch}] finalizeTask: {e}")
        TX_LOG.append(
            {
                "phase": PHASE,
                "label": f"[E{epoch}] finalizeTask",
                "tx_id": f"ERR: {e}",
            }
        )

    # ── Withdraw Earnings ──
    hdr(f"{epoch_label} — Withdraw Earnings")
    try:
        receipt = registry.withdraw_earnings()
        log_tx(f"[E{epoch}] withdrawEarnings()", receipt)
    except Exception as e:
        warn(f"[E{epoch}] withdrawEarnings: {e}")
        TX_LOG.append(
            {
                "phase": PHASE,
                "label": f"[E{epoch}] withdrawEarnings",
                "tx_id": f"ERR: {e}",
            }
        )


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
def main():
    print(f"\n{'=' * 68}")
    print(f"  {B}ModernTensor — Multi-Epoch On-Chain Integration Test{X}")
    print(f"  {C}{NUM_EPOCHS} epochs × full task lifecycle{X}")
    print(f"{'=' * 68}")

    # ── Phase 1: Connect ──
    hdr("Connect to Hedera Testnet")

    config = load_hedera_config()
    client = HederaClient(config)

    OPERATOR_ID = client.operator_id_str
    account_num = int(OPERATOR_ID.split(".")[-1])
    OPERATOR_EVM = "0x" + account_num.to_bytes(20, "big").hex()
    balance = client.get_balance()

    ok(f"Operator:  {OPERATOR_ID}")
    ok(f"EVM addr:  {OPERATOR_EVM}")
    try:
        bal_str = str(balance.hbars).encode("ascii", errors="replace").decode()
    except Exception:
        bal_str = str(balance.hbars)
    ok(f"Balance:   {bal_str}")

    # Init services
    staking = StakingVaultService(client)
    registry = SubnetRegistryService(client)
    hcs = HCSService(client)

    print(f"\n  {C}Deployed Contracts:{X}")
    for label, svc in [
        ("StakingVault", staking),
        ("SubnetRegistry", registry),
    ]:
        cid = svc.contract_id or "NOT SET"
        ok(f"  {label:18s}  {cid}")

    # ── Phase 2: Stake ──
    hdr("StakingVault — Stake as MINER + VALIDATOR")

    for role_name, role in [("MINER", StakeRole.MINER), ("VALIDATOR", StakeRole.VALIDATOR)]:
        try:
            receipt = staking.stake(amount=int(100 * 1e8), role=role)
            log_tx(f"stake(100 MDT, {role_name})", receipt)
        except Exception as e:
            warn(f"stake {role_name}: {e}")
            TX_LOG.append(
                {"phase": PHASE, "label": f"stake {role_name}", "tx_id": f"ERR: {e}"}
            )

    # ── Phase 3: Register Subnet ──
    hdr("SubnetRegistry — Register Subnet")

    subnet_name = f"MultiEpoch-{int(time.time())}"
    try:
        receipt = registry.register_subnet(
            name=subnet_name,
            description="Multi-epoch test subnet",
            fee_rate=300,
        )
        log_tx(f"registerSubnet('{subnet_name}')", receipt)
    except Exception as e:
        warn(f"registerSubnet: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "registerSubnet", "tx_id": f"ERR: {e}"}
        )

    # Determine subnet ID
    SUBNET_ID = 0
    try:
        count = registry.get_active_subnet_count()
        ok(f"Active subnet count: {count}")
        if count and hasattr(count, "get_uint256"):
            num = count.get_uint256(0)
            SUBNET_ID = max(0, num - 1)
            ok(f"Our subnet ID: {SUBNET_ID}")
    except Exception as e:
        warn(f"getActiveSubnetCount: {e}")

    # ── Phase 4: Register Miner ──
    hdr("SubnetRegistry — Register Miner")

    try:
        receipt = registry.register_miner(SUBNET_ID)
        log_tx(f"registerMiner(subnet={SUBNET_ID})", receipt)
    except Exception as e:
        warn(f"registerMiner: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "registerMiner", "tx_id": f"ERR: {e}"}
        )

    # ── Phase 5: Add Validator ──
    hdr("SubnetRegistry — Add Validator (self)")

    try:
        receipt = registry.add_validator(SUBNET_ID, OPERATOR_EVM)
        log_tx(f"addValidator(subnet={SUBNET_ID})", receipt)
    except Exception as e:
        warn(f"addValidator: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "addValidator", "tx_id": f"ERR: {e}"}
        )

    # ════════════════════════════════════════════════════════
    #  RUN EPOCHS
    # ════════════════════════════════════════════════════════
    epoch_configs = [
        {"epoch": 1, "score": 7500, "reward_mdt": 10},   # 75% score, 10 MDT
        {"epoch": 2, "score": 8500, "reward_mdt": 15},   # 85% score, 15 MDT
        {"epoch": 3, "score": 9500, "reward_mdt": 20},   # 95% score, 20 MDT
    ]

    print(f"\n{'═' * 68}")
    print(f"  {B}{C}Starting {NUM_EPOCHS} Epoch Cycles{X}")
    print(f"{'═' * 68}")

    for cfg in epoch_configs:
        print(f"\n{'─' * 68}")
        print(f"  {B}{Y}◆ EPOCH {cfg['epoch']}{X}  "
              f"score={cfg['score']}  reward={cfg['reward_mdt']} MDT")
        print(f"{'─' * 68}")

        run_epoch(
            epoch=cfg["epoch"],
            registry=registry,
            hcs=hcs,
            subnet_id=SUBNET_ID,
            operator_id=OPERATOR_ID,
            operator_evm=OPERATOR_EVM,
            score=cfg["score"],
            reward_mdt=cfg["reward_mdt"],
        )

    # ── Optional: Update Subnet Fee Rate Between Epochs ──
    hdr("Post-Epochs — Update Subnet Fee Rate")
    try:
        receipt = registry.update_subnet(
            subnet_id=SUBNET_ID,
            new_fee_rate=500,  # 5%
            new_status=1,      # ACTIVE
        )
        log_tx(f"updateSubnet(fee=500)", receipt)
    except Exception as e:
        warn(f"updateSubnet: {e}")

    # ════════════════════════════════════════════════════════
    #  FINAL REPORT
    # ════════════════════════════════════════════════════════
    print(f"\n{'=' * 68}")
    print(f"  {B}MULTI-EPOCH TRANSACTION REPORT{X}")
    print(f"{'=' * 68}")
    print(f"\n  Network: Hedera Testnet")
    print(f"  Operator: {OPERATOR_ID}")
    print(f"  Epochs:   {NUM_EPOCHS}")
    print(f"  Scanner:  https://hashscan.io/testnet")
    print()

    # Contracts
    print(f"  {C}Contracts:{X}")
    print(f"    StakingVault:    {staking.contract_id}")
    print(f"    SubnetRegistry:  {registry.contract_id}")
    print()

    # Transactions
    print(f"  {C}Transactions:{X}")
    print(f"  {'Phase':>5}  {'Operation':<55} {'TX ID'}")
    print(f"  {'─' * 5}  {'─' * 55} {'─' * 30}")

    success_count = 0
    error_count = 0

    for entry in TX_LOG:
        tx = entry["tx_id"] or "N/A"
        phase_num = entry["phase"]
        label = entry["label"]

        if tx and not tx.startswith("ERR:"):
            success_count += 1
            status = G + "[OK]  " + X
        else:
            error_count += 1
            status = R + "[ERR] " + X

        print(f"  {phase_num:>5}  {status}{label:<49} {tx}")

    print(f"\n  {'─' * 68}")
    print(
        f"  {G}Success: {success_count}{X}  |  "
        f"{R}Errors: {error_count}{X}  |  "
        f"Total: {len(TX_LOG)}"
    )
    print()

    # Per-epoch summary
    print(f"  {C}Per-Epoch Summary:{X}")
    for cfg in epoch_configs:
        e = cfg["epoch"]
        epoch_txs = [t for t in TX_LOG if t["label"].startswith(f"[E{e}]")]
        epoch_ok = sum(
            1
            for t in epoch_txs
            if t["tx_id"] and not t["tx_id"].startswith("ERR:")
        )
        print(
            f"    Epoch {e}: {epoch_ok}/{len(epoch_txs)} successful  "
            f"(score={cfg['score']}, reward={cfg['reward_mdt']} MDT)"
        )

    # HashScan links
    print(f"\n  {B}HashScan Links:{X}")
    for entry in TX_LOG:
        tx = entry["tx_id"]
        if tx and not tx.startswith("ERR:") and tx != "HCS message" and tx != "N/A":
            hashscan_url = f"https://hashscan.io/testnet/transaction/{tx}"
            print(f"    {entry['label'][:45]:<45} {hashscan_url}")

    print(f"\n  {B}Contract Pages:{X}")
    print(
        f"    StakingVault:    https://hashscan.io/testnet/contract/{staking.contract_id}"
    )
    print(
        f"    SubnetRegistry:  https://hashscan.io/testnet/contract/{registry.contract_id}"
    )

    print(f"\n{'=' * 68}")

    client.close()


if __name__ == "__main__":
    main()
