#!/usr/bin/env python3
"""
TERMINAL 4 — NETWORK MONITOR 🔴
=================================

Continuously checks health + stats of Miner and Validator nodes.
Displays a real-time dashboard for live network monitoring.

Usage:
    python demo/demo_monitor.py
    python demo/demo_monitor.py --miner http://localhost:8091 --interval 5
"""

import sys
import os
import json
import time
import argparse

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

# ── Terminal Colors & Styles ──
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
BLUE    = "\033[94m"
WHITE   = "\033[97m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def dashboard(miner_url: str, tick: int):
    """Fetch and display dashboard data."""
    clear_screen()

    print(f"""{BOLD}{RED}
  ╔════════════════════════════════════════════════════════════╗
  ║                                                            ║
  ║   🔴  {WHITE}NETWORK MONITOR{RED}  ───────────  Terminal 4             ║
  ║       {CYAN}ModernTensor on Hedera Testnet{RED}                       ║
  ║                                                            ║
  ╚════════════════════════════════════════════════════════════╝{RESET}
""")

    ts = time.strftime("%H:%M:%S")
    print(f"  {DIM}Time: {ts}  │  Refresh #{tick}{RESET}\n")

    # ── Miner Health ──
    print(f"  {BOLD}{CYAN}╭─ MINER NODE ───────────────────────────────────────────╮{RESET}")
    try:
        r = requests.get(f"{miner_url}/health", timeout=3)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status", "unknown")
            color = GREEN if status == "healthy" else YELLOW
            print(f"  │ {DIM}Status   :{RESET}  {color}● {status.upper()}{RESET}")
            print(f"  │ {DIM}Miner ID :{RESET}  {WHITE}{data.get('miner_id', '?')}{RESET}")
            print(f"  │ {DIM}Uptime   :{RESET}  {WHITE}{data.get('uptime', 0):.0f}s{RESET}")
            print(f"  │ {DIM}Endpoint :{RESET}  {WHITE}{miner_url}{RESET}")
        else:
            print(f"  │ {DIM}Status   :{RESET}  {RED}● HTTP {r.status_code}{RESET}")
    except requests.exceptions.ConnectionError:
        print(f"  │ {DIM}Status   :{RESET}  {RED}● OFFLINE{RESET}")
        print(f"  │ {DIM}Start Terminal 1: python run_miner.py --subnet 0{RESET}")
    except Exception as e:
        print(f"  │ {DIM}Status   :{RESET}  {RED}● ERROR: {e}{RESET}")
    print(f"  {CYAN}╰───────────────────────────────────────────────────────╯{RESET}")

    # ── Miner Info ──
    print(f"\n  {BOLD}{MAGENTA}╭─ MINER CAPABILITIES ──────────────────────────────────╮{RESET}")
    try:
        r = requests.get(f"{miner_url}/info", timeout=3)
        if r.status_code == 200:
            info = r.json()
            caps = info.get("capabilities", [])
            subnets = info.get("subnet_ids", [])
            tasks = info.get("tasks_processed", 0)

            print(f"  │ {DIM}Subnets      :{RESET}  {WHITE}{subnets}{RESET}")
            print(f"  │ {DIM}Capabilities :{RESET}  {WHITE}{', '.join(caps)}{RESET}")
            print(f"  │ {DIM}Processed    :{RESET}  {BOLD}{GREEN}{tasks}{RESET} tasks")

            # Stats
            stats = info.get("stats", {})
            if stats:
                processed = stats.get("tasks_processed", 0)
                success = stats.get("tasks_succeeded", 0)
                rate = (success / processed * 100) if processed > 0 else 0
                print(f"  │ {DIM}Success Rate :{RESET}  {WHITE}{rate:.0f}%{RESET}")
                print(f"  │ {DIM}Avg Latency  :{RESET}  {WHITE}{stats.get('avg_processing_time', 0):.1f}s{RESET}")
        else:
            print(f"  │ {DIM}Info unavailable{RESET}")
    except Exception:
        print(f"  │ {DIM}Miner not responding{RESET}")
    print(f"  {MAGENTA}╰───────────────────────────────────────────────────────╯{RESET}")

    # ── Network Overview ──
    print(f"\n  {BOLD}{GREEN}╭─ NETWORK STATE ────────────────────────────────────────╮{RESET}")
    print(f"  │ {DIM}Protocol  :{RESET}  {WHITE}ModernTensor v0.1.0{RESET}")
    print(f"  │ {DIM}Network   :{RESET}  {WHITE}Hedera Testnet{RESET}")
    print(f"  │ {DIM}AI Engine :{RESET}  {WHITE}Google Gemini 2.0 Flash{RESET}")
    print(f"  │ {DIM}Consensus :{RESET}  {WHITE}Proof-of-Quality (PoQ){RESET}")
    print(f"  │ {DIM}Token     :{RESET}  {WHITE}MDT (HTS){RESET}")

    # Check env for on-chain info
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
        acct = os.getenv("HEDERA_ACCOUNT_ID", "not set")
        net = os.getenv("HEDERA_NETWORK", "testnet")
        contract_id = os.getenv("HEDERA_SUBNET_REGISTRY_CONTRACT_ID", "—")
        hcs_reg = os.getenv("HCS_REGISTRATION_TOPIC_ID") or os.getenv("HEDERA_REGISTRATION_TOPIC_ID", "—")
        hcs_score = os.getenv("HCS_SCORING_TOPIC_ID") or os.getenv("HEDERA_SCORING_TOPIC_ID", "—")
        hcs_task = os.getenv("HCS_TASK_TOPIC_ID") or os.getenv("HEDERA_TASK_TOPIC_ID", "—")
        print(f"  │")
        print(f"  │ {DIM}Operator  :{RESET}  {WHITE}{acct}{RESET}")
        print(f"  │ {DIM}Network   :{RESET}  {WHITE}{net}{RESET}")
        print(f"  │ {DIM}Contract  :{RESET}  {WHITE}{contract_id}{RESET}")
        print(f"  │ {DIM}HCS Reg   :{RESET}  {WHITE}{hcs_reg}{RESET}")
        print(f"  │ {DIM}HCS Score :{RESET}  {WHITE}{hcs_score}{RESET}")
        print(f"  │ {DIM}HCS Task  :{RESET}  {WHITE}{hcs_task}{RESET}")
        if contract_id and contract_id != "—":
            print(f"  │ {DIM}→ https://hashscan.io/testnet/contract/{contract_id}{RESET}")
        if hcs_score and hcs_score != "—":
            print(f"  │ {DIM}→ https://hashscan.io/testnet/topic/{hcs_score}{RESET}")
    except Exception:
        pass

    print(f"  {GREEN}╰───────────────────────────────────────────────────────╯{RESET}")

    print(f"\n  {DIM}Auto-refreshing... Press Ctrl+C to stop{RESET}")


def main():
    parser = argparse.ArgumentParser(description="ModernTensor Network Monitor")
    parser.add_argument("--miner", default="http://localhost:8091", help="Miner URL")
    parser.add_argument("--interval", type=int, default=5, help="Refresh interval (seconds)")
    args = parser.parse_args()

    tick = 0
    try:
        while True:
            tick += 1
            dashboard(args.miner, tick)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\n  {YELLOW}Monitor stopped{RESET}\n")


if __name__ == "__main__":
    main()
