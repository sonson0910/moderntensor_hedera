"""
Unit tests for sdk.hedera.subnets — SubnetService

Tests SubnetService methods, dataclasses, fee calculations, and
event parsing using a mock contract_service (no real Hedera node).
"""

import unittest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sdk.hedera.subnets import (
    SubnetService,
    SubnetConfig,
    SubnetInfo,
    SubnetStatus,
    TaskInfo,
    TaskStatus,
    create_subnet_service,
)


# ── Mock helpers ────────────────────────────────────────────


def _mock_contract_service():
    """Create a MagicMock that simulates HederaClient."""
    svc = MagicMock()
    return svc


def _make_subnet_result():
    """Return a tuple matching the shape of getSubnet() result."""
    return (
        0,        # id
        "TestNet",  # name
        "A test subnet",  # description
        "0.0.1234",  # owner
        500,      # fee_rate (5%)
        100000000,  # min_task_reward (1 MDT)
        0,        # total_volume
        0,        # total_tasks
        0,        # active_miners
        0,        # status (ACTIVE)
        1700000000,  # created_at
    )


def _make_task_result(task_id=0, status=0):
    """Return a tuple matching the shape of getTask() result."""
    return (
        task_id,          # id
        0,                # subnet_id
        "0.0.5555",       # requester
        "QmHash123",      # task_hash
        1000000000,       # reward_amount (10 MDT)
        50000000,         # protocol_fee
        25000000,         # subnet_fee
        1700003600,       # deadline
        status,           # status
        "0x0000000000000000000000000000000000000000",  # winning_miner
        0,                # winning_score
        1700000000,       # created_at
    )


# ── Dataclass tests ─────────────────────────────────────────


class TestSubnetStatusEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(SubnetStatus.ACTIVE, 0)
        self.assertEqual(SubnetStatus.PAUSED, 1)
        self.assertEqual(SubnetStatus.DEPRECATED, 2)


class TestTaskStatusEnum(unittest.TestCase):
    def test_all_values(self):
        self.assertEqual(TaskStatus.CREATED, 0)
        self.assertEqual(TaskStatus.IN_PROGRESS, 1)
        self.assertEqual(TaskStatus.PENDING_REVIEW, 2)
        self.assertEqual(TaskStatus.COMPLETED, 3)
        self.assertEqual(TaskStatus.CANCELLED, 4)
        self.assertEqual(TaskStatus.EXPIRED, 5)


class TestSubnetConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = SubnetConfig(name="X", description="Y")
        self.assertEqual(cfg.fee_rate, 500)
        self.assertEqual(cfg.min_task_reward, 100000000)

    def test_custom_values(self):
        cfg = SubnetConfig(name="Z", description="W", fee_rate=300, min_task_reward=50)
        self.assertEqual(cfg.fee_rate, 300)
        self.assertEqual(cfg.min_task_reward, 50)


class TestSubnetInfo(unittest.TestCase):
    def test_from_result_tuple(self):
        data = _make_subnet_result()
        info = SubnetInfo(
            id=data[0], name=data[1], description=data[2], owner=data[3],
            fee_rate=data[4], min_task_reward=data[5], total_volume=data[6],
            total_tasks=data[7], active_miners=data[8],
            status=SubnetStatus(data[9]), created_at=data[10],
        )
        self.assertEqual(info.name, "TestNet")
        self.assertEqual(info.status, SubnetStatus.ACTIVE)


class TestTaskInfo(unittest.TestCase):
    def test_winning_miner_none_for_zero_address(self):
        data = _make_task_result()
        info = TaskInfo(
            id=data[0], subnet_id=data[1], requester=data[2],
            task_hash=data[3], reward_amount=data[4], protocol_fee=data[5],
            subnet_fee=data[6], deadline=data[7], status=TaskStatus(data[8]),
            winning_miner=None, winning_score=data[10], created_at=data[11],
        )
        self.assertIsNone(info.winning_miner)


# ── SubnetService method tests ──────────────────────────────


class TestSubnetServiceRegister(unittest.TestCase):
    def setUp(self):
        self.mock_cs = _mock_contract_service()
        self.svc = SubnetService(self.mock_cs, "0.0.999")

    def test_register_subnet_calls_execute(self):
        # Setup mock to return a result with subnetCount fallback
        self.mock_cs.call_contract.return_value = 1
        self.mock_cs.execute_contract.return_value = MagicMock(
            contract_function_result=None
        )

        config = SubnetConfig(name="AI Review", description="Review code", fee_rate=300)
        subnet_id = self.svc.register_subnet(config)
        self.mock_cs.execute_contract.assert_called_once_with(
            "0.0.999", "registerSubnet", ["AI Review", "Review code", 300]
        )
        # Fallback returns int(call_contract result)
        self.assertEqual(subnet_id, 1)

    def test_register_rejects_high_fee_rate(self):
        config = SubnetConfig(name="X", description="Y", fee_rate=3000)
        with self.assertRaises(ValueError):
            self.svc.register_subnet(config)


class TestSubnetServiceGetSubnet(unittest.TestCase):
    def setUp(self):
        self.mock_cs = _mock_contract_service()
        self.svc = SubnetService(self.mock_cs, "0.0.999")

    def test_get_subnet_parses_result(self):
        self.mock_cs.call_contract.return_value = _make_subnet_result()

        info = self.svc.get_subnet(0)
        self.assertEqual(info.id, 0)
        self.assertEqual(info.name, "TestNet")
        self.assertEqual(info.fee_rate, 500)
        self.assertEqual(info.status, SubnetStatus.ACTIVE)


