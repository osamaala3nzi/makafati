@echo off
chcp 65001 >nul
title مكافأتي - تشغيل المشروع
echo =======================================
echo    مكافأتي - منصة ادارة المكافأة
echo =======================================
cd /d "%~dp0"
"C:\Users\alaan\AppData\Local\Programs\Python\Python314\python.exe" app.py
pause
