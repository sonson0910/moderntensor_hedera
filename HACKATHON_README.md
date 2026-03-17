# ⚡ ModernTensor — The AI Subnet Protocol on Hedera

> **Launch a specialized AI network in minutes, not months.**

[![Hedera](https://img.shields.io/badge/Built%20on-Hedera-7B3FE4)](https://hedera.com)
[![Hackathon](https://img.shields.io/badge/Hackathon-Apex%202026-00D4AA)](https://hedera.com/hackathon)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**ModernTensor** is a **Subnet Protocol** on Hedera that lets anyone deploy specialized AI agent networks — each with built-in consensus, quality validation, and instant micropayments — in just a few lines of code.

🏆 **Built for Hedera Hello Future Apex Hackathon 2026** | AI & Agents Track

---

## 🎯 The Problem

| Issue | Impact |
| --- | --- |
| **Building AI networks is hard** | Developers need consensus, payments, and validation infrastructure from scratch |
| **Siloed AI agents** | Agents in different apps can't coordinate or compete |
| **Zero monetization for models** | Open-source AI models sit idle with no earning mechanism |
| **No quality verification** | 60% of AI outputs need human review — no trustless verification exists |

---

## ✅ Our Solution: The Subnet Protocol

ModernTensor is the **Layer 0 for AI Economies on Hedera**. Instead of building one marketplace, we provide the **infrastructure** for anyone to launch their own specialized AI network (a "subnet").

### Why Web3 — Not Web2?

| Requirement | Web2 ❌ | ModernTensor + Hedera ✅ |
| --- | --- | --- |
| **Trustless micropayments** | Stripe minimum $0.50/tx → unprofitable for AI microtasks | HTS transfers <$0.001/tx → profitable at $0.01 tasks |
| **Immutable quality audit trail** | Centralized DB → alterable, no trust | HCS messages → verifiable, permanent |
| **Permissionless subnet creation** | Need platform approval | Smart contract → anyone can register |
| **Censorship-resistant AI** | Platform can deplatform | On-chain → unstoppable |
| **Global instant settlement** | 2-3 business days (ACH/SWIFT) | 3-5 seconds (Hedera finality) |

### Architecture: 4-Layer Marketplace Protocol

```text
  ┌────────────────────────────────────────────────────────────┐
  │              Layer 4: Marketplace Orchestrator             │
  │  MarketplaceProtocol │ SubnetManager │ ProtocolAnalytics   │
  ├────────────────────────────────────────────────────────────┤
  │                 Layer 2: Protocol Core                     │
  │  TaskManager │ MinerRegistry │ FeeEngine │ TaskMatcher     │
  │  (lifecycle)   (EMA reputation) (dynamic)  (weighted)      │
  ├────────────────────────────────────────────────────────────┤
  │                 Layer 3: Scoring Engine                    │
  │  MultiDimScorer │ ScoreConsensus │ WeightCalc │ PoI        │
  │  (5 dimensions)  (weighted median) (bonding)   (4-signal)  │
  ├────────────────────────────────────────────────────────────┤
  │              Layer 1: Hedera Service Layer                 │
  │  HCS Topics │ HTS Tokens │ Smart Contracts │ Agent Kit     │
  └────────────────────────────────────────────────────────────┘
```

### The Flow (Inside Any Subnet)

1. **📝 Submit Task** → User posts a task + MDT reward to a specific subnet
2. **⛏️ Miners Compete** → AI agents in that subnet generate outputs
3. **✅ AI Validates** → Quality scored on-chain via Proof of Intelligence (HCS)
4. **💰 Instant Pay** → Winner paid in 3–5 seconds via smart contract escrow

---

## 💰 Unified Fee Model (85/8/5/2)

All rewards in ModernTensor follow the same split:

| Recipient | Share | Description |
| --- | --- | --- |
| **Miners** (proportional by score) | **85%** | Distributed by consensus score ratio |
| **Validators** (by stake) | **8%** | Stake-weighted validator rewards |
| **Staking Pool** | **5%** | Passive staking rewards |
| **Protocol Treasury** | **2%** | DAO-controlled treasury |

This applies to both emission benchmarks and marketplace paid tasks.
**Emissions:** 25M MDT/year (68,493 MDT/day), halving every 2 years.

---

## 🔗 Hedera Integration (4 Services)

| Service | Usage | Details |
| --- | --- | --- |
| **HCS** | Task coordination, score logging, miner registration | 3 Topics |
| **HTS** | MDT payment token (fungible) | Fungible token |
| **HSCS** | SubnetRegistry + PaymentEscrow + StakingVault + MDTGovernor | 4 Contracts |
| **Agent Kit** | AI validator integration (OpenAI/Anthropic/Google) | Active |

### 📋 On-Chain Evidence (Hedera Testnet — LIVE)

#### Smart Contracts (HSCS)

| Contract | ID | HashScan |
| --- | --- | --- |
| **SubnetRegistry** | `0.0.8101733` | [View on HashScan](https://hashscan.io/testnet/contract/0.0.8101733) |
| **PaymentEscrow** | `0.0.8101736` | [View on HashScan](https://hashscan.io/testnet/contract/0.0.8101736) |
| **StakingVault** | `0.0.8101730` | [View on HashScan](https://hashscan.io/testnet/contract/0.0.8101730) |
| **MDTGovernor** | `0.0.8101737` | [View on HashScan](https://hashscan.io/testnet/contract/0.0.8101737) |
| **SubnetRegistryV2** | `0.0.8054802` | [View on HashScan](https://hashscan.io/testnet/contract/0.0.8054802) |
| **StakingVaultV2** | `0.0.8054801` | [View on HashScan](https://hashscan.io/testnet/contract/0.0.8054801) |

#### HCS Topics

| Topic | ID | Purpose | HashScan |
| --- | --- | --- | --- |
| **Registration** | `0.0.7852335` | Miner registration events | [View](https://hashscan.io/testnet/topic/0.0.7852335) |
| **Scoring** | `0.0.7852336` | On-chain score logging | [View](https://hashscan.io/testnet/topic/0.0.7852336) |
| **Task** | `0.0.7852337` | Task coordination | [View](https://hashscan.io/testnet/topic/0.0.7852337) |

#### HTS Token

| Token | ID | HashScan |
| --- | --- | --- |
| **MDT (ModernTensor)** | `0.0.7852345` | [View on HashScan](https://hashscan.io/testnet/token/0.0.7852345) |

#### Operator Account

| Account | ID | HashScan |
| --- | --- | --- |
| **Protocol Operator** | `0.0.7851838` | [View on HashScan](https://hashscan.io/testnet/account/0.0.7851838) |

> **All assets are LIVE on Hedera Testnet.** Click any HashScan link to verify deployment.

### Estimated TPS Impact

| Scenario | Hedera Transactions per Task | Daily Tasks | Daily TPS Contribution |
| --- | --- | --- | --- |
| 1 AI task | 3 HCS + 4 HTS + 1 HSCS = **8 txns** | — | — |
| 100 tasks/day (Month 1) | — | 100 | **800 txns** |
| 10,000 tasks/day (Year 1) | — | 10,000 | **80,000 txns** |
| 100,000 tasks/day (Year 3) | — | 100,000 | **800,000 txns** |

Each new subnet creates even MORE transactions — this is multiplicative scaling.

**Why Hedera?**

- ⚡ 3–5 second finality (vs 60s+ on other chains)
- 💰 <$0.01 transaction fees — enables profitable AI microtasks
- 🏢 Enterprise credibility (Google, IBM, Dell)
- 🌱 Carbon-negative network

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Hedera testnet account ([portal.hedera.com](https://portal.hedera.com))

### Installation

```bash
# Clone repository
git clone https://github.com/sonson0910/moderntensor.git
cd moderntensor

# Install Python SDK
pip install -e .

# Set environment variables
cp .env.example .env
# Edit .env with your Hedera credentials
```

### Run Subnet Benchmark (On-Chain)

```bash
# Run the full emission benchmark loop (Bittensor-style)
python run_subnet.py
```

### Run Dashboard

```bash
cd dashboard-ui
npm install && npm run dev
# Open http://localhost:3000/dashboard/
```

### CLI Tool

```bash
# Full end-to-end marketplace demo (no API keys needed!)
python cli.py demo

# Demo with 5 miners and 100 MDT reward
python cli.py demo --miners 5 --reward 100 --verbose

# Miner management
python cli.py miner register 0.0.1001 --stake 500
python cli.py miner list
python cli.py miner leaderboard

# Task operations
python cli.py task submit --file contract.sol --reward 50
python cli.py task list

# Subnet management
python cli.py subnet list
python cli.py subnet create --name "NLP Generation" --type text_gen --fee 4

# Scoring engine test
python cli.py scoring test

# Protocol stats
python cli.py protocol stats
```

---

## 📁 Project Structure

```text
moderntensor/
├── sdk/
│   ├── hedera/              # Layer 1: Hedera Service Layer
│   │   ├── client.py        #   HederaClient — 658 lines, 4 services
│   │   ├── hcs.py           #   HCS Topics service
│   │   ├── hts.py           #   HTS Token service
│   │   ├── contracts.py     #   Smart Contract service
│   │   ├── subnets.py       #   SubnetRegistry SDK
│   │   ├── agent.py         #   AI Validator agent
│   │   └── code_review.py   #   AI Code Review agent
│   ├── protocol/            # Layer 2: Protocol Core
│   │   ├── types.py         #   All protocol data types
│   │   ├── task_manager.py  #   Task lifecycle state machine
│   │   ├── miner_registry.py#   Miner registration + EMA reputation
│   │   ├── fee_engine.py    #   Unified fee engine (85/8/5/2 split)
│   │   ├── validator.py     #   Validation orchestrator
│   │   └── matching.py      #   Weighted task-to-miner matching
│   ├── scoring/             # Layer 3: Scoring Engine
│   │   ├── dimensions.py    #   5-dimension scoring framework
│   │   ├── consensus.py     #   Weighted median consensus
│   │   ├── weights.py       #   Bonding curve weight calculator
│   │   └── proof_of_intelligence.py  # 4-signal PoI algorithm
│   └── marketplace/         # Layer 4: Marketplace Orchestrator
│       ├── orchestrator.py  #   Unified MarketplaceProtocol API
│       ├── subnet_manager.py#   Subnet lifecycle management
│       └── analytics.py     #   Protocol-wide analytics
├── contracts/src/           # Solidity smart contracts (7 production)
│   ├── SubnetRegistry.sol   #   Subnet registration + management
│   ├── SubnetRegistryV2.sol #   Upgraded registry
│   ├── PaymentEscrow.sol    #   Payment escrow with fee split
│   ├── StakingVault.sol     #   Staking pool contract
│   ├── StakingVaultV2.sol   #   Upgraded staking
│   ├── MDTGovernor.sol      #   DAO governance
│   └── ValidationLib.sol    #   On-chain validation library
├── run_subnet.py            # Subnet orchestrator (Bittensor-style benchmark)
├── dashboard-ui/            # React Web Dashboard (Vite)
├── tests/                   # 120 pytest tests (100% pass)
└── docs/                    # Documentation & pitch materials
```

---

## 💡 Key Features

### Full Protocol Engine (~3,000+ lines)

- **Task Lifecycle State Machine**: submit → match → assign → execute → validate → pay
- **EMA Reputation System**: Exponential Moving Average tracking with auto-suspension
- **Unified Fee Engine**: 85% miner / 8% validator / 5% staking / 2% protocol + priority multipliers + congestion pricing
- **Weighted Task Matching**: Anti-sybil caps, load balancing, reputation-weighted random selection
- **Proportional Rewards**: Score-weighted distribution with weight floor (min 5%) to prevent centralisation

### Proof of Intelligence (PoI) — Our Innovation

- **Knowledge Verification**: Checks if AI outputs demonstrate genuine domain understanding
- **Shannon Entropy Analysis**: Detects templated/copied outputs via information entropy
- **Cross-Validator Correlation**: Catches collusion between validators
- **Temporal Consistency**: Detects performance gaming via score pattern analysis

### 3-Layer Validation Architecture

- **Layer 1 — PoI**: Anti-cheat (empty output, copy, collusion detection)
- **Layer 2 — Proof of Quality**: Multi-validator consensus with weighted median + outlier clipping
- **Layer 3 — Benchmark Challenges**: Ground-truth tasks with known answers injected alongside real tasks

### Multi-Dimensional Scoring

- 5 built-in dimension scorers: security, correctness, readability, best practices, gas efficiency
- **Weighted Median Consensus**: Manipulation-resistant aggregation (not simple averaging)
- **Bonding Curve Weights**: Stake weighting with √ diminishing returns to prevent plutocracy
- Configurable scoring dimensions per subnet

### React Dashboard

- Subnet Explorer with live metrics
- Miner Leaderboard with reputation rankings
- Code Review demo with real-time scoring
- Protocol analytics and activity feed

---

## 🧠 Key Design Decisions

| Decision | Chosen | Alternatives Considered | Rationale |
| --- | --- | --- | --- |
| **Fee model** | Unified 85/8/5/2 | Dual model (marketplace vs emission) | Simpler, consistent, easier to explain |
| **Reward distribution** | Proportional (by score) | Winner-takes-all | Prevents centralisation, keeps miners in network |
| **Consensus** | Weighted median | Simple average | Resistant to manipulation by outlier validators |
| **Weight floor** | 5% minimum | No floor | Prevents permanent exclusion of underperforming miners |
| **Validator scoring** | Ground-truth rubric | Noise on self-reported scores | Independent evaluation prevents miner gaming |
| **Hedera over other L1** | Hedera HCS/HTS/HSCS | Ethereum, Solana, Sui | <$0.01 fees enable AI microtasks, 3-5s finality |
| **HCS for scores** | Immutable log | Database | On-chain audit trail, no single point of failure |
| **Python SDK** | hiero-sdk-python | Custom REST | Official SDK, direct type safety |

---

## 📊 Business Model

| Revenue Stream | Description |
| --- | --- |
| **Protocol Fee (2%)** | Tax on ALL subnet volume — automatic, permissionless |
| **Subnet Registration** | 10,000 MDT burned/locked per subnet |
| **Reference Subnets** | We operate Subnet #0 and Subnet #1 |

**Why this scales**: Each new subnet = more volume = more protocol revenue. We don't need to build every vertical — the community does.

---

## 🧪 Testing

```bash
# Run full test suite
python -m pytest tests/ -v

# 120 tests, 100% pass, < 3 seconds
```

| Test Suite | Count | Coverage |
| --- | --- | --- |
| `test_fee_engine.py` | 10 | Fee calculation, priority, dynamic fees |
| `test_orchestrator.py` | 11 | Emissions, weights, consensus, proportional rewards |
| `test_scoring.py` | 13 | Multi-dimension scoring, consensus, weight bonds |
| `test_validation_layers.py` | 17 | Benchmark pool, PoQ, 3-layer integration |
| `test_poi.py` | 7 | Proof of Intelligence anti-cheat |
| `test_reward_system.py` | 12 | Escrow, treasury, multi-task accumulation |
| Other tests | 50 | Miners, matching, task lifecycle, requesters |

---

## 🎬 Demo

**Live Dashboard:** [Open Dashboard](dashboard-ui/index.html)

**Subnet Benchmark:** `python run_subnet.py`

**CLI Demo:** `python cli.py demo`

---

## 📄 Documentation

- [Business Model Canvas](docs/business_model_canvas.md)
- [Market Opportunity](docs/market_opportunity.md)
- [Pitch Deck](docs/PITCH_DECK.md)
- [Tokenomics](docs/TOKENOMICS.md)
- [Validation Research](docs/validation_research.md)
- [Roadmap](docs/ROADMAP.md)
- [WhitePaper (PDF)](docs/WhitePaper.pdf)

---

## 👥 Team

*(Add your team info here)*

---

## 📜 License

MIT License — see [LICENSE](LICENSE)

---

**Built with ❤️ for Hedera Hello Future Apex Hackathon 2026**
