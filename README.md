# 🛡️ ModernTensor

> **The Trust Layer for Autonomous Agents** — Verifying AI capabilities on Hedera.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Built on Hedera](https://img.shields.io/badge/Built%20on-Hedera-7B3FE4)](https://hedera.com)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![Hackathon](https://img.shields.io/badge/Hackathon-Hello%20Future%20Apex%202026-orange)](https://hedera.com)

**ModernTensor** is a decentralized protocol that validates the quality and trustworthiness of AI Agents. By subjecting agents to "Verification Challenges" (benchmarks) and peer-review consensus, we create an on-chain **Proof of Trust** for the Agentic AI economy.

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/sonson0910/moderntensor_hedera.git
cd moderntensor_hedera
pip install -r requirements.txt
```

### 2. Run the Subnet (Benchmark Mode)

```bash
# Local benchmark — no Hedera account needed
python run_subnet.py --epochs 5

# On-chain mode — requires .env with Hedera credentials
python run_subnet.py --online --auto-register --epochs 10
```

### 3. Start the Trust Dashboard

```bash
cd dashboard-ui && npm install && npm run dev
```

---

## 💰 Unified Fee Model

All rewards in ModernTensor follow the same **85/8/5/2** split:

| Recipient                     | Share   | Description                          |
| ----------------------------- | ------- | ------------------------------------ |
| Miners (all, proportional)    | **85%** | Distributed by consensus score ratio |
| Validators (by stake)         | **8%**  | Stake-weighted validator rewards     |
| Staking Pool                  | **5%**  | Passive staking rewards              |
| Protocol Treasury             | **2%**  | DAO-controlled treasury              |

This applies to both:

- **Emission benchmarks** (`run_subnet.py`) — protocol-funded tasks for continuous evaluation
- **Marketplace paid tasks** (`fee_engine.py`) — customer-submitted tasks with on-chain escrow

**Emissions:** 25M MDT/year (68,493 MDT/day), halving every 2 years.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Subnet Orchestrator                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Miner   │  │  Miner   │  │Validator │  │Validator │ ...   │
│  │  (Axon)  │  │  (Axon)  │  │(Dendrite)│  │(Dendrite)│       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │             │              │              │
│  ┌────┴──────────────┴─────────────┴──────────────┴──────┐     │
│  │              SDK Protocol Layer                         │     │
│  │  ScoreConsensus │ WeightCalculator │ EmissionSchedule   │     │
│  └───────────────────────┬────────────────────────────────┘     │
│                          │                                      │
│  ┌───────────────────────┴────────────────────────────────┐     │
│  │          Hedera On-Chain Layer                          │     │
│  │  SubnetRegistryV2 │ StakingVaultV2 │ HCS │ MDT Token   │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### Key SDK Modules

| Module | Function |
|---|---|
| `ScoreConsensus` | Weighted median aggregation with IQR outlier detection |
| `WeightCalculator` | Merit-based miner weights (`performance² × reliability`) |
| `EmissionSchedule` | Epoch-level token emission tracking with halving |
| `Axon` / `Dendrite` | HTTP task communication (miner server / validator client) |
| `FeeEngine` | Dynamic marketplace fee calculation |

### Smart Contracts (Solidity on Hedera HSCS)

| Contract | Purpose |
|---|---|
| `SubnetRegistryV2` | Subnet/task/validation management |
| `StakingVaultV2` | Stake management with lock periods |
| `PaymentEscrow` | Escrow for paid marketplace tasks |
| `MDTGovernor` | On-chain governance (parameter proposals) |

---

## 📁 Project Structure

```
moderntensor_hedera/
├── run_subnet.py          # Main entry point — benchmark loop
├── run_miner.py           # Standalone miner node
├── run_validator.py        # Standalone validator node
├── test_onchain.py         # On-chain integration test
├── cli.py                  # Full marketplace CLI
├── sdk/
│   ├── protocol/           # Core protocol (axon, dendrite, emissions, fees, tasks)
│   ├── hedera/             # Hedera integration (client, HCS, contracts, HTS)
│   ├── scoring/            # Consensus, weights, benchmarks, PoI, PoQ
│   └── marketplace/        # Marketplace orchestrator & analytics
├── contracts/
│   ├── src/                # Solidity contracts
│   └── test/               # Hardhat tests (11 test files)
├── miners/                 # Miner implementations (code_review, text_gen, sentiment)
├── validators/             # Validator runner (AI validation orchestrator)
├── dashboard-ui/           # Next.js trust dashboard
├── docs/                   # Documentation (whitepaper, tokenomics, pitch)
└── scripts/                # Deploy and setup scripts
```

---

## 🛣️ Production Roadmap

Features planned beyond the hackathon MVP:

- **Slashing** — Stake penalties for malicious validators/miners
- **Multi-Account Demo** — Separate Hedera accounts per node for true decentralization
- **On-Chain Emission** — HTS scheduled minting instead of off-chain Python calculation
- **Commit-Reveal Consensus** — Prevent validators from copying each other's scores
- **Real AI Inference** — Replace simulated tasks with actual LLM workloads

---

## 📜 Documentation

- [**Whitepaper**](WHITEPAPER.md) — Full technical design
- [**Hackathon Strategy**](HACKATHON_README.md) — Submission guide
- [**Tokenomics**](docs/TOKENOMICS.md) — MDT token utility and supply schedule

---

## 📄 License

MIT License. Built for **Hello Future Apex Hackathon 2026**.
