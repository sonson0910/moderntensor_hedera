#!/usr/bin/env python3
"""
=================================================================
  ModernTensor — Multi-Validator Escrow Test (On-Chain)
=================================================================

Tests the PaymentEscrow multi-validator consensus mechanism:

  Phase 1:  Connect & init services
  Phase 2:  Create escrow task
  Phase 3:  Add validator (self as single validator)
  Phase 4:  Submit result (miner)
  Phase 5:  Validate submission (score 9000)
  Phase 6:  Finalize escrow task
  Phase 7:  Create 2nd escrow task
  Phase 8:  Commit-reveal scoring on 2nd task
  Phase 9:  Dispute flow — open & resolve dispute
  Phase 10: Withdraw earnings
  Phase 11: Query contract state (totalTasks, getTask, etc.)

Tests PaymentEscrow-specific features:
  - Task lifecycle (create → submit → validate → finalize)
  - Commit-reveal scoring
  - Dispute resolution
  - Adaptive min validations
  - Platform fee mechanics

Usage:
    python test_multi_validator_escrow.py

For ModernTensor on Hedera — Hello Future Apex Hackathon 2026
=================================================================
"""

import os
import secrets
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from sdk.hedera.config import load_hedera_config
from sdk.hedera.client import HederaClient
from sdk.hedera.staking_vault import StakingVaultService, StakeRole
from sdk.hedera.payment_escrow import PaymentEscrowService

# ── Formatting ──
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
C = "\033[96m"
B = "\033[1m"
X = "\033[0m"

