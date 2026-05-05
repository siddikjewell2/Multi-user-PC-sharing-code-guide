@echo off
title RDP Project to EXE Converter
color 0e
echo ========================================
echo    RDP Project to EXE Converter
echo ========================================
echo.

echo [1] Installing PyInstaller...
pip install pyinstaller

echo.
echo [2] Building RDP Server...
pyinstaller --onefile --name "RDPServer" --console server.py

echo.
echo [3] Building RDP Client...
pyinstaller --onefile --name "RDPClient" --noconsole --add-data "config.py;." --hidden-import "PIL" --hidden-import "cv2" --hidden-import "numpy" --hidden-import "pyautogui" client.py

echo.
echo ========================================
echo    Build Complete!
echo ========================================
echo.
echo Server: dist\RDPServer.exe
echo Client: dist\RDPClient.exe
echo.
pause