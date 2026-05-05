"""
RDP ফাস্ট ক্লায়েন্ট - ফিক্সড এবং অপটিমাইজড
একাধিক উইন্ডো খোলা বন্ধসহ
"""

import sys
import os
import tempfile
import atexit

# ============================================================
# একাধিক উইন্ডো চেক - শুধুমাত্র একটি ক্লায়েন্ট চলতে পারবে
# ============================================================
lock_file = os.path.join(tempfile.gettempdir(), "rdp_client_fast.lock")

try:
    with open(lock_file, 'x') as f:
        f.write(str(os.getpid()))
    print("✅ RDP ক্লায়েন্ট চালু হচ্ছে...")
except FileExistsError:
    print("")
    print("="*60)
    print("❌ RDP ক্লায়েন্ট ইতিমধ্যে চলছে!")
    print("="*60)
    print("")
    print("শুধুমাত্র একটি ক্লায়েন্ট উইন্ডো খোলা যাবে।")
    print("আগের উইন্ডোটি ব্যবহার করুন বা বন্ধ করুন।")
    print("")
    input("Enter চাপুন...")
    sys.exit(0)

def cleanup_lock():
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except:
        pass

atexit.register(cleanup_lock)

# ============================================================
# ইম্পোর্ট লাইব্রেরি
# ============================================================
import socket
import threading
import struct
import pickle
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import time
from datetime import datetime

# ============================================================
# কনফিগারেশন - এখানে আপনার সার্ভারের IP দিন
# ============================================================
try:
    from config import REMOTE_SERVER_IP, SERVER_PORT, CLIENT_WINDOW_WIDTH, CLIENT_WINDOW_HEIGHT, ENABLE_LOGGING
except ImportError:
    REMOTE_SERVER_IP = '192.168.0.113'
    SERVER_PORT = 5000
    CLIENT_WINDOW_WIDTH = 800
    CLIENT_WINDOW_HEIGHT = 600
    ENABLE_LOGGING = True


