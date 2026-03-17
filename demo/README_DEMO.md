# 🎬 ModernTensor — Hackathon Demo Guide

## Chuẩn bị

```bash
pip install -r requirements.txt
```

Đảm bảo `.env` có `GOOGLE_API_KEY` (Gemini), `HEDERA_ACCOUNT_ID`, `HEDERA_PRIVATE_KEY`, v.v.

---

## Layout 4 Terminal

```text
┌──────────────────────────────┬──────────────────────────────┐
│  TERMINAL 1 — MINER          │  TERMINAL 2 — VALIDATOR       │
│  (Gemini AI Engine)           │  (Task Creator + Scorer)     │
│  🟢 Axon HTTP Server          │  🔵 Dendrite Client → Miners  │
│  Port 8091                    │  Send tasks → Score → HCS    │
├──────────────────────────────┼──────────────────────────────┤
│  TERMINAL 3 — LIVE TASKS      │  TERMINAL 4 — MONITOR        │
│  (ON-CHAIN task submission)   │  (On-chain + HashScan)       │
│  SubnetRegistry + HCS        │  Health check, stats, tx     │
└──────────────────────────────┴──────────────────────────────┘
```

---

## Bước chạy (theo thứ tự)

### Terminal 1 — MINER 🟢

```bash
python run_miner.py --subnet 0 --auto-register --stake --onchain --port 8091
```

> Miner khởi động, auto register + stake on-chain, Gemini AI engine online, chờ tasks.

### Terminal 2 — VALIDATOR 🔵

```bash
python run_validator.py --subnet 0 --auto-register --stake --onchain --miners http://localhost:8091 --task-interval 30
```

> Validator tạo tasks, gửi cho Miner, chấm điểm, report lên HCS + SubnetRegistry.

### Terminal 3 — LIVE TASKS 🟡

```bash
python demo\demo_live_tasks.py --onchain
```

> Gửi tasks ON-CHAIN: SubnetRegistry.createTask() → Miner AI → submitResult() → HCS logging.

### Terminal 4 — MONITOR 🔴

```bash
python demo\demo_monitor.py
```

> Theo dõi health, stats, on-chain status (Contract, HCS topics, HashScan links).

---

## Demo Flow cho Giám Khảo

1. **Mở T1** → "Đây là Miner node, auto-register + stake on-chain, chạy Gemini 2.0 Flash"
2. **Mở T2** → "Validator tạo task on-chain, gửi cho miner qua Dendrite protocol"
3. **T1 log hiện** → "Miner nhận task, Gemini phân tích code real-time"
4. **T2 log hiện** → "Validator chấm điểm, submit score on-chain qua SubnetRegistry + HCS"
5. **Chạy T3** → "Giờ ta gửi task ON-CHAIN — create_task() → AI → submitResult()"
6. **T3 hiện result** → "AI trả về phân tích, result hash submitted on-chain"
7. **T4 hiện stats** → "Tất cả verified on HashScan — link cho judge click vào xem"

---

## Tips

- **Zoom in** Terminal cho judge đọc được
- Chạy T1 trước, đợi "Axon server running", rồi mới chạy T2
- T3 là show-off moment — task cycle ON-CHAIN end-to-end
- `--onchain` flag bật SubnetRegistry + HCS integration