TX_LOG: list[dict] = []
PHASE = 0


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


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
def main():
    print(f"\n{'=' * 68}")
    print(f"  {B}ModernTensor — Multi-Validator Escrow Test{X}")
    print(f"  {C}PaymentEscrow consensus, disputes & commit-reveal{X}")
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
    ok(f"Balance:   {balance.hbars}")

    # Init services
    staking = StakingVaultService(client)
    escrow = PaymentEscrowService(client)

    print(f"\n  {C}Deployed Contracts:{X}")
    for label, svc in [
        ("StakingVault", staking),
        ("PaymentEscrow", escrow),
    ]:
        cid = svc.contract_id or "NOT SET"
        ok(f"  {label:18s}  {cid}")

    # ── Phase 2: Stake ──
    hdr("StakingVault — Stake as VALIDATOR")

    try:
        receipt = staking.stake(amount=int(100 * 1e8), role=StakeRole.VALIDATOR)
        log_tx("stake(100 MDT, VALIDATOR)", receipt)
    except Exception as e:
        warn(f"stake VALIDATOR: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "stake VALIDATOR", "tx_id": f"ERR: {e}"}
        )

    # ── Phase 3: Add Validator to Escrow ──
    hdr("PaymentEscrow — Add Validator")

    try:
        receipt = escrow.add_validator(OPERATOR_EVM)
        log_tx(f"escrow.addValidator({OPERATOR_EVM[:14]}...)", receipt)
    except Exception as e:
        warn(f"escrow.addValidator: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.addValidator", "tx_id": f"ERR: {e}"}
        )

    # Verify validator status
    try:
        is_val = escrow.is_validator(OPERATOR_EVM)
        ok(f"escrow.isValidator: {is_val}")
    except Exception as e:
        warn(f"escrow.isValidator: {e}")

    # ════════════════════════════════════════════════════════
    #  TASK 1: Standard Validate Flow
    # ════════════════════════════════════════════════════════

    # ── Phase 4: Create Escrow Task 1 ──
    hdr("PaymentEscrow — Create Task 1 (Standard)")

    task1_hash = f"QmEscrowTask1_{int(time.time())}"
    try:
        receipt = escrow.create_task(
            task_hash=task1_hash,
            reward_amount=int(10 * 1e8),  # 10 MDT
            duration=86400,
        )
        log_tx(f"escrow.createTask(hash={task1_hash[:24]}...)", receipt)
    except Exception as e:
        warn(f"escrow.createTask: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.createTask 1", "tx_id": f"ERR: {e}"}
        )

    TASK1_ID = 0

    # ── Phase 5: Submit Result for Task 1 ──
    hdr("PaymentEscrow — Submit Result (Task 1)")

    result1_hash = f"QmEscResult1_{int(time.time())}"
    try:
        receipt = escrow.submit_result(TASK1_ID, result1_hash)
        log_tx(f"escrow.submitResult(task={TASK1_ID})", receipt)
    except Exception as e:
        warn(f"escrow.submitResult: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.submitResult 1", "tx_id": f"ERR: {e}"}
        )

    # ── Phase 6: Validate Submission (Task 1) ──
    hdr("PaymentEscrow — Validate Submission (Task 1, score=9000)")

    try:
        receipt = escrow.validate_submission(
            task_id=TASK1_ID,
            miner_index=0,
            score=9000,
        )
        log_tx(f"escrow.validateSubmission(task={TASK1_ID}, s=9000)", receipt)
    except Exception as e:
        warn(f"escrow.validateSubmission: {e}")
        TX_LOG.append(
            {
                "phase": PHASE,
                "label": "escrow.validateSubmission 1",
                "tx_id": f"ERR: {e}",
            }
        )

    # ── Phase 7: Finalize Task 1 ──
    hdr("PaymentEscrow — Finalize Task 1")

    try:
        receipt = escrow.finalize_task(TASK1_ID)
        log_tx(f"escrow.finalizeTask(task={TASK1_ID})", receipt)
    except Exception as e:
        warn(f"escrow.finalizeTask: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.finalizeTask 1", "tx_id": f"ERR: {e}"}
        )

    # ════════════════════════════════════════════════════════
    #  TASK 2: Commit-Reveal Score Flow
    # ════════════════════════════════════════════════════════

    # ── Phase 8: Create Escrow Task 2 ──
    hdr("PaymentEscrow — Create Task 2 (Commit-Reveal)")

    task2_hash = f"QmEscrowTask2_{int(time.time())}"
    try:
        receipt = escrow.create_task(
            task_hash=task2_hash,
            reward_amount=int(15 * 1e8),  # 15 MDT
            duration=86400,
        )
        log_tx(f"escrow.createTask(hash={task2_hash[:24]}...)", receipt)
    except Exception as e:
        warn(f"escrow.createTask: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.createTask 2", "tx_id": f"ERR: {e}"}
        )

    TASK2_ID = 1

    # ── Phase 9: Submit Result for Task 2 ──
    hdr("PaymentEscrow — Submit Result (Task 2)")

    result2_hash = f"QmEscResult2_{int(time.time())}"
    try:
        receipt = escrow.submit_result(TASK2_ID, result2_hash)
        log_tx(f"escrow.submitResult(task={TASK2_ID})", receipt)
    except Exception as e:
        warn(f"escrow.submitResult: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.submitResult 2", "tx_id": f"ERR: {e}"}
        )

    # ── Phase 10: Commit Score for Task 2 ──
    hdr("PaymentEscrow — Commit Score (Task 2)")

    SCORE2 = 8000
    SALT2 = secrets.token_bytes(32)

    ok(f"Score: {SCORE2}  Salt (hex): {SALT2.hex()[:32]}...")

    try:
        commit_hash_result = escrow.get_commit_hash(score=SCORE2, salt=SALT2)
        ok(f"getCommitHash result: {commit_hash_result}")
    except Exception as e:
        warn(f"escrow.getCommitHash: {e}")

    try:
        receipt = escrow.commit_score(
            task_id=TASK2_ID,
            miner_index=0,
            commit_hash=SALT2,
        )
        log_tx(f"escrow.commitScore(task={TASK2_ID})", receipt)
    except Exception as e:
        warn(f"escrow.commitScore: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.commitScore 2", "tx_id": f"ERR: {e}"}
        )

    # ── Phase 11: Reveal Score for Task 2 ──
    hdr("PaymentEscrow — Reveal Score (Task 2)")

    try:
        receipt = escrow.reveal_score(
            task_id=TASK2_ID,
            miner_index=0,
            score=SCORE2,
            salt=SALT2,
        )
        log_tx(f"escrow.revealScore(task={TASK2_ID}, s={SCORE2})", receipt)
    except Exception as e:
        warn(f"escrow.revealScore: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.revealScore 2", "tx_id": f"ERR: {e}"}
        )

    # ── Phase 12: Finalize Task 2 ──
    hdr("PaymentEscrow — Finalize Task 2")

    try:
        receipt = escrow.finalize_task(TASK2_ID)
        log_tx(f"escrow.finalizeTask(task={TASK2_ID})", receipt)
    except Exception as e:
        warn(f"escrow.finalizeTask: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.finalizeTask 2", "tx_id": f"ERR: {e}"}
        )

    # ════════════════════════════════════════════════════════
    #  TASK 3: Dispute Flow
    # ════════════════════════════════════════════════════════

    # ── Phase 13: Create + Submit + Validate Task 3 ──
    hdr("PaymentEscrow — Task 3 (Dispute Flow)")

    task3_hash = f"QmDispute_{int(time.time())}"
    try:
        receipt = escrow.create_task(
            task_hash=task3_hash,
            reward_amount=int(5 * 1e8),  # 5 MDT
            duration=86400,
        )
        log_tx(f"escrow.createTask(hash={task3_hash[:20]}...)", receipt)
    except Exception as e:
        warn(f"escrow.createTask 3: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.createTask 3", "tx_id": f"ERR: {e}"}
        )

    TASK3_ID = 2

    # Submit
    result3_hash = f"QmDisputeResult_{int(time.time())}"
    try:
        receipt = escrow.submit_result(TASK3_ID, result3_hash)
        log_tx(f"escrow.submitResult(task={TASK3_ID})", receipt)
    except Exception as e:
        warn(f"escrow.submitResult 3: {e}")

    # Validate with low score
    try:
        receipt = escrow.validate_submission(
            task_id=TASK3_ID,
            miner_index=0,
            score=3000,  # Low score
        )
        log_tx(f"escrow.validateSubmission(task={TASK3_ID}, s=3000)", receipt)
    except Exception as e:
        warn(f"escrow.validateSubmission 3: {e}")

    # ── Phase 14: Open Dispute ──
    hdr("PaymentEscrow — Open Dispute (Task 3)")

    try:
        receipt = escrow.open_dispute(TASK3_ID)
        log_tx(f"escrow.openDispute(task={TASK3_ID})", receipt)
    except Exception as e:
        warn(f"escrow.openDispute: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.openDispute", "tx_id": f"ERR: {e}"}
        )

    # ── Phase 15: Resolve Dispute ──
    hdr("PaymentEscrow — Resolve Dispute (Task 3)")

    try:
        receipt = escrow.resolve_dispute(
            task_id=TASK3_ID,
            miner_index=0,
            new_score=7000,  # Re-scored
        )
        log_tx(f"escrow.resolveDispute(task={TASK3_ID}, newScore=7000)", receipt)
    except Exception as e:
        warn(f"escrow.resolveDispute: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.resolveDispute", "tx_id": f"ERR: {e}"}
        )

    # ════════════════════════════════════════════════════════
    #  QUERY & VERIFY STATE
    # ════════════════════════════════════════════════════════

    # ── Phase 16: Query Escrow State ──
    hdr("PaymentEscrow — Query Contract State")

    # Total tasks
    try:
        total = escrow.total_tasks()
        ok(f"totalTasks: {total}")
    except Exception as e:
        warn(f"totalTasks: {e}")

    # Get task info for each
    for tid in [TASK1_ID, TASK2_ID, TASK3_ID]:
        try:
            task_info = escrow.get_task(tid)
            ok(f"getTask({tid}): {task_info}")
        except Exception as e:
            warn(f"getTask({tid}): {e}")

    # Submission count for task 1
    try:
        sub_count = escrow.get_submission_count(TASK1_ID)
        ok(f"getSubmissionCount(task={TASK1_ID}): {sub_count}")
    except Exception as e:
        warn(f"getSubmissionCount: {e}")

    # Adaptive min validations
    try:
        adaptive = escrow.get_adaptive_min_validations(int(10 * 1e8))
        ok(f"getAdaptiveMinValidations(10 MDT): {adaptive}")
    except Exception as e:
        warn(f"getAdaptiveMinValidations: {e}")

    # ── Phase 17: Withdraw Earnings ──
    hdr("PaymentEscrow — Withdraw Earnings")

    try:
        receipt = escrow.withdraw_earnings()
        log_tx("escrow.withdrawEarnings()", receipt)
    except Exception as e:
        warn(f"escrow.withdrawEarnings: {e}")
        TX_LOG.append(
            {"phase": PHASE, "label": "escrow.withdrawEarnings", "tx_id": f"ERR: {e}"}
        )

    # ════════════════════════════════════════════════════════
    #  FINAL REPORT
    # ════════════════════════════════════════════════════════
    print(f"\n{'=' * 68}")
    print(f"  {B}MULTI-VALIDATOR ESCROW TRANSACTION REPORT{X}")
    print(f"{'=' * 68}")
    print(f"\n  Network: Hedera Testnet")
    print(f"  Operator: {OPERATOR_ID}")
    print(f"  Scanner:  https://hashscan.io/testnet")
    print()

    print(f"  {C}Test Flows:{X}")
    print(f"    Task 1: Standard validate → finalize")
    print(f"    Task 2: Commit-reveal → finalize")
    print(f"    Task 3: Low score → dispute → resolve")
    print()

    print(f"  {C}Contracts:{X}")
    print(f"    StakingVault:    {staking.contract_id}")
    print(f"    PaymentEscrow:   {escrow.contract_id}")
    print()

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

    # HashScan links
    print(f"\n  {B}HashScan Links:{X}")
    for entry in TX_LOG:
        tx = entry["tx_id"]
        if tx and not tx.startswith("ERR:") and tx != "N/A":
            hashscan_url = f"https://hashscan.io/testnet/transaction/{tx}"
            print(f"    {entry['label'][:45]:<45} {hashscan_url}")

    print(f"\n  {B}Contract Pages:{X}")
    print(
        f"    StakingVault:    https://hashscan.io/testnet/contract/{staking.contract_id}"
    )
    print(
        f"    PaymentEscrow:   https://hashscan.io/testnet/contract/{escrow.contract_id}"
    )

    print(f"\n{'=' * 68}")

    client.close()


if __name__ == "__main__":
    main()
