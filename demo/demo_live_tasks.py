#!/usr/bin/env python3
"""
TERMINAL 3 — LIVE TASK SUBMISSION 🟡 (ON-CHAIN)
=================================================

Sends tasks to the Miner (Terminal 1), then:
  1) Creates task ON-CHAIN via SubnetRegistry.create_task()
  2) Sends task to Miner Axon via HTTP
  3) Submits result hash ON-CHAIN via SubnetRegistry.submit_result()
  4) Logs task via HCS (Hedera Consensus Service)
  5) Displays HashScan links for on-chain verification

Usage:
    python demo/demo_live_tasks.py --onchain        # Full on-chain
    python demo/demo_live_tasks.py                   # HTTP-only fallback
"""

import sys
import os
import json
import time
import hashlib
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import requests
except ImportError:
    print("Installing requests...")
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
ITALIC  = "\033[3m"
RESET   = "\033[0m"
BG_BLUE   = "\033[44m"
BG_GREEN  = "\033[42m"
BG_YELLOW = "\033[43m"

# ── On-chain state (populated if --onchain) ──
hedera_client = None
registry_service = None
hcs_service = None
onchain_mode = False
task_counter = 0  # on-chain task ID counter


def init_onchain():
    """Initialize Hedera client + services for on-chain mode."""
    global hedera_client, registry_service, hcs_service, onchain_mode

    print(f"\n  {BOLD}{CYAN}⛓️  Initializing ON-CHAIN mode...{RESET}")
    print(f"  {DIM}{'─' * 50}{RESET}")

    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    except ImportError:
        pass

    try:
        from sdk.hedera.client import HederaClient
        from sdk.hedera.subnet_registry import SubnetRegistryService
        from sdk.hedera.hcs import HCSService, TaskSubmission, ScoreSubmission

        hedera_client = HederaClient.from_env()
        registry_service = SubnetRegistryService(hedera_client)
        hcs_service = HCSService(hedera_client)

        acct_id = os.getenv("HEDERA_ACCOUNT_ID", "?")
        contract_id = registry_service.contract_id
        hcs_task_topic = hcs_service.task_topic_id
        hcs_scoring_topic = hcs_service.scoring_topic_id

        print(f"  {GREEN}✓{RESET} {BOLD}Hedera client connected{RESET}")
        print(f"    {DIM}Account     :{RESET}  {WHITE}{acct_id}{RESET}")
        print(f"    {DIM}Network     :{RESET}  {WHITE}{os.getenv('HEDERA_NETWORK', 'testnet')}{RESET}")
        print(f"    {DIM}Contract    :{RESET}  {WHITE}{contract_id or '(not deployed)'}{RESET}")
        print(f"    {DIM}HCS Task    :{RESET}  {WHITE}{hcs_task_topic or '(not set)'}{RESET}")
        print(f"    {DIM}HCS Scoring :{RESET}  {WHITE}{hcs_scoring_topic or '(not set)'}{RESET}")

        if not contract_id:
            print(f"\n  {YELLOW}⚠  SubnetRegistry contract not deployed{RESET}")
            print(f"     {DIM}Smart contract calls skipped — will use HCS for on-chain logging{RESET}")

        onchain_mode = True
        return True

    except Exception as e:
        print(f"  {RED}✗ On-chain init failed:{RESET} {e}")
        print(f"    {DIM}Falling back to HTTP-only mode{RESET}")
        onchain_mode = False
        return False


def banner():
    mode_label = "ON-CHAIN ⛓️" if onchain_mode else "HTTP-ONLY 📡"
    mode_color = GREEN if onchain_mode else YELLOW
    print(f"""
{BOLD}{YELLOW}
  ╔════════════════════════════════════════════════════════════╗
  ║                                                            ║
  ║   🟡  {WHITE}LIVE TASK SUBMISSION{YELLOW}  ─────────  Terminal 3         ║
  ║       {CYAN}ModernTensor on Hedera Network{YELLOW}                      ║
  ║       {mode_color}Mode: {mode_label}{YELLOW}                                     ║
  ║                                                            ║
  ╚════════════════════════════════════════════════════════════╝{RESET}
""")


