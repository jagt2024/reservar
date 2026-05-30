@echo off
chcp 65001 >nul
title SolarCalc Pro ☀
streamlit run solar_app.py --server.port 8501
