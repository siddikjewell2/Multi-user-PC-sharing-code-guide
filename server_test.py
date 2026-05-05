import pyautogui
import time

print("5 সেকেন্ডে মাউস auto-move হবে...")
time.sleep(5)
pyautogui.moveTo(500, 500)
print("✅ মাউস মুভ হয়েছে!")