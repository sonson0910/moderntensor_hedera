#!/usr/bin/env python3
"""
🎬 ModernTensor — Demo Video: On-Chain Asset Verification
==========================================================

Verifies all 6 on-chain assets deployed on Hedera Testnet
via mirror node API. Designed for demo video recording.

Usage:
    python scripts/demo_video_e2e.py
"""

import json
import time
import sys

try:
    import requests
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

# ── Colors ──
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# ── On-chain asset IDs ──
ASSETS = {
    "SubnetRegistryV2": {"type": "contract", "id": "0.0.8101733"},
    "StakingVaultV2":   {"type": "contract", "id": "0.0.8101730"},
    "MDT Token":        {"type": "token",    "id": "0.0.7852345"},
    "HCS Governance":   {"type": "topic",    "id": "0.0.7852335"},
    "HCS Scoring":      {"type": "topic",    "id": "0.0.7852336"},
    "HCS Task":         {"type": "topic",    "id": "0.0.7852337"},
}

MIRROR = "https://testnet.mirrornode.hedera.com"


def banner():
    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════════════════════╗
║        ModernTensor — On-Chain Asset Verification        ║
║                  Hedera Testnet (LIVE)                    ║
╚══════════════════════════════════════════════════════════╝{RESET}
""")


def verify_contract(name: str, contract_id: str) -> bool:
    """Verify a smart contract exists on mirror node."""
    url = f"{MIRROR}/api/v1/contracts/{contract_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            evm = data.get("evm_address", "?")
            created = data.get("created_timestamp", "?")
            if isinstance(created, str) and "." in created:
                ts = float(created)
                created = time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts))
            print(f"  {GREEN}✓{RESET} {BOLD}{name}{RESET}")
            print(f"    ID:       {contract_id}")
            print(f"    EVM:      {evm}")
            print(f"    Created:  {created}")
            print(f"    {DIM}→ https://hashscan.io/testnet/contract/{contract_id}{RESET}")
            return True
        else:
            print(f"  {RED}✗{RESET} {name} — HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"  {RED}✗{RESET} {name} — {e}")
        return False


def verify_token(name: str, token_id: str) -> bool:
    """Verify an HTS token exists on mirror node."""
    url = f"{MIRROR}/api/v1/tokens/{token_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            symbol = data.get("symbol", "?")
            supply = int(data.get("total_supply", 0))
            decimals = int(data.get("decimals", 0))
            supply_human = supply / (10 ** decimals) if decimals else supply
            print(f"  {GREEN}✓{RESET} {BOLD}{name}{RESET}")
            print(f"    ID:       {token_id}")
            print(f"    Symbol:   {symbol}")
            print(f"    Supply:   {supply_human:,.0f} {symbol}")
            print(f"    Decimals: {decimals}")
            print(f"    {DIM}→ https://hashscan.io/testnet/token/{token_id}{RESET}")
            return True
        else:
            print(f"  {RED}✗{RESET} {name} — HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"  {RED}✗{RESET} {name} — {e}")
        return False


def verify_topic(name: str, topic_id: str) -> bool:
    """Verify an HCS topic exists on mirror node."""
    url = f"{MIRROR}/api/v1/topics/{topic_id}/messages?limit=1&order=desc"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            msgs = data.get("messages", [])
            # Also get topic info
            r2 = requests.get(f"{MIRROR}/api/v1/topics/{topic_id}", timeout=10)
            memo = ""
            if r2.status_code == 200:
                memo = r2.json().get("memo", "")
            msg_count = len(msgs)
            seq = msgs[0].get("sequence_number", "?") if msgs else 0
            print(f"  {GREEN}✓{RESET} {BOLD}{name}{RESET}")
            print(f"    ID:       {topic_id}")
            if memo:
                print(f"    Memo:     {memo}")
            print(f"    Latest:   seq #{seq}")
            print(f"    {DIM}→ https://hashscan.io/testnet/topic/{topic_id}{RESET}")
            return True
        else:
            print(f"  {RED}✗{RESET} {name} — HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"  {RED}✗{RESET} {name} — {e}")
        return False


def verify_account():
    """Verify operator account."""
    acct = "0.0.7851838"
    url = f"{MIRROR}/api/v1/accounts/{acct}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            balance_hbar = int(data.get("balance", {}).get("balance", 0)) / 1e8
            print(f"  {BOLD}Operator Account:{RESET} {acct}")
            print(f"  Balance: {GREEN}{balance_hbar:.2f} HBAR{RESET}")
            print(f"  {DIM}→ https://hashscan.io/testnet/account/{acct}{RESET}")
            print()
            return True
    except:
        pass
    return False


def main():
    banner()

    # Account info
    print(f"  {BOLD}{CYAN}── Account ──{RESET}")
    verify_account()

    # Verify all assets
    passed = 0
    total = len(ASSETS)

    print(f"  {BOLD}{CYAN}── Smart Contracts ──{RESET}\n")
    for name, info in ASSETS.items():
        if info["type"] == "contract":
            if verify_contract(name, info["id"]):
                passed += 1
            print()

    print(f"  {BOLD}{CYAN}── HTS Token ──{RESET}\n")
    for name, info in ASSETS.items():
        if info["type"] == "token":
            if verify_token(name, info["id"]):
                passed += 1
            print()

    print(f"  {BOLD}{CYAN}── HCS Topics ──{RESET}\n")
    for name, info in ASSETS.items():
        if info["type"] == "topic":
            if verify_topic(name, info["id"]):
                passed += 1
            print()

    # Summary
    color = GREEN if passed == total else YELLOW
    print(f"""
{BOLD}{color}╔══════════════════════════════════════════════════════════╗
║          VERIFICATION: {passed}/{total} ASSETS LIVE ON HEDERA            ║
╚══════════════════════════════════════════════════════════╝{RESET}
""")

    if passed == total:
        print(f"  {GREEN}All on-chain assets verified ✓{RESET}")
    else:
        print(f"  {YELLOW}Warning: {total - passed} asset(s) could not be verified{RESET}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
