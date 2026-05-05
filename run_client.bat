@echo off
title RDP Fast Client
color 0f
cls
echo ========================================
echo    ⚡ RDP ফাস্ট ক্লায়েন্ট চালু হচ্ছে
echo ========================================
echo.
echo প্রথমে config.py এ SERVER_IP ঠিক করুন!
echo বর্তমান IP: 
findstr "REMOTE_SERVER_IP" config.py
echo.
pause
python client.py
pause