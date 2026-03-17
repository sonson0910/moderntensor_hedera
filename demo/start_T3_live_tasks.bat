@echo off
title Terminal 3 — LIVE TASKS (On-Chain Demo for Judges)
color 0E
echo ============================================================
echo   TERMINAL 3 — LIVE TASK SUBMISSION (ON-CHAIN)
echo   Interactive demo for judges
echo ============================================================
echo.
echo   NOTE: Start Terminal 1 (Miner) first!
echo.
timeout /t 3
python demo\demo_live_tasks.py --onchain
pause
