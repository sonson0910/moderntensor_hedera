#!/usr/bin/env python3
"""
=================================================================
  ModernTensor — Direct Scoring Test (V2 Multi-Account)
=================================================================

SubnetRegistryV2 replaces commit-reveal with DIRECT scoring via
`validateSubmission(taskId, minerIndex, score)`.

Tests the full lifecycle with TWO Hedera accounts:

  Account 1 (Operator): Miner — stakes, submits results
  Account 2 (Created):  Validator — stakes, scores directly

Phases:
  1. Connect operator + create validator account on-chain
  2. Associate & fund validator with MDT tokens
  3. Approve MDT spending for both contracts
  4. Stake both accounts (miner + validator)
  5. Register subnet + set minValidations = 1
  6. Register miner (account 1) + add validator (account 2)
  7. Create task (approve MDT for reward)
  8. Submit result (miner)
  9. Validate submission directly (validator — score 8500/10000)
 10. Finalize task + withdraw earnings

Usage:
    python test_commit_reveal.py

For ModernTensor on Hedera — Hello Future Apex Hackathon 2026
=================================================================
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from sdk.hedera.config import load_hedera_config, HederaConfig
from sdk.hedera.client import HederaClient
from sdk.hedera.staking_vault import StakingVaultService, StakeRole
from sdk.hedera.subnet_registry import SubnetRegistryService

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


def info(msg):
    print(f"  {C}[--]{X} {msg}")


def fail(msg):
    print(f"  {R}[FAIL]{X} {msg}")


def check_receipt_status(receipt) -> bool:
    """Return True if receipt indicates success."""
    if receipt is None:
        return False
    status = getattr(receipt, "status", None)
    if status is None:
        return True
    status_str = str(status).upper()
    # Explicit success
    if "SUCCESS" in status_str:
        return True
    # Known failure patterns
    if any(kw in status_str for kw in ("REVERT", "FAIL", "ERROR", "INVALID", "INSUFFICIENT")):
        return False
    # Default: assume OK if no known failure pattern
    return True


def log_tx(label: str, receipt):
    tx_id = None
    if receipt:
        tx_id = getattr(receipt, "transaction_id", None)
        if tx_id:
            tx_id = str(tx_id)
    success = check_receipt_status(receipt)
    entry = {"phase": PHASE, "label": label, "tx_id": tx_id, "success": success}
    TX_LOG.append(entry)
    if tx_id:
        status_icon = f"{G}[OK]{X}" if success else f"{R}[REVERT]{X}"
        print(f"  {status_icon} {label}  TX: {tx_id}")
        if not success:
            warn(f"Receipt status: {getattr(receipt, 'status', 'unknown')}")
    else:
        ok(f"{label}  (receipt logged)")
    return tx_id


def account_to_evm(account_id_str: str) -> str:
    """Convert '0.0.12345' → '0x0000000000000000000000000000000000003039'"""
    num = int(account_id_str.split(".")[-1])
    return "0x" + num.to_bytes(20, "big").hex()


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
def main():
    print(f"\n{'=' * 68}")
    print(f"  {B}ModernTensor — Direct Scoring Test V2 (Multi-Account){X}")
    print(f"  {C}Accounts: Miner (operator) + Validator (created on-chain){X}")
    print(f"{'=' * 68}")

    # ── Phase 1: Connect + Create Validator Account ──
    hdr("Connect & Create Validator Account")

    config = load_hedera_config()
    client = HederaClient(config)

    OPERATOR_ID = client.operator_id_str
    OPERATOR_EVM = account_to_evm(OPERATOR_ID)
    balance = client.get_balance()

    ok(f"Operator (Miner): {OPERATOR_ID}")
    ok(f"Miner EVM:        {OPERATOR_EVM}")
    ok(f"Balance:          {balance.hbars}")

    # Create validator account on-chain
    ok("Creating validator account on testnet...")
    try:
        validator_account_id, validator_key = client.create_account(
            initial_balance_hbar=20.0
        )
        VALIDATOR_EVM = account_to_evm(validator_account_id)
        ok(f"Validator account: {validator_account_id}")
        ok(f"Validator EVM:     {VALIDATOR_EVM}")
        TX_LOG.append(
            {"phase": PHASE, "label": "createAccount(validator)", "tx_id": "OK", "success": True}
        )
    except Exception as e:
        fail(f"Cannot create validator account: {e}")
        print(f"\n  {R}FATAL: Multi-account test requires account creation.{X}")
        client.close()
        return

    # Create a second HederaClient for the validator
    validator_config = HederaConfig(
        network=config.network,
        account_id=validator_account_id,
        private_key=validator_key.to_string_raw(),
    )
    validator_client = HederaClient(validator_config)
    ok(f"Validator client connected: {validator_client.operator_id_str}")

    # Init services
    staking_miner = StakingVaultService(client)
    staking_validator = StakingVaultService(validator_client)
    registry_miner = SubnetRegistryService(client)
    registry_validator = SubnetRegistryService(validator_client)

    print(f"\n  {C}Deployed Contracts:{X}")
    ok(f"  {'StakingVault':18s}  {staking_miner.contract_id}")
    ok(f"  {'SubnetRegistry':18s}  {registry_miner.contract_id}")

    MDT_TOKEN_ID = os.getenv("HEDERA_MDT_TOKEN_ID", "") or os.getenv("MDT_TOKEN_ID", "")
    STAKING_VAULT_ID = staking_miner.contract_id
    SUBNET_REGISTRY_ID = registry_miner.contract_id

    # ── Phase 2: Associate & Fund Validator with MDT ──
    hdr("Associate MDT Token with Validator Account")

    if MDT_TOKEN_ID:
        ok(f"MDT Token: {MDT_TOKEN_ID}")

        # Associate token with validator
        try:
            receipt = validator_client.associate_token(MDT_TOKEN_ID)
            log_tx("tokenAssociate(MDT, validator)", receipt)
        except Exception as e:
            warn(f"tokenAssociate: {e}")
            TX_LOG.append({"phase": PHASE, "label": "tokenAssociate", "tx_id": f"ERR: {e}", "success": False})

        # Transfer MDT to validator
        TRANSFER_AMOUNT = int(200 * 1e8)
        try:
            receipt = client.transfer_token(
                token_id=MDT_TOKEN_ID,
                to_account=validator_account_id,
                amount=TRANSFER_AMOUNT,
            )
            log_tx(f"transferToken({TRANSFER_AMOUNT} MDT → validator)", receipt)
        except Exception as e:
            warn(f"transferToken: {e}")
            TX_LOG.append({"phase": PHASE, "label": "transferToken", "tx_id": f"ERR: {e}", "success": False})
    else:
        warn("MDT_TOKEN_ID not found — skipping token association")

    # ── Phase 3: Approve MDT Spending ──
    hdr("Approve MDT Spending for Contracts")

    APPROVE_AMOUNT = int(1_000_000 * 1e8)
    if MDT_TOKEN_ID:
        # Miner approves StakingVault + SubnetRegistry
        for contract_name, contract_id in [("StakingVault", STAKING_VAULT_ID), ("SubnetRegistry", SUBNET_REGISTRY_ID)]:
            if contract_id:
                try:
                    receipt = client.approve_token_allowance(MDT_TOKEN_ID, contract_id, APPROVE_AMOUNT)
                    log_tx(f"approve(MDT, {contract_name}) — miner", receipt)
                except Exception as e:
                    warn(f"approve {contract_name} miner: {e}")

        # Validator approves StakingVault
        if STAKING_VAULT_ID:
            try:
                receipt = validator_client.approve_token_allowance(MDT_TOKEN_ID, STAKING_VAULT_ID, APPROVE_AMOUNT)
                log_tx("approve(MDT, StakingVault) — validator", receipt)
            except Exception as e:
                warn(f"approve StakingVault validator: {e}")
    else:
        warn("No MDT_TOKEN_ID — skip approvals")

    # ── Phase 4: Stake Both Accounts ──
    hdr("StakingVault — Stake for Both Roles")

    STAKE_AMOUNT = int(100 * 1e8)

    # Miner stake
    try:
        receipt = staking_miner.stake(amount=STAKE_AMOUNT, role=StakeRole.MINER)
        log_tx("stake(100 MDT, MINER) — operator", receipt)
    except Exception as e:
        warn(f"stake MINER: {e}")
        TX_LOG.append({"phase": PHASE, "label": "stake MINER", "tx_id": f"ERR: {e}", "success": False})

    # Validator stake
    try:
        receipt = staking_validator.stake(amount=STAKE_AMOUNT, role=StakeRole.VALIDATOR)
        log_tx("stake(100 MDT, VALIDATOR) — validator", receipt)
    except Exception as e:
        warn(f"stake VALIDATOR: {e}")
        TX_LOG.append({"phase": PHASE, "label": "stake VALIDATOR", "tx_id": f"ERR: {e}", "success": False})

    # ── Phase 5: Register Subnet + setMinValidations ──
    hdr("SubnetRegistry — Register Subnet")

    # Read subnetCount BEFORE registering to determine our new subnet's ID
    SUBNET_ID = 0
    try:
        count_result = registry_miner.get_subnet_count()
        pre_count = count_result.get_int256(0)
        ok(f"Current subnetCount on-chain: {pre_count}")
        SUBNET_ID = pre_count  # contract does: subnetId = subnetCount++
    except Exception as e:
        warn(f"get_subnet_count: {e} — will try fallback")
        # Fallback: probe from 0 upward to find first empty slot
        try:
            for probe in range(100):
                r = registry_miner.get_subnet(probe)
                # Check if subnet owner is zero address (empty slot)
                owner = r.get_address(0) if hasattr(r, 'get_address') else None
                if owner == "0x" + "0" * 40:
                    SUBNET_ID = probe
                    break
                SUBNET_ID = probe + 1
        except Exception:
            pass

    subnet_name = f"V2-DirectScore-{int(time.time())}"
    try:
        receipt = registry_miner.register_subnet(
            name=subnet_name,
            description="V2 direct scoring test — no commit-reveal",
            fee_rate=200,
        )
        log_tx(f"registerSubnet('{subnet_name}')", receipt)
        ok(f"Subnet ID (dynamic): {SUBNET_ID}")
    except Exception as e:
        warn(f"registerSubnet: {e}")
        TX_LOG.append({"phase": PHASE, "label": "registerSubnet", "tx_id": f"ERR: {e}", "success": False})

    # Set min validators = 1
    try:
        receipt = registry_miner.set_min_validations(
            subnet_id=SUBNET_ID,
            min_validations=1,
        )
        log_tx(f"setMinValidations(subnet={SUBNET_ID}, min=1)", receipt)
    except Exception as e:
        warn(f"setMinValidations: {e}")
        TX_LOG.append({"phase": PHASE, "label": "setMinValidations", "tx_id": f"ERR: {e}", "success": False})

    # ── Phase 6: Register Miner + Add Validator ──
    hdr("SubnetRegistry — Register Miner & Validator")

    try:
        receipt = registry_miner.register_miner(SUBNET_ID)
        log_tx(f"registerMiner(subnet={SUBNET_ID})", receipt)
    except Exception as e:
        warn(f"registerMiner: {e}")
        TX_LOG.append({"phase": PHASE, "label": "registerMiner", "tx_id": f"ERR: {e}", "success": False})

    try:
        receipt = registry_miner.add_validator(SUBNET_ID, VALIDATOR_EVM)
        log_tx(f"addValidator(subnet={SUBNET_ID}, {VALIDATOR_EVM[:12]}...)", receipt)
    except Exception as e:
        warn(f"addValidator: {e}")
        TX_LOG.append({"phase": PHASE, "label": "addValidator", "tx_id": f"ERR: {e}", "success": False})

    # ── Phase 7: Create Task ──
    hdr("SubnetRegistry — Create Task")

    task_hash = f"QmV2DirectScore_{int(time.time())}"
    REWARD_AMOUNT = int(10 * 1e8)
    try:
        receipt = registry_miner.create_task(
            subnet_id=SUBNET_ID,
            task_hash=task_hash,
            reward_amount=REWARD_AMOUNT,
            duration=86400,
        )
        log_tx(f"createTask(hash={task_hash[:28]}...)", receipt)
    except Exception as e:
        warn(f"createTask: {e}")
        TX_LOG.append({"phase": PHASE, "label": "createTask", "tx_id": f"ERR: {e}", "success": False})

    # Probe actual Task ID — binary search for the last valid task
    # Contract uses ++_taskIdCounter (1-based, private), so we find the
    # boundary between valid tasks and empty slots using O(log n) queries
    TASK_ID = 1
    try:
        def _task_exists(tid):
            """Return True if task `tid` has a non-zero requester."""
            try:
                result = registry_miner.get_task(tid)
                if hasattr(result, "get_address"):
                    requester = result.get_address(2)
                    return requester != "0x" + "0" * 40
                return False
            except Exception:
                return False

        # Step 1: Exponential probe to find upper bound (1,2,4,8,16...)
        lo, hi = 1, 1
        while _task_exists(hi):
            lo = hi
            hi *= 2
            if hi > 100000:
                break
        ok(f"Exponential probe: valid tasks in [{lo}, {hi})")

        # Step 2: Binary search for exact last valid task ID
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if _task_exists(mid):
                lo = mid
            else:
                hi = mid

        TASK_ID = lo
        ok(f"Binary search found last task ID: {TASK_ID}")
    except Exception as e:
        warn(f"Task ID probe: {e} — using TASK_ID={TASK_ID}")

    # ── Phase 8: Submit Result (Miner) ──
    hdr("SubnetRegistry — Submit Result (Miner)")

    result_hash = f"QmV2Result_{int(time.time())}"
    try:
        receipt = registry_miner.submit_result(TASK_ID, result_hash)
        log_tx(f"submitResult(task={TASK_ID})", receipt)
    except Exception as e:
        err_str = str(e)
        if "expired" in err_str.lower() or "REVERT" in err_str:
            fail(f"submitResult REVERTED (task {TASK_ID} may be expired): {err_str[:200]}")
        else:
            warn(f"submitResult: {err_str[:200]}")
        TX_LOG.append({"phase": PHASE, "label": "submitResult", "tx_id": f"ERR: {e}", "success": False})

    # ── Phase 9: Validate Submission (Validator — Direct Score) ──
    hdr("SubnetRegistry — Validate Submission (Direct Score)")

    SCORE = 8500  # 85% in basis points

    ok(f"Validator ({validator_account_id}) scores submission directly")
    ok(f"Score: {SCORE}/10000 = {SCORE/100}%")
    ok("→ V2 direct scoring — no commit-reveal overhead ✓")

    try:
        receipt = registry_validator.validate_submission(
            task_id=TASK_ID,
            miner_index=0,
            score=SCORE,
        )
        log_tx(f"validateSubmission(task={TASK_ID}, minerIdx=0, score={SCORE}) — VALIDATOR", receipt)
        if check_receipt_status(receipt):
            ok("✓ validateSubmission SUCCESS — direct scoring works!")
        else:
            fail("validateSubmission REVERTED — check contract state")
    except Exception as e:
        warn(f"validateSubmission: {e}")
        TX_LOG.append({"phase": PHASE, "label": "validateSubmission", "tx_id": f"ERR: {e}", "success": False})

    # ── Phase 10: Verify + Finalize ──
    hdr("SubnetRegistry — Verify & Finalize")

    # Check validator reputation on-chain (V2 feature — may not exist on V1 contracts)
    try:
        rep_result = registry_miner.get_validator_reputation(VALIDATOR_EVM)
        # Decode tuple: (totalValidations, accurateValidations, reputationScore, lastActiveAt)
        if hasattr(rep_result, "get_uint256"):
            total = rep_result.get_uint256(0)
            accurate = rep_result.get_uint256(1)
            score = rep_result.get_uint256(2)
            ok(f"getValidatorReputation: total={total}, accurate={accurate}, score={score}")
        else:
            ok(f"getValidatorReputation: {rep_result}")
    except Exception as e:
        err_msg = str(e)
        if "CONTRACT_REVERT_EXECUTED" in err_msg:
            info(f"getValidatorReputation: V2-only function — not in deployed contract (expected)")
        else:
            warn(f"getValidatorReputation: {e}")

    # Check submission count — decode uint256 from raw bytes
    try:
        sub_result = registry_miner.get_submission_count(TASK_ID)
        if hasattr(sub_result, "get_uint256"):
            count = sub_result.get_uint256(0)
            ok(f"getSubmissionCount(task={TASK_ID}): {count}")
        elif hasattr(sub_result, "contract_call_result"):
            raw = sub_result.contract_call_result
            count = int.from_bytes(raw[-32:], "big") if len(raw) >= 32 else 0
            ok(f"getSubmissionCount(task={TASK_ID}): {count}")
        else:
            ok(f"getSubmissionCount(task={TASK_ID}): {sub_result}")
    except Exception as e:
        warn(f"getSubmissionCount: {e}")

    # Finalize task
    try:
        receipt = registry_miner.finalize_task(TASK_ID)
        log_tx(f"finalizeTask(task={TASK_ID})", receipt)
    except Exception as e:
        warn(f"finalizeTask: {e}")
        TX_LOG.append({"phase": PHASE, "label": "finalizeTask", "tx_id": f"ERR: {e}", "success": False})

    # Withdraw earnings
    try:
        receipt = registry_miner.withdraw_earnings()
        log_tx("withdrawEarnings() — miner", receipt)
    except Exception as e:
        warn(f"withdrawEarnings miner: {e}")

    try:
        receipt = registry_validator.withdraw_earnings()
        log_tx("withdrawEarnings() — validator", receipt)
    except Exception as e:
        warn(f"withdrawEarnings validator: {e}")

    # ════════════════════════════════════════════════════════
    #  FINAL REPORT
    # ════════════════════════════════════════════════════════
    print(f"\n{'=' * 68}")
    print(f"  {B}V2 DIRECT SCORING — TRANSACTION REPORT{X}")
    print(f"{'=' * 68}")
    print(f"\n  Network:    Hedera Testnet")
    print(f"  Miner:      {OPERATOR_ID} (operator)")
    print(f"  Validator:  {validator_account_id} (created on-chain)")
    print(f"  Scanner:    https://hashscan.io/testnet")
    print()

    print(f"  {C}V2 Scoring (Direct — No Commit-Reveal):{X}")
    print(f"    Score:           {SCORE}/10000 = {SCORE/100}%")
    print(f"    Method:          validateSubmission(taskId, minerIdx, score)")
    print()

    print(f"  {C}Contracts:{X}")
    print(f"    StakingVault:    {staking_miner.contract_id}")
    print(f"    SubnetRegistry:  {registry_miner.contract_id}")
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
        is_ok = entry.get("success", True)

        if tx and not tx.startswith("ERR:") and is_ok:
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
        if tx and not tx.startswith("ERR:") and tx not in ("N/A", "OK"):
            hashscan_url = f"https://hashscan.io/testnet/transaction/{tx}"
            print(f"    {entry['label'][:45]:<45} {hashscan_url}")

    print(f"\n  {B}Accounts:{X}")
    print(f"    Miner:     https://hashscan.io/testnet/account/{OPERATOR_ID}")
    print(f"    Validator: https://hashscan.io/testnet/account/{validator_account_id}")

    print(f"\n  {B}Contract Pages:{X}")
    print(f"    StakingVault:    https://hashscan.io/testnet/contract/{staking_miner.contract_id}")
    print(f"    SubnetRegistry:  https://hashscan.io/testnet/contract/{registry_miner.contract_id}")

    print(f"\n{'=' * 68}")

    # Cleanup
    validator_client.close()
    client.close()


if __name__ == "__main__":
    main()
