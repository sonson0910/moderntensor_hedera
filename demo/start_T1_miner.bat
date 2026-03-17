@echo off
title Terminal 1 — MINER (Gemini AI Engine) — ON-CHAIN
color 0A
echo ============================================================
echo   TERMINAL 1 — MINER NODE (ON-CHAIN)
echo   ModernTensor on Hedera Testnet
echo ============================================================
echo.
echo   Starting Miner with on-chain registration...
echo   Port: 8091  ^|  Auto-register + stake 1000 MDT
echo.
python run_miner.py --subnet 0 --port 8091 --auto-register --stake 1000
pause
