"""
RDP ফাস্ট সার্ভার - ফিক্সড এবং অপটিমাইজড
"""

import socket
import threading
import struct
import pickle
import time
from PIL import ImageGrab
import cv2
import numpy as np
import pyautogui
from datetime import datetime

# কনফিগারেশন লোড
try:
    from config import *
    print("✓ config.py loaded")
except ImportError:
    SERVER_HOST = '0.0.0.0'
    SERVER_PORT = 5000
    SCREEN_FPS = 5
    SCREEN_QUALITY = 25
    SCREEN_WIDTH = 400
    SKIP_FRAMES = 1
    USE_GRAYSCALE = False
    USE_COMPRESSION = True
    ENABLE_LOGGING = True


class FastRDPServer:
    def __init__(self):
        self.clients = []
        self.running = False
        self.server_socket = None
        self.frame_counter = 0
        
        # স্ক্রিন সাইজ সেটআপ
        self.screen = pyautogui.size()
        self.screen_width = self.screen.width
        self.screen_height = self.screen.height
        ratio = self.screen_width / self.screen_height
        self.new_height = int(SCREEN_WIDTH / ratio)
        
        self.log(f"📺 স্ক্রিন: {self.screen_width}x{self.screen_height} → {SCREEN_WIDTH}x{self.new_height}")
        self.log(f"⚡ সেটিংস: FPS={SCREEN_FPS}, কোয়ালিটি={SCREEN_QUALITY}, স্কিপ={SKIP_FRAMES}")
        
    def log(self, message):
        if ENABLE_LOGGING:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
            
    def start(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # TCP_NODELAY ল্যাগ কমানোর জন্য
            self.server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.server_socket.bind((SERVER_HOST, SERVER_PORT))
            self.server_socket.listen(5)
            self.running = True
            
            self.log(f"✅ সার্ভার চালু: {SERVER_HOST}:{SERVER_PORT}")
            self.log(f"⏳ ক্লায়েন্টের জন্য অপেক্ষা...")
            print("\n" + "="*50)
            
            # থ্রেড শুরু
            threading.Thread(target=self._accept_clients, daemon=True).start()
            threading.Thread(target=self._broadcast_screen, daemon=True).start()
            
            while self.running:
                time.sleep(0.1)
                
        except Exception as e:
            self.log(f"❌ এরর: {e}")
            self.stop()
            
    def _accept_clients(self):
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                # TCP_NODELAY ক্লায়েন্টের জন্যও
                client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.log(f"🔗 ক্লায়েন্ট সংযুক্ত: {address[0]}")
                self.clients.append(client_socket)
                threading.Thread(target=self._handle_input, args=(client_socket, address), daemon=True).start()
            except Exception as e:
                if self.running:
                    self.log(f"⚠️ এরর: {e}")
                break
                
    def _handle_input(self, client_socket, address):
        while self.running:
            try:
                # ডাটার সাইজ পড়ুন
                raw_size = client_socket.recv(4)
                if not raw_size:
                    break
                    
                size = struct.unpack('>I', raw_size)[0]
                
                # সম্পূর্ণ ডাটা পড়ুন
                data = b''
                while len(data) < size:
                    chunk = client_socket.recv(size - len(data))
                    if not chunk:
                        break
                    data += chunk
                
                packet = pickle.loads(data)
                
                # মাউস ইভেন্ট
                if packet['type'] == 'mouse':
                    self._process_mouse(packet)
                # কিবোর্ড ইভেন্ট
                elif packet['type'] == 'keyboard':
                    self._process_keyboard(packet)
                    
            except Exception as e:
                break
                
        # ক্লায়েন্ট ডিসকানেক্ট
        if client_socket in self.clients:
            self.clients.remove(client_socket)
        try:
            client_socket.close()
        except:
            pass
        self.log(f"🔌 ক্লায়েন্ট ডিসকানেক্ট: {address[0]}")
        
    def _process_mouse(self, packet):
        try:
            action = packet.get('action', 'move')
            x = packet.get('x', 0)
            y = packet.get('y', 0)
            client_width = packet.get('client_width', 800)
            client_height = packet.get('client_height', 600)
            
            # রেজোলিউশন স্কেলিং
            if client_width > 0 and client_height > 0:
                scaled_x = int(x * self.screen_width / client_width)
                scaled_y = int(y * self.screen_height / client_height)
            else:
                scaled_x = x
                scaled_y = y
            
            # বাউন্ডারি চেক
            scaled_x = max(0, min(scaled_x, self.screen_width - 1))
            scaled_y = max(0, min(scaled_y, self.screen_height - 1))
            
            if action == 'move':
                pyautogui.moveTo(scaled_x, scaled_y)
            elif action == 'click':
                button = packet.get('button', 'left')
                pyautogui.click(scaled_x, scaled_y, button=button)
            elif action == 'double_click':
                pyautogui.doubleClick(scaled_x, scaled_y)
            elif action == 'scroll':
                amount = packet.get('amount', 0)
                pyautogui.scroll(amount, scaled_x, scaled_y)
                
        except Exception as e:
            if ENABLE_LOGGING:
                print(f"⚠️ মাউস এরর: {e}")
                
    def _process_keyboard(self, packet):
        try:
            action = packet.get('action', 'press')
            key = packet.get('key', '')
            
            if action == 'press':
                special_keys = {
                    'return': 'enter', 'backspace': 'backspace', 'delete': 'delete',
                    'tab': 'tab', 'escape': 'esc', 'space': 'space',
                    'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
                    'ctrl': 'ctrl', 'alt': 'alt', 'shift': 'shift'
                }
                
                if key in special_keys:
                    pyautogui.press(special_keys[key])
                elif len(key) == 1:
                    pyautogui.press(key)
                    
        except Exception as e:
            if ENABLE_LOGGING:
                print(f"⚠️ কিবোর্ড এরর: {e}")
                
    def _capture_screen(self):
        """দ্রুত স্ক্রিন ক্যাপচার"""
        try:
            # স্ক্রিন ক্যাপচার
            screenshot = ImageGrab.grab()
            
            # রিসাইজ
            screenshot = screenshot.resize((SCREEN_WIDTH, self.new_height))
            
            # গ্রেস্কেল (যদি চান)
            if USE_GRAYSCALE:
                screenshot = screenshot.convert('L')
                img = np.array(screenshot)
                img = np.stack((img,)*3, axis=-1)
            else:
                img = np.array(screenshot)
            
            # কম্প্রেশন
            if USE_COMPRESSION:
                img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), SCREEN_QUALITY]
                _, buffer = cv2.imencode('.jpg', img_bgr, encode_param)
                return buffer.tobytes()
            else:
                return img.tobytes()
                
        except Exception as e:
            self.log(f"⚠️ স্ক্রিন ক্যাপচার ব্যর্থ: {e}")
            return None
            
    def _broadcast_screen(self):
        """স্ক্রিন ব্রডকাস্ট - ফ্রেম স্কিপিং সহ"""
        frame_time = 1.0 / SCREEN_FPS
        skip = max(1, SKIP_FRAMES)
        
        while self.running:
            if not self.clients:
                time.sleep(0.02)
                continue
            
            # ফ্রেম স্কিপিং
            self.frame_counter += 1
            if self.frame_counter % skip != 0:
                time.sleep(0.005)
                continue
                
            start_time = time.time()
            
            # স্ক্রিন ক্যাপচার
            img_bytes = self._capture_screen()
            if img_bytes is None:
                time.sleep(0.01)
                continue
            
            # প্যাকেট তৈরি
            packet = {
                'type': 'screen',
                'data': img_bytes,
                'size': len(img_bytes),
                'width': SCREEN_WIDTH,
                'height': self.new_height
            }
            
            try:
                data_bytes = pickle.dumps(packet)
                data_len = struct.pack('>I', len(data_bytes))
            except Exception as e:
                continue
            
            # সব ক্লায়েন্টে পাঠান
            disconnected = []
            for client in self.clients:
                try:
                    client.send(data_len)
                    client.send(data_bytes)
                except:
                    disconnected.append(client)
            
            # ডিসকানেক্টেড ক্লায়েন্ট সরান
            for client in disconnected:
                if client in self.clients:
                    self.clients.remove(client)
            
            # ফ্রেম রেট কন্ট্রোল
            elapsed = time.time() - start_time
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                time.sleep(0.001)  # মিনিমাম স্লিপ
                
    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        self.log("✅ সার্ভার বন্ধ")


def main():
    print("""
    ╔══════════════════════════════════════════╗
    ║     ⚡ RDP ফাস্ট সার্ভার                 ║
    ║     মাল্টি-ইউজার পিসি শেয়ারিং          ║
    ╚══════════════════════════════════════════╝
    """)
    
    try:
        server = FastRDPServer()
        server.start()
    except KeyboardInterrupt:
        print("\n🛑 সার্ভার বন্ধ করা হচ্ছে...")
        if 'server' in locals():
            server.stop()
    except Exception as e:
        print(f"❌ ফ্যাটাল এরর: {e}")


if __name__ == "__main__":
    main()