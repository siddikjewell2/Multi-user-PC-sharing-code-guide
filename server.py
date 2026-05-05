# RDP সার্ভার - যেই কম্পিউটার শেয়ার করতে চান সেখানে এই কোড রান করান

import socket
import threading
import struct
import pickle
import time
import sys
from PIL import ImageGrab
import cv2
import numpy as np
import pyautogui
from datetime import datetime

# কনফিগারেশন
try:
    from config import SERVER_HOST, SERVER_PORT, SCREEN_FPS, SCREEN_QUALITY, SCREEN_WIDTH, ENABLE_LOGGING
    print('✓ config.py loaded successfully')
except ImportError:
    print('⚠️ config.py not found, using defaults')
    SERVER_HOST = '0.0.0.0'
    SERVER_PORT = 5000
    SCREEN_FPS = 20
    SCREEN_QUALITY = 70
    SCREEN_WIDTH = 800
    ENABLE_LOGGING = True
except NameError:
    print('⚠️ Config variables missing, using defaults')
    SERVER_HOST = '0.0.0.0'
    SERVER_PORT = 5000
    SCREEN_FPS = 20
    SCREEN_QUALITY = 70
    SCREEN_WIDTH = 800
    ENABLE_LOGGING = True

class RDPServer:
    def __init__(self, host=SERVER_HOST, port=SERVER_PORT):
        self.host = host
        self.port = port
        self.clients = []
        self.server_socket = None
        self.running = False
        self.frame_count = 0
        self.start_time = time.time()
        
        self.screen = pyautogui.size()
        self.screen_width = self.screen.width
        self.screen_height = self.screen.height
        self.calc_new_size()
        
        self.log(f"সার্ভার ইনিশিয়ালাইজড: স্ক্রিন {self.screen_width}x{self.screen_height}")
        
    def calc_new_size(self):
        self.new_width = SCREEN_WIDTH
        ratio = self.screen_width / self.screen_height
        self.new_height = int(self.new_width / ratio)
        
    def log(self, message):
        if ENABLE_LOGGING:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
            
    def start(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            self.log(f"✅ সার্ভার চালু হয়েছে {self.host}:{self.port}")
            self.log(f"📺 স্ক্রিন: {self.screen_width}x{self.screen_height}")
            self.log("⏳ ক্লায়েন্টের জন্য অপেক্ষা...")
            print("\n" + "="*50)
            
            accept_thread = threading.Thread(target=self._accept_clients, daemon=True)
            accept_thread.start()
            
            broadcast_thread = threading.Thread(target=self._broadcast_screen, daemon=True)
            broadcast_thread.start()
            
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            self.log(f"❌ Error: {e}")
            self.stop()
            
    def _accept_clients(self):
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                self.log(f"🔗 New client: {address[0]}:{address[1]}")
                self.clients.append(client_socket)
                
                client_thread = threading.Thread(
                    target=self._handle_client_input,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    self.log(f"⚠️ Error: {e}")
                break
                
    def capture_screen(self):
        try:
            screenshot = ImageGrab.grab()
            screenshot = screenshot.resize((self.new_width, self.new_height))
            img_np = np.array(screenshot)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), SCREEN_QUALITY]
            _, buffer = cv2.imencode('.jpg', img_bgr, encode_param)
            return buffer.tobytes()
        except Exception as e:
            return None
            
    def _broadcast_screen(self):
        while self.running:
            if not self.clients:
                time.sleep(0.1)
                continue
            
            img_bytes = self.capture_screen()
            if img_bytes is None:
                continue
                
            packet = {
                'type': 'screen',
                'data': img_bytes,
                'size': len(img_bytes),
                'screen_size': (self.new_width, self.new_height)
            }
            
            try:
                data_bytes = pickle.dumps(packet)
                data_len = struct.pack('>I', len(data_bytes))
            except:
                continue
            
            disconnected_clients = []
            for client in self.clients:
                try:
                    client.send(data_len)
                    client.send(data_bytes)
                    self.frame_count += 1
                except:
                    disconnected_clients.append(client)
            
            for client in disconnected_clients:
                if client in self.clients:
                    self.clients.remove(client)
                    self.log("🔌 Client disconnected")
            
            time.sleep(1.0 / SCREEN_FPS)
            
    def _handle_client_input(self, client_socket, address):
        while self.running:
            try:
                raw_size = client_socket.recv(4)
                if not raw_size:
                    break
                    
                size = struct.unpack('>I', raw_size)[0]
                data = b''
                while len(data) < size:
                    chunk = client_socket.recv(size - len(data))
                    if not chunk:
                        break
                    data += chunk
                
                packet = pickle.loads(data)
                
                if packet['type'] == 'mouse':
                    self._process_mouse_event(packet)
                elif packet['type'] == 'keyboard':
                    self._process_keyboard_event(packet)
                    
            except:
                break
                
    def _process_mouse_event(self, packet):
        try:
            action = packet.get('action', 'move')
            x = int(packet.get('x', 0))
            y = int(packet.get('y', 0))
            client_width = packet.get('client_width', SCREEN_WIDTH)
            client_height = packet.get('client_height', SCREEN_WIDTH)
            
            scaled_x = int(x * self.screen_width / client_width)
            scaled_y = int(y * self.screen_height / client_height)
            
            scaled_x = max(0, min(scaled_x, self.screen_width - 1))
            scaled_y = max(0, min(scaled_y, self.screen_height - 1))
            
            if action == 'move':
                pyautogui.moveTo(scaled_x, scaled_y)
            elif action == 'click':
                button = packet.get('button', 'left')
                pyautogui.click(scaled_x, scaled_y, button=button)
            elif action == 'scroll':
                amount = packet.get('amount', 0)
                pyautogui.scroll(amount, scaled_x, scaled_y)
        except:
            pass
            
    def _process_keyboard_event(self, packet):
        try:
            action = packet.get('action', 'press')
            key = packet.get('key', '')
            
            if action == 'press':
                special_keys = {
                    'return': 'enter', 'backspace': 'backspace', 'delete': 'delete',
                    'tab': 'tab', 'escape': 'esc', 'space': 'space'
                }
                if key in special_keys:
                    pyautogui.press(special_keys[key])
                elif len(key) == 1:
                    pyautogui.press(key)
        except:
            pass
                
    def stop(self):
        self.running = False
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        if self.server_socket:
            self.server_socket.close()
        self.log("✅ সার্ভার বন্ধ")

def main():
    print("""
    ╔══════════════════════════════════════════╗
    ║     🖥️  RDP সার্ভার                      ║
    ╚══════════════════════════════════════════╝
    """)
    print("📋 নির্দেশনা:")
    print("   1. এই PC টি অন্যরা কন্ট্রোল করবে")
    print("   2. অন্য PC থেকে client.py রান করান")
    print("   3. Ctrl+C চেপে বন্ধ করুন")
    print("="*50)
    
    try:
        server = RDPServer()
        server.start()
    except KeyboardInterrupt:
        print("\n🛑 বন্ধ করা হচ্ছে...")
        if 'server' in locals():
            server.stop()

if __name__ == "__main__":
    main()