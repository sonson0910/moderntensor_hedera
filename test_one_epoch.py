#!/usr/bin/env python3
"""
Test one epoch: start miner (Axon), run validator (Dendrite) for 1 epoch, 
then report results. All offline (no on-chain calls).
"""
import sys
import os
import time
import json
import hashlib

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from sdk.protocol.axon import Axon
from sdk.protocol.dendrite import Dendrite
from sdk.scoring.weights import WeightCalculator
from sdk.scoring.consensus import ScoreConsensus


# ── AI Handler (same as run_miner.py) ──
def ai_handler(payload: dict, task_type: str) -> dict:
    if task_type == "code_review":
        code = payload.get("code", "")
        return {
            "analysis": f"Code review completed. Analyzed {len(code)} chars.",
            "findings": [
                {"severity": "info", "message": "Code structure looks good"},
                {"severity": "suggestion", "message": "Consider adding type hints"},
            ],
            "score": 0.82,
            "confidence": 0.90,
        }
    return {"status": "processed", "task_type": task_type}


def main():
    print("=" * 70)
    print("  ModernTensor - Test One Epoch (Offline)")
    print("=" * 70)

    # ── Step 1: Start 2 miners ──
    print("\n[1/5] Starting miners...")
    
    miner1 = Axon(
        miner_id="miner-0",
        handler=ai_handler,
        host="127.0.0.1",
        port=8091,
        subnet_ids=[0],
        capabilities=["code_review"],
    )
    miner1.start()
    print(f"  OK Miner 1 started on {miner1.endpoint}")

    miner2 = Axon(
        miner_id="miner-1",
        handler=ai_handler,
        host="127.0.0.1",
        port=8092,
        subnet_ids=[0],
        capabilities=["code_review"],
    )
    miner2.start()
    print(f"  OK Miner 2 started on {miner2.endpoint}")

    time.sleep(0.5)  # Let servers start

    # ── Step 2: Create validator ──
    print("\n[2/5] Creating validator...")
    dendrite = Dendrite(validator_id="validator-0", timeout=10.0)
    weight_calc = WeightCalculator(min_stake=100.0)
    consensus = ScoreConsensus()

    miners = [
        {"miner_id": "miner-0", "endpoint": "http://127.0.0.1:8091"},
        {"miner_id": "miner-1", "endpoint": "http://127.0.0.1:8092"},
    ]

    # Health check
    for m in miners:
        ok = dendrite.check_health(m["endpoint"])
        status = "OK online" if ok else "FAIL OFFLINE"
        print(f"  {status}: {m['miner_id']} @ {m['endpoint']}")

    # ── Step 3: Create and send task ──
    print("\n[3/5] Sending task to miners...")
    task_payload = {
        "code": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
        "language": "python",
        "context": "Test epoch #1",
    }
    task_hash = hashlib.sha256(
        json.dumps(task_payload, sort_keys=True).encode()
    ).hexdigest()
    print(f"  Task hash: {task_hash[:16]}...")

    results = dendrite.broadcast(
        miners=miners,
        task_id="test-epoch-1",
        task_type="code_review",
        payload=task_payload,
    )

    for r in results:
        if r.success:
            print(f"  OK {r.miner_id}: score={r.output.get('score', 'N/A')}, "
                  f"confidence={r.output.get('confidence', 'N/A')}, "
                  f"latency={r.latency:.3f}s")
        else:
            print(f"  FAIL {r.miner_id}: ERROR - {r.error}")

    # ── Step 4: Score results ──
    print("\n[4/5] Scoring miners...")
    successful = [r for r in results if r.success]

    if not successful:
        print("  FAIL No successful results to score!")
    else:
        scores = {}
        for r in successful:
            output = r.output or {}
            score = 0.5
            if "analysis" in output:
                score += 0.2
            if "score" in output:
                score = min(1.0, output["score"])
            if "findings" in output and len(output.get("findings", [])) > 0:
                score += 0.1
            if "confidence" in output:
                score = score * float(output.get("confidence", 1.0))
            scores[r.miner_id] = min(1.0, round(score, 4))

        for mid, sc in scores.items():
            print(f"  {mid}: {sc:.4f}")

        # Consensus
        consensus_result = consensus.aggregate(scores)
        winner = max(scores, key=scores.get) if scores else None
        print(f"\n  Consensus: {consensus_result.to_dict()}")
        print(f"  Winner: {winner} (score={scores.get(winner, 0):.4f})")

    # ── Step 5: Stats ──
    print("\n[5/5] Final stats:")
    dendrite_stats = dendrite.get_stats()
    print(f"  Dendrite: requests={dendrite_stats['total_requests']}, "
          f"errors={dendrite_stats['total_errors']}, "
          f"success_rate={dendrite_stats['success_rate']:.2%}")
    
    m1_stats = miner1.get_stats()
    m2_stats = miner2.get_stats()
    print(f"  Miner 1: tasks_processed={m1_stats['tasks_processed']}")
    print(f"  Miner 2: tasks_processed={m2_stats['tasks_processed']}")

    # Cleanup
    miner1.stop()
    miner2.stop()
    print("\n  Miners stopped.")

    print("\n" + "=" * 70)
    all_ok = all(r.success for r in results)
    if all_ok:
        print("  EPOCH TEST PASSED - All miners responded successfully")
    else:
        failed = [r.miner_id for r in results if not r.success]
        print(f"  EPOCH TEST FAILED - Failed miners: {failed}")
    print("=" * 70)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
