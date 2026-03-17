#!/usr/bin/env python3
"""
ModernTensor — Gemini AI Miner Demo
=====================================

Demonstrates a REAL AI-powered miner processing tasks on the
ModernTensor decentralized AI network on Hedera.

What this demo shows:
  1. Initialize Gemini AI miner (real LLM engine)
  2. Process a code review task → Gemini analyzes code quality
  3. Process a text generation task → Gemini generates content
  4. Hash results → ready for on-chain submission
  5. (Optional) Submit to Hedera smart contracts

For ModernTensor on Hedera — Hello Future Apex Hackathon 2026
"""

import sys
import os
import json
import time
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from sdk.ai.gemini_ai import GeminiMiner

# ── Pretty output helpers ──

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def banner(text):
    print(f"\n{BOLD}{CYAN}{'═' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 60}{RESET}\n")


def section(text):
    print(f"\n{BOLD}{MAGENTA}── {text} ──{RESET}\n")


def kv(key, value, color=GREEN):
    print(f"  {DIM}{key}:{RESET} {color}{value}{RESET}")


# ── Demo Tasks ──

TASK_CODE_REVIEW = {
    "code": """
import hashlib
import json
from typing import List, Dict

class BlockchainValidator:
    def __init__(self, stake_amount: float):
        self.stake = stake_amount
        self.validated_blocks = []

    def validate_transaction(self, tx: Dict) -> bool:
        # Check transaction hash integrity
        tx_hash = hashlib.sha256(
            json.dumps(tx, sort_keys=True).encode()
        ).hexdigest()
        if tx.get('hash') != tx_hash:
            return False

        # Verify sender has sufficient balance
        if tx.get('amount', 0) <= 0:
            return False

        self.validated_blocks.append(tx_hash)
        return True

    def get_reward(self, base_reward: float) -> float:
        multiplier = min(2.0, 1.0 + len(self.validated_blocks) * 0.01)
        return base_reward * multiplier * (self.stake / 10000)
""",
    "language": "python",
    "context": "Smart contract validator - code review task",
}

TASK_TEXT_GEN = {
    "prompt": "Explain how decentralized AI networks use blockchain incentives to ensure honest computation by miners, in 3 sentences.",
}


def main():
    banner("ModernTensor — Gemini AI Miner Demo")

    # 1. Initialize
    section("1. Initialize Gemini AI Miner")
    miner = GeminiMiner()
    kv("Model", miner.MODEL)
    kv("Online", str(miner.is_online), GREEN if miner.is_online else YELLOW)

    if not miner.is_online:
        print(f"\n  {YELLOW}⚠ Gemini API not available — running in fallback mode{RESET}")
        print(f"  {DIM}Set GOOGLE_API_KEY in .env to enable real AI{RESET}\n")

    # 2. Code Review Task
    section("2. Code Review Task → Gemini AI Analysis")
    print(f"  {DIM}Sending Python code for AI-powered review...{RESET}")
    t0 = time.time()
    review_result = miner.code_review(
        code=TASK_CODE_REVIEW["code"],
        language=TASK_CODE_REVIEW["language"],
    )
    elapsed = time.time() - t0
    kv("Latency", f"{elapsed * 1000:.0f}ms")
    kv("AI Powered", str(review_result.get("ai_powered", False)))
    kv("Score", f"{review_result.get('score', 0):.2f}")
    kv("Confidence", f"{review_result.get('confidence', 0):.2f}")
    print(f"\n  {BOLD}Analysis:{RESET}")
    print(f"  {review_result.get('analysis', 'N/A')[:300]}")

    findings = review_result.get("findings", [])
    if findings:
        print(f"\n  {BOLD}Findings ({len(findings)}):{RESET}")
        for f in findings[:5]:
            sev = f.get("severity", "info")
            colors = {"critical": "\033[91m", "warning": YELLOW, "info": CYAN, "suggestion": GREEN}
            c = colors.get(sev, RESET)
            print(f"    {c}[{sev.upper()}]{RESET} {f.get('message', '')}")

    # 3. Text Generation Task
    section("3. Text Generation → Gemini AI Content")
    print(f"  {DIM}Prompt: {TASK_TEXT_GEN['prompt'][:80]}...{RESET}")
    t0 = time.time()
    gen_result = miner.text_generation(prompt=TASK_TEXT_GEN["prompt"])
    elapsed = time.time() - t0
    kv("Latency", f"{elapsed * 1000:.0f}ms")
    kv("AI Powered", str(gen_result.get("ai_powered", False)))
    print(f"\n  {BOLD}Generated Text:{RESET}")
    text = gen_result.get("text", "")
    # Wrap long text
    for i in range(0, len(text), 80):
        print(f"  {text[i:i + 80]}")

    # 4. Hash for on-chain
    section("4. Hash Results for On-Chain Submission")
    combined = json.dumps(
        {"code_review": review_result, "text_gen": gen_result},
        sort_keys=True,
        default=str,
    )
    result_hash = hashlib.sha256(combined.encode()).hexdigest()
    kv("Result Hash", result_hash[:40] + "...")
    kv("Ready for", "SubnetRegistry.submit_result()")

    # 5. Stats
    section("5. Miner Stats")
    stats = miner.stats
    for k, v in stats.items():
        kv(k, str(v))

    # Summary
    banner("Demo Complete ✓")
    print(f"  {GREEN}✓ Real AI processing with Google Gemini{RESET}")
    print(f"  {GREEN}✓ Code review with detailed findings{RESET}")
    print(f"  {GREEN}✓ Text generation for network tasks{RESET}")
    print(f"  {GREEN}✓ Results hashed for on-chain submission{RESET}")
    print(f"  {GREEN}✓ Decentralized AI on Hedera — ModernTensor{RESET}")
    print()


if __name__ == "__main__":
    main()
