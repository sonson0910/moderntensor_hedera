@echo off
title Terminal 2 — VALIDATOR (On-Chain Task Creator + Scorer)
color 09
echo ============================================================
echo   TERMINAL 2 — VALIDATOR NODE (ON-CHAIN)
echo   ModernTensor on Hedera Testnet
echo ============================================================
echo.
echo   Starting Validator with on-chain registration...
echo   Miners: http://localhost:8091
echo   Task interval: 30s  ^|  Reward: 10 MDT/task
echo   Auto-register + stake 50000 MDT
echo.
echo   NOTE: Start Terminal 1 (Miner) first!
echo.
timeout /t 5
python run_validator.py --subnet 0 --auto-register --stake 50000 --miners http://localhost:8091 --task-interval 30 --task-reward 10
pause
