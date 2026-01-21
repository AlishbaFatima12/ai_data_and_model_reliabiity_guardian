@echo off
title DMRG Dashboard
echo Starting DMRG Dashboard...
echo.
cd /d D:\ai_dmrg
python -m streamlit run dashboard/app.py --server.port 8650
pause