def header(num, title, color=CYAN):
    line = f"  TASK {num}  │  {title}"
    pad = 58 - len(line) + 2
    print(f"""
  {BOLD}{color}╭{'─' * 58}╮
  │{line}{' ' * max(pad, 1)}│
  ╰{'─' * 58}╯{RESET}""")


def kv(key, value, indent=2):
    label = f"{key}".ljust(16)
    print(f"{' ' * indent}{DIM}{label}{RESET} {GREEN}{value}{RESET}")


def section_divider():
    print(f"\n  {DIM}{'━' * 58}{RESET}\n")


def onchain_create_task(task_type: str, payload: dict, reward_mdt: int = 10) -> dict:
    """
    Create task ON-CHAIN:
      1) SubnetRegistry.create_task() — creates on-chain task record
      2) HCS.create_task() — logs task to HCS topic
    Returns dict with on-chain references.
    """
    global task_counter
    result = {"onchain": False}

    task_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()

    # ── 1) SubnetRegistry — create_task() ──
    if registry_service and registry_service.contract_id:
        try:
            print(f"  {CYAN}⛓️  SubnetRegistry.createTask()...{RESET}")
            reward_amount = reward_mdt * 10**8  # MDT has 8 decimals
            receipt = registry_service.create_task(
                subnet_id=0,
                task_hash=task_hash,
                reward_amount=reward_amount,
                duration=3600,  # 1 hour
            )
            task_counter += 1
            result["contract_tx"] = True
            result["task_hash"] = task_hash
            result["onchain_task_id"] = task_counter
            print(f"  {GREEN}✓ Task created on-chain (SubnetRegistry){RESET}")
            print(f"    task_hash:     {task_hash[:32]}...")
            print(f"    reward:        {reward_mdt} MDT")
        except Exception as e:
            print(f"  {YELLOW}⚠ SubnetRegistry.createTask() failed: {e}{RESET}")
            result["contract_tx"] = False
    else:
        result["contract_tx"] = False

    # ── 2) HCS — log task creation ──
    if hcs_service and hcs_service.task_topic_id:
        try:
            from sdk.hedera.hcs import TaskSubmission
            task_msg = TaskSubmission(
                task_id=f"demo-{int(time.time())}",
                requester_id=os.getenv("HEDERA_ACCOUNT_ID", "demo"),
                task_type=task_type,
                prompt=json.dumps(payload, default=str)[:512],
                reward_amount=reward_mdt,
                deadline=int(time.time()) + 3600,
            )
            receipt = hcs_service.create_task(task_msg)
            seq = getattr(receipt, 'topic_sequence_number', None)
            result["hcs_sequence"] = seq
            result["hcs_topic"] = hcs_service.task_topic_id
            result["onchain"] = True
            print(f"  {GREEN}✓ Task logged to HCS{RESET}")
            if seq:
                print(f"    sequence:      #{seq}")
            print(f"    topic:         {hcs_service.task_topic_id}")
            hashscan = f"https://hashscan.io/testnet/topic/{hcs_service.task_topic_id}"
            print(f"    {DIM}→ {hashscan}{RESET}")
        except Exception as e:
            print(f"  {YELLOW}⚠ HCS task log failed: {e}{RESET}")

    return result


def onchain_submit_result(result_hash: str, task_id: int = 0) -> dict:
    """
    Submit result ON-CHAIN:
      1) SubnetRegistry.submit_result() — on-chain result submission
      2) HCS — log score/completion
    """
    info = {"onchain": False}

    # ── SubnetRegistry submission ──
    if registry_service and registry_service.contract_id and task_id > 0:
        try:
            print(f"  {CYAN}⛓️  SubnetRegistry.submitResult()...{RESET}")
            receipt = registry_service.submit_result(
                task_id=task_id,
                result_hash=result_hash,
            )
            info["contract_submit"] = True
            info["onchain"] = True
            print(f"  {GREEN}✓ Result submitted on-chain{RESET}")
            print(f"    result_hash:   {result_hash[:32]}...")
        except Exception as e:
            print(f"  {YELLOW}⚠ SubnetRegistry.submitResult() failed: {e}{RESET}")

    # ── HCS score logging ──
    if hcs_service and hcs_service.scoring_topic_id:
        try:
            from sdk.hedera.hcs import ScoreSubmission
            score_msg = ScoreSubmission(
                validator_id=os.getenv("HEDERA_ACCOUNT_ID", "demo"),
                miner_id="gemini-miner-001",
                task_id=f"demo-{task_id}",
                score=85.0,
                confidence=0.95,
                metrics={"latency_ms": 2000, "quality": 0.9},
            )
            receipt = hcs_service.submit_score(score_msg)
            seq = getattr(receipt, 'topic_sequence_number', None)
            info["hcs_score_seq"] = seq
            info["onchain"] = True
            print(f"  {GREEN}✓ Score logged to HCS{RESET}")
            if seq:
                print(f"    sequence:      #{seq}")
            hashscan = f"https://hashscan.io/testnet/topic/{hcs_service.scoring_topic_id}"
            print(f"    {DIM}→ {hashscan}{RESET}")
        except Exception as e:
            print(f"  {YELLOW}⚠ HCS score log failed: {e}{RESET}")

    return info