class TestSubnetServiceGetTask(unittest.TestCase):
    def setUp(self):
        self.mock_cs = _mock_contract_service()
        self.svc = SubnetService(self.mock_cs, "0.0.999")

    def test_get_task_parses_result(self):
        self.mock_cs.call_contract.return_value = _make_task_result(task_id=42)

        info = self.svc.get_task(42)
        self.assertEqual(info.id, 42)
        self.assertEqual(info.requester, "0.0.5555")
        self.assertIsNone(info.winning_miner)  # zero address → None

    def test_get_task_with_winner(self):
        data = list(_make_task_result(task_id=7, status=3))
        data[9] = "0xABCDEF1234567890"  # non-zero address
        self.mock_cs.call_contract.return_value = tuple(data)

        info = self.svc.get_task(7)
        self.assertEqual(info.winning_miner, "0xABCDEF1234567890")
        self.assertEqual(info.status, TaskStatus.COMPLETED)


class TestSubnetServiceListSubnets(unittest.TestCase):
    def setUp(self):
        self.mock_cs = _mock_contract_service()
        self.svc = SubnetService(self.mock_cs, "0.0.999")

    def test_list_subnets_iterates(self):
        self.mock_cs.call_contract.side_effect = [
            2,  # subnetCount
            _make_subnet_result(),
            _make_subnet_result(),
        ]
        subnets = self.svc.list_subnets()
        self.assertEqual(len(subnets), 2)

    def test_list_subnets_empty(self):
        self.mock_cs.call_contract.return_value = 0
        subnets = self.svc.list_subnets()
        self.assertEqual(len(subnets), 0)


class TestSubnetServiceFeeCalculation(unittest.TestCase):
    def setUp(self):
        self.svc = SubnetService(MagicMock(), "0.0.999")

    def test_fee_calculation_standard(self):
        fees = self.svc.calculate_fees(reward_amount=10000, subnet_fee_rate=500)
        # protocol: 10000 * 500 / 10000 = 500
        self.assertEqual(fees["protocol_fee"], 500)
        # subnet: 10000 * 500 / 10000 = 500
        self.assertEqual(fees["subnet_fee"], 500)
        self.assertEqual(fees["miner_reward"], 10000)
        self.assertEqual(fees["total_deposit"], 10000 + 500 + 500)

    def test_fee_calculation_zero_subnet_fee(self):
        fees = self.svc.calculate_fees(reward_amount=10000, subnet_fee_rate=0)
        self.assertEqual(fees["subnet_fee"], 0)
        self.assertEqual(fees["total_deposit"], 10000 + 500)

    def test_fee_calculation_large_amount(self):
        amount = 100_000_000_000  # 1000 MDT
        fees = self.svc.calculate_fees(reward_amount=amount, subnet_fee_rate=1000)
        self.assertEqual(fees["protocol_fee"], amount * 500 // 10000)
        self.assertEqual(fees["subnet_fee"], amount * 1000 // 10000)


class TestSubnetServiceWithdraw(unittest.TestCase):
    def setUp(self):
        self.mock_cs = _mock_contract_service()
        self.svc = SubnetService(self.mock_cs, "0.0.999")

    def test_withdraw_earnings(self):
        result = self.svc.withdraw_earnings()
        self.assertTrue(result)
        self.mock_cs.execute_contract.assert_called_once_with(
            "0.0.999", "withdrawEarnings", []
        )

    def test_get_pending_withdrawals(self):
        self.mock_cs.call_contract.return_value = 5000
        balance = self.svc.get_pending_withdrawals("0.0.1234")
        self.assertEqual(balance, 5000)


class TestSubnetServiceMiner(unittest.TestCase):
    def setUp(self):
        self.mock_cs = _mock_contract_service()
        self.svc = SubnetService(self.mock_cs, "0.0.999")

    def test_register_miner(self):
        result = self.svc.register_miner(subnet_id=0)
        self.assertTrue(result)

    def test_is_miner(self):
        self.mock_cs.call_contract.return_value = True
        self.assertTrue(self.svc.is_miner(0, "0.0.1234"))


class TestSubnetServiceReputation(unittest.TestCase):
    def setUp(self):
        self.mock_cs = _mock_contract_service()
        self.svc = SubnetService(self.mock_cs, "0.0.999")

    def test_get_validator_reputation(self):
        self.mock_cs.call_contract.return_value = (100, 95, 9500, 1700000000)
        rep = self.svc.get_validator_reputation("0.0.1234")
        self.assertEqual(rep["total_validations"], 100)
        self.assertEqual(rep["accurate_validations"], 95)
        self.assertEqual(rep["reputation_score"], 9500)
        self.assertEqual(rep["reputation_percent"], 95.0)

    def test_port_reputation(self):
        result = self.svc.port_reputation(from_subnet_id=0, to_subnet_id=1)
        self.assertTrue(result)


class TestCreateSubnetServiceFactory(unittest.TestCase):
    def test_factory_creates_instance(self):
        svc = create_subnet_service(MagicMock(), "0.0.888")
        self.assertIsInstance(svc, SubnetService)
        self.assertEqual(svc.contract_id, "0.0.888")


if __name__ == "__main__":
    unittest.main()