class FastRDPClient:
    def __init__(self, server_host=REMOTE_SERVER_IP, server_port=SERVER_PORT):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None
        self.running = False
        self.root = None
        self.canvas = None
        self.status_label = None
        self.fps_label = None
        self.current_image = None
        self.frame_count = 0
        self.start_time = time.time()
        self.is_fullscreen = False
        self.last_frame_time = 0
        
    def log(self, message):
        if ENABLE_LOGGING:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
            
    def connect(self):
        try:
            self.log(f"🔌 কানেক্ট করছি {self.server_host}:{self.server_port}...")
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.settimeout(3)
            self.socket.connect((self.server_host, self.server_port))
            self.socket.settimeout(None)
            
            self.running = True
            self.log(f"✅ সংযোগ সফল!")
            
            self._setup_gui()
            
            receive_thread = threading.Thread(target=self._receive_screen, daemon=True)
            receive_thread.start()
            
            monitor_thread = threading.Thread(target=self._monitor_performance, daemon=True)
            monitor_thread.start()
            
            return True
            
        except socket.timeout:
            self.log(f"❌ টাইমআউট: {self.server_host}")
            messagebox.showerror("সংযোগ ব্যর্থ", f"সার্ভার {self.server_host} এ পৌঁছানো যায়নি\n\nচেক করুন:\n1. সার্ভার চালু আছে?\n2. আইপি সঠিক?\n3. ফায়ারওয়াল ওপেন?")
            return False
        except ConnectionRefusedError:
            self.log(f"❌ সংযোগ প্রত্যাখ্যান")
            messagebox.showerror("সংযোগ ব্যর্থ", "সার্ভার কি চালু আছে?")
            return False
        except Exception as e:
            self.log(f"❌ সংযোগ ব্যর্থ: {e}")
            messagebox.showerror("সংযোগ ব্যর্থ", str(e))
            return False
            
    def _setup_gui(self):
        if self.root is not None:
            try:
                if self.root.winfo_exists():
                    self.root.lift()
                    self.root.focus_force()
                    return
            except:
                pass
        
        self.root = tk.Tk()
        self.root.title(f"RDP ক্লায়েন্ট - {self.server_host}")
        self.root.geometry(f"{CLIENT_WINDOW_WIDTH}x{CLIENT_WINDOW_HEIGHT}")
        self.root.minsize(480, 360)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # স্টাইল
        self.root.configure(bg='#1a1a1a')
        
        # FPS লেবেল
        self.fps_label = tk.Label(
            self.root, 
            text="FPS: --", 
            bg='#1a1a1a', 
            fg='#00ff00',
            font=("Arial", 10, "bold")
        )
        self.fps_label.pack(side=tk.TOP, anchor=tk.NE, padx=10, pady=5)
        
        # টুলবার
        toolbar = tk.Frame(self.root, bg='#2d2d2d', height=35)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        disconnect_btn = tk.Button(
            toolbar, 
            text="🔌 ডিসকানেক্ট", 
            command=self.disconnect,
            bg='#ff4444', 
            fg='white',
            font=("Arial", 9)
        )
        disconnect_btn.pack(side=tk.LEFT, padx=5, pady=2)
        
        fullscreen_btn = tk.Button(
            toolbar,
            text="🖥 ফুলস্ক্রিন (F11)",
            command=self._toggle_fullscreen,
            bg='#4444ff',
            fg='white',
            font=("Arial", 9)
        )
        fullscreen_btn.pack(side=tk.LEFT, padx=5, pady=2)
        
        status_text = f"🎯 {self.server_host}:{self.server_port}"
        status_info = tk.Label(
            toolbar, 
            text=status_text, 
            bg='#2d2d2d', 
            fg='#888888',
            font=("Arial", 9)
        )
        status_info.pack(side=tk.RIGHT, padx=10)
        
        # স্ট্যাটাস বার
        self.status_label = tk.Label(
            self.root, 
            text="✅ সংযুক্ত", 
            bg='#4CAF50', 
            fg='white',
            font=("Arial", 9),
            padx=5
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        # ক্যানভাস
        self.canvas = tk.Canvas(
            self.root, 
            bg='#000000', 
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # মাউস ইভেন্ট
        self.canvas.bind('<Button-1>', lambda e: self._send_mouse_event('click', e.x, e.y, 'left'))
        self.canvas.bind('<Button-2>', lambda e: self._send_mouse_event('click', e.x, e.y, 'middle'))
        self.canvas.bind('<Button-3>', lambda e: self._send_mouse_event('click', e.x, e.y, 'right'))
        self.canvas.bind('<Double-Button-1>', lambda e: self._send_mouse_event('double_click', e.x, e.y))
        self.canvas.bind('<B1-Motion>', lambda e: self._send_mouse_event('move', e.x, e.y))
        self.canvas.bind('<Motion>', lambda e: self._send_mouse_event('move', e.x, e.y))
        self.canvas.bind('<MouseWheel>', lambda e: self._send_mouse_scroll(e.delta))
        
        # কিবোর্ড ইভেন্ট
        self.root.bind('<Key>', self._send_keyboard_event)
        self.root.bind('<F11>', lambda e: self._toggle_fullscreen())
        
        # ফোকাস নিশ্চিত করুন
        self.canvas.focus_set()
        
        self.log("✅ GUI তৈরি হয়েছে")
        
    def _send_mouse_event(self, action, x, y, button='left'):
        if not self.running or not self.canvas:
            return
            
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
            
        packet = {
            'type': 'mouse',
            'action': action,
            'x': x,
            'y': y,
            'button': button,
            'client_width': canvas_width,
            'client_height': canvas_height
        }
        self._send_packet(packet)
        
    def _send_mouse_scroll(self, delta):
        if not self.running:
            return
        amount = 1 if delta > 0 else -1
        packet = {'type': 'mouse', 'action': 'scroll', 'amount': amount}
        self._send_packet(packet)
        
    def _send_keyboard_event(self, event):
        if not self.running:
            return
            
        key = event.keysym.lower()
        
        special_keys = {
            'return': 'enter', 'backspace': 'backspace', 'delete': 'delete',
            'tab': 'tab', 'escape': 'esc', 'space': 'space',
            'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right'
        }
        
        if key in special_keys:
            key_to_send = special_keys[key]
        elif len(key) == 1:
            key_to_send = key
        else:
            return
            
        packet = {'type': 'keyboard', 'action': 'press', 'key': key_to_send}
        self._send_packet(packet)
        
    def _send_packet(self, packet):
        if not self.running or not self.socket:
            return
        try:
            data = pickle.dumps(packet)
            size = struct.pack('>I', len(data))
            self.socket.send(size)
            self.socket.send(data)
        except:
            self.disconnect()
            
    def _receive_screen(self):
        self.log("📡 স্ক্রিন রিসিভার শুরু")
        last_decode_time = 0
        
        while self.running:
            try:
                # সাইজ রিসিভ
                raw_size = self.socket.recv(4)
                if not raw_size:
                    break
                    
                size = struct.unpack('>I', raw_size)[0]
                
                # ডাটা রিসিভ
                data = b''
                while len(data) < size:
                    chunk = self.socket.recv(size - len(data))
                    if not chunk:
                        break
                    data += chunk
                
                # প্যাকেট ডিকোড
                packet = pickle.loads(data)
                
                if packet['type'] == 'screen':
                    img_array = np.frombuffer(packet['data'], np.uint8)
                    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    
                    if img is not None:
                        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        if self.root:
                            self.root.after(1, self._update_display, img_rgb)
                        self.frame_count += 1
                        
            except Exception as e:
                if self.running:
                    self.log(f"⚠️ রিসিভ এরর: {e}")
                break
                
        self.disconnect()
        
    def _update_display(self, img_rgb):
        if not self.running or not self.canvas:
            return
            
        try:
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                pil_img = Image.fromarray(img_rgb)
                pil_img = pil_img.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
                self.current_image = ImageTk.PhotoImage(pil_img)
                
                self.canvas.delete("all")
                self.canvas.create_image(
                    canvas_width // 2,
                    canvas_height // 2,
                    anchor=tk.CENTER,
                    image=self.current_image
                )
        except Exception as e:
            pass
            
    def _toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes('-fullscreen', self.is_fullscreen)
        
    def _monitor_performance(self):
        while self.running:
            time.sleep(1)
            if self.start_time and self.frame_count > 0:
                fps = self.frame_count / (time.time() - self.start_time)
                self.frame_count = 0
                self.start_time = time.time()
                if self.fps_label:
                    self.root.after(0, lambda: self.fps_label.config(text=f"⚡ FPS: {fps:.1f}"))
                    
    def disconnect(self):
        if not self.running:
            return
            
        self.log("🔌 সংযোগ বিচ্ছিন্ন করা হচ্ছে...")
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            
        if self.status_label:
            self.status_label.config(text="❌ বিচ্ছিন্ন", bg="#ff4444")
            
        self.log("✅ সংযোগ বিচ্ছিন্ন হয়েছে")
        
    def _on_closing(self):
        self.disconnect()
        if self.root:
            self.root.destroy()
        
    def _quit(self):
        self.disconnect()
        if self.root:
            self.root.quit()
            self.root.destroy()
            
    def run(self):
        if self.connect():
            self.log("🟢 ক্লায়েন্ট চলছে...")
            self.root.mainloop()
        else:
            self.log("🔴 ক্লায়েন্ট বন্ধ হচ্ছে...")


def main():
    print("""
    ╔══════════════════════════════════════════╗
    ║     ⚡ RDP ফাস্ট ক্লায়েন্ট               ║
    ║     মাল্টি-ইউজার পিসি শেয়ারিং          ║
    ╚══════════════════════════════════════════╝
    """)
    print(f"🎯 টার্গেট সার্ভার: {REMOTE_SERVER_IP}:{SERVER_PORT}")
    print("="*50)
    print("📋 কন্ট্রোল:")
    print("   • মাউস মুভ/ক্লিক → রিমোট কন্ট্রোল")
    print("   • কিবোর্ড টাইপ → রিমোট টাইপ")
    print("   • F11 → ফুলস্ক্রিন")
    print("   • শুধুমাত্র একটি উইন্ডো খোলা যাবে")
    print("="*50)
        
    client = FastRDPClient()
    try:
        client.run()
    except KeyboardInterrupt:
        print("\n🛑 ক্লায়েন্ট বন্ধ করা হচ্ছে...")
    finally:
        cleanup_lock()


if __name__ == "__main__":
    main()