def send_task(miner_url: str, task_type: str, payload: dict, task_num: int) -> dict:
    """Send task to Miner Axon server via HTTP."""
    url = f"{miner_url}/task"
    body = {
        "task_id": f"demo-live-{task_num}-{int(time.time())}",
        "task_type": task_type,
        "payload": payload,
        "validator_id": "demo-presenter",
    }

    print(f"  {DIM}→ POST {url}{RESET}")
    print(f"  {DIM}  task_type: {task_type}{RESET}")

    t0 = time.time()
    try:
        resp = requests.post(url, json=body, timeout=60)
        elapsed = time.time() - t0
        data = resp.json()

        print(f"  {GREEN}← {resp.status_code} OK ({elapsed*1000:.0f}ms){RESET}")
        return data
    except requests.exceptions.ConnectionError:
        print(f"  {RED}✗ Connection refused — is Miner running on {miner_url}?{RESET}")
        print(f"  {DIM}  Start Terminal 1 first: python run_miner.py --subnet 0{RESET}")
        return {}
    except Exception as e:
        print(f"  {RED}✗ Error: {e}{RESET}")
        return {}


def show_result(result: dict, onchain_info: dict = None):
    """Display AI results + on-chain verification links."""
    output = result.get("output", result)

    if "analysis" in output:
        print(f"\n  {BOLD}📋 AI Analysis:{RESET}")
        analysis = output["analysis"]
        for line in analysis.split("\n")[:15]:
            print(f"  {line}")

    if "score" in output:
        score = float(output.get("score", 0))
        bar_len = int(score * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        color = GREEN if score >= 0.7 else YELLOW if score >= 0.4 else RED
        print(f"\n  {BOLD}Score:{RESET} {color}{bar} {score:.2f}{RESET}")

    if "confidence" in output:
        conf = float(output.get("confidence", 0))
        print(f"  {BOLD}Confidence:{RESET} {conf:.2f}")

    if "findings" in output:
        findings = output["findings"]
        if findings:
            print(f"\n  {BOLD}🔍 Findings ({len(findings)}):{RESET}")
            for f in findings[:5]:
                sev = f.get("severity", "info")
                icon = {"critical": "🔴", "warning": "🟡", "info": "🔵", "suggestion": "🟢"}.get(sev, "⚪")
                print(f"    {icon} [{sev.upper()}] {f.get('message', '')}")

    if "text" in output:
        print(f"\n  {BOLD}📝 Generated Text:{RESET}")
        text = output["text"]
        for line in text.split("\n")[:10]:
            print(f"  {line}")

    # Result hash
    result_hash = hashlib.sha256(
        json.dumps(output, sort_keys=True, default=str).encode()
    ).hexdigest()
    print(f"\n  {BOLD}🔗 Result Hash:{RESET} {result_hash[:48]}...")

    # On-chain verification links
    if onchain_info and onchain_info.get("onchain"):
        print(f"\n  {BOLD}{GREEN}⛓️  ON-CHAIN VERIFICATION:{RESET}")
        if onchain_info.get("hcs_topic"):
            topic = onchain_info["hcs_topic"]
            print(f"    HCS Topic:  {topic}")
            print(f"    {CYAN}→ https://hashscan.io/testnet/topic/{topic}{RESET}")
        if onchain_info.get("hcs_sequence"):
            print(f"    Sequence:   #{onchain_info['hcs_sequence']}")
        if onchain_info.get("hcs_score_seq"):
            print(f"    Score Seq:  #{onchain_info['hcs_score_seq']}")
        if onchain_info.get("contract_tx"):
            print(f"    {GREEN}✓ SubnetRegistry transaction confirmed{RESET}")
    else:
        print(f"  {DIM}→ No on-chain submission (use --onchain){RESET}")

    return result_hash


def wait_enter(msg=""):
    input(f"\n  {YELLOW}▶ Press Enter to continue{' — ' + msg if msg else ''}...{RESET}")


# ──────────────────────────────────────────────────────────
# Demo Tasks
# ──────────────────────────────────────────────────────────

TASKS = [
    {
        "title": "Smart Contract Code Review",
        "type": "code_review",
        "reward_mdt": 10,
        "payload": {
            "code": '''pragma solidity ^0.8.19;

contract StakingVault {
    mapping(address => uint256) public stakes;
    uint256 public totalStaked;

    function stake(uint256 amount) external {
        require(amount > 0, "Cannot stake 0");
        stakes[msg.sender] += amount;
        totalStaked += amount;
        // BUG: No token transfer!
    }

    function unstake(uint256 amount) external {
        require(stakes[msg.sender] >= amount, "Insufficient stake");
        stakes[msg.sender] -= amount;
        totalStaked -= amount;
        // Missing: reentrancy guard
        payable(msg.sender).transfer(amount);
    }

    function getReward(address validator) external view returns (uint256) {
        return stakes[validator] * 100 / totalStaked;
    }
}''',
            "language": "solidity",
            "context": "Hedera StakingVault — security audit",
        },
        "description": "Security audit of the StakingVault smart contract",
    },
    {
        "title": "AI Agent Safety Analysis",
        "type": "code_review",
        "reward_mdt": 15,
        "payload": {
            "code": '''import hashlib
import json
from typing import Dict, List

class TrustScoreEngine:
    """Compute trust scores for AI agents in ModernTensor network."""

    def __init__(self):
        self.history: List[Dict] = []
        self.weights = {"accuracy": 0.4, "speed": 0.3, "reliability": 0.3}

    def evaluate(self, agent_id: str, submission: Dict) -> float:
        """Score an agent's submission on [0, 1]."""
        accuracy = self._check_accuracy(submission)
        speed = self._normalize_speed(submission.get("latency_ms", 5000))
        reliability = self._get_reliability(agent_id)

        score = (
            accuracy * self.weights["accuracy"]
            + speed * self.weights["speed"]
            + reliability * self.weights["reliability"]
        )

        self.history.append({
            "agent_id": agent_id,
            "score": round(score, 4),
            "hash": hashlib.sha256(
                json.dumps(submission, sort_keys=True).encode()
            ).hexdigest(),
        })

        return round(score, 4)

    def _check_accuracy(self, submission: Dict) -> float:
        result = submission.get("result", "")
        if not result:
            return 0.0
        return min(1.0, len(str(result)) / 500)

    def _normalize_speed(self, latency_ms: int) -> float:
        return max(0, 1.0 - latency_ms / 10000)

    def _get_reliability(self, agent_id: str) -> float:
        agent_history = [h for h in self.history if h["agent_id"] == agent_id]
        if not agent_history:
            return 0.5
        return sum(h["score"] for h in agent_history[-10:]) / len(agent_history[-10:])
''',
            "language": "python",
            "context": "ModernTensor TrustScoreEngine — peer review",
        },
        "description": "Review TrustScoreEngine — trust scoring system for AI agents",
    },
    {
        "title": "Decentralized AI Whitepaper Draft",
        "type": "text_generation",
        "reward_mdt": 20,
        "payload": {
            "prompt": (
                "Write a 5-sentence executive summary for a whitepaper about "
                "ModernTensor — a decentralized AI verification network built on Hedera. "
                "Focus on: why trust is critical for autonomous AI agents, how Proof-of-Quality "
                "consensus works, and what makes Hedera's high-throughput hashgraph ideal for "
                "real-time AI verification at scale."
            ),
        },
        "description": "Gemini generates executive summary for whitepaper",
    },
]


def main():
    global onchain_mode

    parser = argparse.ArgumentParser()
    parser.add_argument("--miner", default="http://localhost:8091", help="Miner endpoint")
    parser.add_argument("--auto", action="store_true", help="Run automatically without waiting for Enter")
    parser.add_argument("--onchain", action="store_true", help="Enable on-chain mode (SubnetRegistry + HCS)")
    args = parser.parse_args()

    # ── On-chain init ──
    if args.onchain:
        init_onchain()

    banner()
    kv("Miner endpoint", args.miner)
    kv("Tasks to run", str(len(TASKS)))
    kv("Mode", "ON-CHAIN ⛓️" if onchain_mode else "HTTP-only")

    # Health check
    print(f"\n  {DIM}Checking miner health...{RESET}")
    try:
        r = requests.get(f"{args.miner}/health", timeout=5)
        if r.status_code == 200:
            info = r.json()
            print(f"  {GREEN}✓ Miner is ONLINE{RESET}")
            kv("Miner ID", info.get("miner_id", "unknown"))
            kv("Status", info.get("status", "unknown"))
        else:
            print(f"  {YELLOW}⚠ Miner returned {r.status_code}{RESET}")
    except Exception:
        print(f"  {RED}✗ Miner OFFLINE — start Terminal 1 first!{RESET}")
        print(f"  {DIM}  python run_miner.py --subnet 0 --port 8091{RESET}")
        return

    # Run tasks
    for i, task in enumerate(TASKS, 1):
        if not args.auto:
            wait_enter(task["description"])

        header(i, task["title"], [CYAN, MAGENTA, GREEN][i % 3])
        print(f"  {DIM}{task['description']}{RESET}\n")

        # ── STEP 1: Create task on-chain ──
        onchain_info = {}
        if onchain_mode:
            print(f"  {BOLD}STEP 1: Create task ON-CHAIN{RESET}")
            onchain_info = onchain_create_task(
                task["type"], task["payload"], task.get("reward_mdt", 10)
            )
            print()

        # ── STEP 2: Send to Miner (HTTP) ──
        step_label = "STEP 2" if onchain_mode else "STEP 1"
        print(f"  {BOLD}{step_label}: Send to Miner (Gemini AI){RESET}")
        result = send_task(args.miner, task["type"], task["payload"], i)

        if result:
            # ── STEP 3: Show result + submit on-chain ──
            result_hash = show_result(result, onchain_info)

            # Submit result hash on-chain
            if onchain_mode:
                print(f"\n  {BOLD}STEP 3: Submit result ON-CHAIN{RESET}")
                submit_info = onchain_submit_result(
                    result_hash,
                    task_id=onchain_info.get("onchain_task_id", 0),
                )
                if submit_info.get("onchain"):
                    print(f"  {BOLD}{GREEN}✓ FULL ON-CHAIN CYCLE COMPLETE{RESET}")

        if i < len(TASKS):
            print(f"\n  {DIM}{'─' * 56}{RESET}")

    # Summary
    chain_icon = "⛓️" if onchain_mode else "📡"
    chain_status = "All tasks recorded ON-CHAIN" if onchain_mode else "HTTP-only (use --onchain)"
    print(f"""
{BOLD}{GREEN}╔══════════════════════════════════════════════════════════╗
║                    ✅ DEMO COMPLETE                      ║
║──────────────────────────────────────────────────────────║
║  {chain_icon} {chain_status:<51}║
║  ✓ {len(TASKS)} tasks processed by Gemini AI Miner                  ║
║  ✓ Real-time code review + text generation               ║
║  ✓ Results hashed & submitted to Hedera                  ║
║  ✓ ModernTensor — Decentralized AI on Hedera             ║
╚══════════════════════════════════════════════════════════╝{RESET}
""")

    if onchain_mode and hcs_service:
        print(f"  {BOLD}🔍 Verify on HashScan:{RESET}")
        if hcs_service.task_topic_id:
            print(f"  Tasks:  https://hashscan.io/testnet/topic/{hcs_service.task_topic_id}")
        if hcs_service.scoring_topic_id:
            print(f"  Scores: https://hashscan.io/testnet/topic/{hcs_service.scoring_topic_id}")
        contract_id = registry_service.contract_id if registry_service else None
        if contract_id:
            print(f"  Contract: https://hashscan.io/testnet/contract/{contract_id}")
        print()


if __name__ == "__main__":
    main()
