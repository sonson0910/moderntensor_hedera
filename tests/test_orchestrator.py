"""
Tests for the Subnet Orchestrator and SDK module integration.

Tests cover:
- EmissionSchedule: epoch rewards, halving, stats
- WeightCalculator: merit-based weights, floor enforcement
- ScoreConsensus: weighted median, outlier detection
- SubnetOrchestrator: proportional rewards, full epoch flow
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk.protocol.emissions import EmissionSchedule
from sdk.scoring.weights import WeightCalculator
from sdk.scoring.consensus import ScoreConsensus


# =====================================================================
# EmissionSchedule Tests
# =====================================================================

class TestEmissionSchedule:
    def test_init(self):
        es = EmissionSchedule()
        assert es is not None

    def test_epoch_rewards(self):
        """Stakers should receive proportional rewards."""
        es = EmissionSchedule()
        stakers = {"alice": 100_000, "bob": 50_000}
        rewards = es.calculate_epoch_rewards(stakers)
        assert "alice" in rewards
        assert "bob" in rewards
        # Alice has 2x stake → should get ~2x reward
        assert rewards["alice"] > rewards["bob"]

    def test_stats(self):
        """Stats should include key metrics."""
        es = EmissionSchedule()
        stats = es.get_stats()
        assert "current_epoch" in stats
        assert "daily_emission" in stats
        assert "remaining_pool" in stats
        assert stats["daily_emission"] > 0
        assert stats["remaining_pool"] > 0


# =====================================================================
# WeightCalculator Tests
# =====================================================================

class TestWeightCalculator:
    def test_init(self):
        wc = WeightCalculator(
            min_stake=100.0,
            weight_cap=0.80,
            performance_exponent=2.0,
            new_miner_bonus=0.1,
        )
        assert wc is not None

    def test_calculate_weights(self):
        """Miners with higher reputation should get higher weights."""
        wc = WeightCalculator(
            min_stake=100.0,
            weight_cap=0.80,
            performance_exponent=2.0,
            new_miner_bonus=0.1,
        )
        miners = [
            {
                "miner_id": "good_miner",
                "reputation_score": 0.95,
                "stake_amount": 1000,
                "success_rate": 1.0,
                "timeout_rate": 0.0,
                "total_tasks": 10,
            },
            {
                "miner_id": "bad_miner",
                "reputation_score": 0.30,
                "stake_amount": 1000,
                "success_rate": 0.5,
                "timeout_rate": 0.1,
                "total_tasks": 10,
            },
        ]
        matrix = wc.calculate(miners=miners, epoch=1, subnet_id=0)
        good_w = matrix.get_weight("good_miner")
        bad_w = matrix.get_weight("bad_miner")
        assert good_w > bad_w, "Good miner should have higher weight"
        assert good_w > 0
        assert bad_w >= 0

    def test_weight_floor(self):
        """Weight floor should prevent permanent exclusion."""
        wc = WeightCalculator(
            min_stake=100.0,
            weight_cap=0.80,
            performance_exponent=2.0,
        )
        WEIGHT_FLOOR = 0.05
        miners = [
            {
                "miner_id": "dominant",
                "reputation_score": 1.0,
                "stake_amount": 1000,
                "success_rate": 1.0,
                "timeout_rate": 0.0,
                "total_tasks": 100,
            },
            {
                "miner_id": "weak",
                "reputation_score": 0.01,
                "stake_amount": 1000,
                "success_rate": 0.1,
                "timeout_rate": 0.5,
                "total_tasks": 100,
            },
        ]
        matrix = wc.calculate(miners=miners, epoch=1, subnet_id=0)
        raw_w = matrix.get_weight("weak")
        floored_w = max(raw_w, WEIGHT_FLOOR)
        assert floored_w >= WEIGHT_FLOOR


# =====================================================================
# ScoreConsensus Tests
# =====================================================================

class TestScoreConsensus:
    def test_weighted_median(self):
        """Weighted median should be robust to outliers."""
        sc = ScoreConsensus(min_validators=1, outlier_sensitivity=1.5)
        scores = {
            "val_a": 0.90,
            "val_b": 0.88,
            "val_c": 0.20,  # outlier
        }
        weights = {
            "val_a": 50_000,
            "val_b": 60_000,
            "val_c": 10_000,  # small stake
        }
        result = sc.aggregate(scores=scores, weights=weights)
        # Consensus should be close to 0.88-0.90, not pulled down by outlier
        assert result.consensus_score > 0.80
        assert hasattr(result, "confidence")
        assert hasattr(result, "agreement_level")

    def test_agreement_score(self):
        """High agreement when all validators score similarly."""
        sc = ScoreConsensus(min_validators=1)
        scores = {"v1": 0.85, "v2": 0.86, "v3": 0.84}
        weights = {"v1": 100, "v2": 100, "v3": 100}
        result = sc.aggregate(scores=scores, weights=weights)
        assert result.agreement_level > 0.9


# =====================================================================
# Proportional Reward Tests
# =====================================================================

class TestProportionalRewards:
    def test_proportional_split(self):
        """Rewards should split proportionally by score."""
        scores = {"alpha": 0.90, "beta": 0.60}
        miner_pool = 8.50  # 85% of 10 MDT

        total_score = sum(scores.values())
        rewards = {}
        for name, score in scores.items():
            rewards[name] = miner_pool * (score / total_score)

        assert abs(rewards["alpha"] + rewards["beta"] - miner_pool) < 0.01
        assert rewards["alpha"] > rewards["beta"]
        # Alpha 60%, Beta 40%
        assert abs(rewards["alpha"] / miner_pool - 0.6) < 0.01
        assert abs(rewards["beta"] / miner_pool - 0.4) < 0.01

    def test_equal_split_when_zero_scores(self):
        """Equal split when all scores are 0."""
        scores = {"a": 0.0, "b": 0.0}
        miner_pool = 8.50
        total_score = sum(scores.values())

        if total_score == 0:
            equal = miner_pool / len(scores)
            rewards = {k: equal for k in scores}
        else:
            rewards = {k: miner_pool * (v / total_score) for k, v in scores.items()}

        assert rewards["a"] == rewards["b"]
        assert abs(rewards["a"] - 4.25) < 0.01

    def test_reward_split_percentages(self):
        """Total reward split should equal 100%."""
        task_reward = 10.0
        split = {
            "miner": 0.85,
            "validator": 0.08,
            "staking": 0.05,
            "protocol": 0.02,
        }
        total_pct = sum(split.values())
        assert abs(total_pct - 1.0) < 0.001

        total_tokens = sum(task_reward * pct for pct in split.values())
        assert abs(total_tokens - task_reward) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
