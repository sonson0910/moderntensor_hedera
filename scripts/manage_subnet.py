#!/usr/bin/env python3
"""
ModernTensor — Subnet Management Tool

Create, configure, and manage subnets on the ModernTensor network.

Commands:
    python scripts/manage_subnet.py create   — Create a new subnet
    python scripts/manage_subnet.py info      — View subnet details
    python scripts/manage_subnet.py miners    — List miners in subnet
    python scripts/manage_subnet.py stats     — Get subnet statistics
    python scripts/manage_subnet.py deploy    — Deploy SubnetRegistry contract
    python scripts/manage_subnet.py update    — Update subnet fee rate / status
    python scripts/manage_subnet.py task      — View task info from contract
    python scripts/manage_subnet.py withdraw  — Withdraw miner / validator earnings

Usage:
    python scripts/manage_subnet.py create \
        --name "AI Code Review" \
        --fee-rate 0.03 \
        --min-stake 100

    python scripts/manage_subnet.py update --subnet-id 0 --fee-rate 0.05
    python scripts/manage_subnet.py task --task-id 0
    python scripts/manage_subnet.py withdraw
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import click
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [subnet] %(message)s",
)
log = logging.getLogger(__name__)


# ── Shared helpers ──────────────────────────────────────────


def _get_hedera_client():
    """Create and return a HederaClient from env config."""
    from sdk.hedera.config import load_hedera_config
    from sdk.hedera.client import HederaClient

    config = load_hedera_config()
    return HederaClient(config)


def _get_registry(client=None):
    """Get SubnetRegistryService, optionally reusing a client."""
    from sdk.hedera.subnet_registry import SubnetRegistryService

    if client is None:
        client = _get_hedera_client()
    return SubnetRegistryService(client), client


def _get_staking(client=None):
    """Get StakingVaultService."""
    from sdk.hedera.staking_vault import StakingVaultService

    if client is None:
        client = _get_hedera_client()
    return StakingVaultService(client), client


# ── CLI Group ───────────────────────────────────────────────


@click.group()
def cli():
    """ModernTensor Subnet Manager"""
    pass


# -----------------------------------------------------------------------
# create
# -----------------------------------------------------------------------


@cli.command()
@click.option("--name", required=True, help="Subnet name")
@click.option("--fee-rate", type=float, default=0.03, help="Fee rate (0–0.20)")
@click.option("--min-stake", type=float, default=100.0, help="Min stake (MDT)")
@click.option(
    "--task-types",
    default="code_review,text_generation",
    help="Comma-separated task types",
)
@click.option("--max-miners", type=int, default=100, help="Max miners allowed")
@click.option("--dry-run", is_flag=True, default=False, help="Preview without executing on-chain")
def create(name, fee_rate, min_stake, task_types, max_miners, dry_run):
    """Create a new subnet."""
    if not (0 <= fee_rate <= 0.20):
        click.echo("❌ Fee rate must be between 0 and 0.20 (0–20%)")
        return

    subnet_id = abs(hash(name)) % 10000

    subnet_config = {
        "subnet_id": subnet_id,
        "name": name,
        "owner": os.getenv("HEDERA_ACCOUNT_ID", "0.0.unknown"),
        "fee_rate": fee_rate,
        "min_stake": min_stake,
        "task_types": task_types.split(","),
        "max_miners": max_miners,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "active",
    }

    click.echo(f"\n{'=' * 50}")
    click.echo(f"  🌐 Creating Subnet: {name}")
    click.echo(f"{'=' * 50}")
    click.echo(f"  ID:          {subnet_id}")
    click.echo(f"  Owner:       {subnet_config['owner']}")
    click.echo(f"  Fee Rate:    {fee_rate * 100:.1f}%")
    click.echo(f"  Min Stake:   {min_stake} MDT")
    click.echo(f"  Task Types:  {task_types}")
    click.echo(f"  Max Miners:  {max_miners}")

    if dry_run:
        click.echo("\n🔍 DRY-RUN mode — no changes will be made.")
        click.echo("   Would save config and register on-chain.")
        return

    # Save subnet config locally
    subnets_dir = ROOT / ".moderntensor" / "subnets"
    subnets_dir.mkdir(parents=True, exist_ok=True)
    config_file = subnets_dir / f"subnet_{subnet_id}.json"
    config_file.write_text(json.dumps(subnet_config, indent=2))

    click.echo(f"\n💾 Config saved: {config_file}")

    # Try on-chain registration
    try:
        _register_onchain(subnet_config)
        click.echo("📡 Registered on Hedera SubnetRegistry contract")
    except Exception as e:
        click.echo(f"⚠️  On-chain registration skipped: {e}")
        click.echo("   Subnet saved locally. Deploy contract first.")

    click.echo("✅ Subnet created!")


def _register_onchain(config):
    """Register subnet on SubnetRegistry smart contract."""
    registry, client = _get_registry()

    try:
        fee_rate_bps = int(config["fee_rate"] * 10000)
        receipt = registry.register_subnet(
            name=config["name"],
            description=f"Managed subnet: {config['name']}",
            fee_rate=fee_rate_bps,
        )
        tx_id = getattr(receipt, "transaction_id", None) if receipt else None
        if tx_id:
            click.echo(f"   TX: {tx_id}")
    finally:
        client.close()


# -----------------------------------------------------------------------
# info
# -----------------------------------------------------------------------


@cli.command()
@click.argument("subnet_id", type=int, required=False, default=None)
def info(subnet_id):
    """View subnet details."""
    subnets_dir = ROOT / ".moderntensor" / "subnets"

    if subnet_id is not None:
        config_file = subnets_dir / f"subnet_{subnet_id}.json"
        if config_file.exists():
            data = json.loads(config_file.read_text())
            _print_subnet(data)
        else:
            click.echo(f"❌ Subnet {subnet_id} not found locally")
    else:
        # List all subnets
        if not subnets_dir.exists():
            click.echo("No subnets found. Create one with: manage_subnet.py create")
            return

        files = sorted(subnets_dir.glob("subnet_*.json"))
        if not files:
            click.echo("No subnets found.")
            return

        click.echo(f"\n🌐 Registered Subnets ({len(files)}):")
        click.echo(f"{'ID':>6}  {'Name':<25} {'Fee':>6} {'Miners':>6}  {'Status'}")
        click.echo("─" * 65)

        for f in files:
            data = json.loads(f.read_text())
            click.echo(
                f"{data['subnet_id']:>6}  "
                f"{data['name']:<25} "
                f"{data['fee_rate']*100:>5.1f}% "
                f"{data.get('miner_count', 0):>6}  "
                f"{data['status']}"
            )


def _print_subnet(data):
    """Print detailed subnet info."""
    click.echo(f"\n{'=' * 50}")
    click.echo(f"  🌐 Subnet: {data['name']}")
    click.echo(f"{'=' * 50}")
    for k, v in data.items():
        click.echo(f"  {k:>15}: {v}")


# -----------------------------------------------------------------------
# update  (NEW)
# -----------------------------------------------------------------------


@cli.command()
@click.option("--subnet-id", type=int, required=True, help="Subnet ID to update")
@click.option("--fee-rate", type=float, default=None, help="New fee rate (0–0.20)")
@click.option(
    "--status",
    type=click.Choice(["active", "paused"]),
    default=None,
    help="New status",
)
@click.option("--dry-run", is_flag=True, default=False, help="Preview without executing")
def update(subnet_id, fee_rate, status, dry_run):
    """Update subnet fee rate or status on-chain."""
    if fee_rate is None and status is None:
        click.echo("❌ Specify at least --fee-rate or --status")
        return

    if fee_rate is not None and not (0 <= fee_rate <= 0.20):
        click.echo("❌ Fee rate must be between 0 and 0.20 (0–20%)")
        return

    new_fee = int(fee_rate * 10000) if fee_rate is not None else 0
    new_status = {"active": 1, "paused": 2}.get(status, 0) if status else 0

    click.echo(f"\n{'=' * 50}")
    click.echo(f"  🔄 Updating Subnet {subnet_id}")
    click.echo(f"{'=' * 50}")
    if fee_rate is not None:
        click.echo(f"  New Fee Rate:  {fee_rate * 100:.1f}%  (bps: {new_fee})")
    if status:
        click.echo(f"  New Status:    {status}  (code: {new_status})")

    if dry_run:
        click.echo("\n🔍 DRY-RUN — no on-chain changes.")
        return

    try:
        registry, client = _get_registry()
        try:
            receipt = registry.update_subnet(
                subnet_id=subnet_id,
                new_fee_rate=new_fee if fee_rate is not None else None,
                new_status=new_status if status else None,
            )
            tx_id = getattr(receipt, "transaction_id", None) if receipt else None
            click.echo(f"✅ Subnet updated!  TX: {tx_id or 'N/A'}")
        finally:
            client.close()
    except Exception as e:
        click.echo(f"❌ Update failed: {e}")


# -----------------------------------------------------------------------
# task  (NEW)
# -----------------------------------------------------------------------


@cli.command()
@click.option("--task-id", type=int, required=True, help="Task ID to look up")
def task(task_id):
    """View task info from SubnetRegistry contract."""
    if task_id < 0:
        click.echo("❌ Task ID must be non-negative")
        return

    click.echo(f"\n📋 Querying task {task_id} ...")

    try:
        registry, client = _get_registry()
        try:
            result = registry.get_task(task_id)
            click.echo(f"\n{'=' * 50}")
            click.echo(f"  📋 Task #{task_id}")
            click.echo(f"{'=' * 50}")
            click.echo(f"  Result: {result}")
        finally:
            client.close()
    except Exception as e:
        click.echo(f"❌ get_task failed: {e}")


# -----------------------------------------------------------------------
# withdraw  (NEW)
# -----------------------------------------------------------------------


@cli.command()
@click.option("--dry-run", is_flag=True, default=False, help="Preview without executing")
def withdraw(dry_run):
    """Withdraw miner / validator earnings from SubnetRegistry."""
    click.echo("\n💰 Withdrawing earnings ...")

    if dry_run:
        click.echo("🔍 DRY-RUN — would call withdrawEarnings() on SubnetRegistry.")
        return

    try:
        registry, client = _get_registry()
        try:
            receipt = registry.withdraw_earnings()
            tx_id = getattr(receipt, "transaction_id", None) if receipt else None
            click.echo(f"✅ Earnings withdrawn!  TX: {tx_id or 'N/A'}")
        finally:
            client.close()
    except Exception as e:
        click.echo(f"❌ Withdraw failed: {e}")


# -----------------------------------------------------------------------
# miners
# -----------------------------------------------------------------------


@cli.command()
@click.argument("subnet_id", type=int, default=0)
def miners(subnet_id):
    """List miners in a subnet."""
    from sdk.protocol.miner_registry import MinerRegistry

    registry = MinerRegistry()
    try:
        registry.load_state()
        active = registry.get_active_miners(subnet_id=subnet_id)
    except Exception:
        active = []

    if not active:
        click.echo(f"No miners found in subnet {subnet_id}")
        click.echo("Miners register with: python miners/code_review_miner.py")
        return

    click.echo(f"\n⛏️  Miners in Subnet {subnet_id} ({len(active)}):")
    click.echo(
        f"{'Miner ID':<20} {'Reputation':>10} {'Weight':>8} "
        f"{'Tasks':>6} {'Capabilities'}"
    )
    click.echo("─" * 70)

    for miner in sorted(active, key=lambda m: m.effective_weight, reverse=True):
        click.echo(
            f"{miner.miner_id:<20} "
            f"{miner.reputation.score:>10.4f} "
            f"{miner.effective_weight:>8.4f} "
            f"{miner.reputation.total_tasks:>6} "
            f"{miner.capabilities}"
        )


# -----------------------------------------------------------------------
# stats
# -----------------------------------------------------------------------


@cli.command()
@click.argument("subnet_id", type=int, default=0)
def stats(subnet_id):
    """Get subnet statistics."""
    from sdk.protocol.miner_registry import MinerRegistry

    registry = MinerRegistry()
    try:
        registry.load_state()
        active = registry.get_active_miners(subnet_id=subnet_id)
    except Exception:
        active = []

    total_stake = sum(m.stake_amount for m in active) if active else 0
    avg_rep = (
        sum(m.reputation.score for m in active) / len(active) if active else 0
    )

    click.echo(f"\n📊 Subnet {subnet_id} Statistics:")
    click.echo(f"  Active miners:      {len(active)}")
    click.echo(f"  Total staked:       {total_stake:.2f} MDT")
    click.echo(f"  Average reputation: {avg_rep:.4f}")

    if active:
        capabilities = set()
        for m in active:
            capabilities.update(m.capabilities)
        click.echo(f"  Capabilities:       {sorted(capabilities)}")

        top = sorted(active, key=lambda m: m.effective_weight, reverse=True)[:3]
        click.echo(f"\n  🏆 Top Miners:")
        for i, m in enumerate(top, 1):
            click.echo(f"    #{i} {m.miner_id} (weight={m.effective_weight:.4f})")


# -----------------------------------------------------------------------
# deploy
# -----------------------------------------------------------------------


@cli.command()
def deploy():
    """Deploy SubnetRegistry smart contract to Hedera."""
    click.echo("\n🚀 Smart Contract Deployment")
    click.echo("─" * 50)
    click.echo("  Run the full deployment script:")
    click.echo("    python scripts/deploy_contracts.py")
    click.echo()
    click.echo("  This deploys:")
    click.echo("    1. SubnetRegistry.sol — Subnet & miner management")
    click.echo("    2. PaymentEscrow.sol  — Task payment escrow")
    click.echo("    3. StakingVault.sol   — Stake management")
    click.echo("    4. MDTGovernor.sol    — Governance")
    click.echo()
    click.echo("  Prerequisites:")
    click.echo("    - Hedera testnet account with HBAR")
    click.echo("    - .env configured with account credentials")
    click.echo("    - npm install in contracts/ (for OpenZeppelin)")


if __name__ == "__main__":
    cli()
