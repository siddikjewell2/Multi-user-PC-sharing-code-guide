"""
RDP ক্লায়েন্ট - যেই কম্পিউটার থেকে কানেক্ট করবেন সেখানে এই কোড রান করান
VS Code এ রান: F5 চাপুন অথবা টার্মিনালে: python client.py
"""

import socket
import threading
import struct
import pickle
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import sys
from datetime import datetime

# কনফিগারেশন ফাইল থেকে সেটিংস নিচ্ছি
try:
    from config import *
except ImportError:
    # ডিফল্ট সেটিংস
    REMOTE_SERVER_IP = '127.0.0.1'
    SERVER_PORT = 5000
    CLIENT_WINDOW_WIDTH = 1024
    CLIENT_WINDOW_HEIGHT = 768
    ENABLE_LOGGING = True

class RDPClient:
    """
    RDP ক্লায়েন্ট - সার্ভারের সাথে সংযোগ স্থাপন করে
    গ্রাফিক্যাল ইউজার ইন্টারফেস সহ
    """
    
    def __init__(self, server_host=REMOTE_SERVER_IP, server_port=SERVER_PORT):
        """
        ক্লায়েন্ট ইনিশিয়ালাইজেশন
        
        Args:
            server_host: সার্ভারের IP এড্রেস
            server_port: সার্ভারের পোর্ট
        """
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None
        self.running = False
        self.root = None
        self.canvas = None
        self.status_label = None
        self.connection_info = None
        self.current_image = None
        
        # পারফরম্যান্স মিটার
        self.frame_count = 0
        self.start_time = time.time()
        
    def log(self, message):
        """লগ মেসেজ প্রিন্ট"""
        if ENABLE_LOGGING:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
            
    def connect(self):
        """
        সার্ভারের সাথে কানেক্ট করা
        Returns: bool - সফল হলে True, ব্যর্থ হলে False
        """
        try:
            self.log(f"🔌 কানেক্ট করছি {self.server_host}:{self.server_port}...")
            
            # সকেট তৈরি
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)  # 5 সেকেন্ড টাইমআউট
            self.socket.connect((self.server_host, self.server_port))
            self.socket.settimeout(None)  # টাইমআউট রিমুভ
            
            self.running = True
            self.log(f"✅ সংযোগ সফল হয়েছে!")
            
            # GUI তৈরি
            self._setup_gui()
            
            # স্ক্রিন রিসিভার থ্রেড
            receive_thread = threading.Thread(target=self._receive_screen, daemon=True)
            receive_thread.start()
            
            # পারফরম্যান্স মনিটর থ্রেড
            monitor_thread = threading.Thread(target=self._monitor_performance, daemon=True)
            monitor_thread.start()
            
            return True
            
        except socket.timeout:
            self.log(f"❌ টাইমআউট: {self.server_host} এ সংযোগ করা যায়নি")
            messagebox.showerror("সংযোগ ব্যর্থ", f"সার্ভার {self.server_host} এ পৌঁছানো যায়নি\n\nচেক করুন:\n1. সার্ভার কি চালু আছে?\n2. আইপি কি সঠিক?\n3. ফায়ারওয়াল কি 5000 পোর্ট ওপেন করেছে?")
            return False
        except ConnectionRefusedError:
            self.log(f"❌ সংযোগ প্রত্যাখ্যান: সার্ভার কি চালু আছে?")
            messagebox.showerror("সংযোগ ব্যর্থ", "সার্ভার সংযোগ প্রত্যাখ্যান করেছে\n\nসার্ভার কি চালু আছে?")
            return False
        except Exception as e:
            self.log(f"❌ সংযোগ ব্যর্থ: {e}")
            messagebox.showerror("সংযোগ ব্যর্থ", f"এরর: {e}")
            return False
            
    def _setup_gui(self):
        """
        GUI উইন্ডো তৈরি করা
        টিঙ্কিন্টার দিয়ে সুন্দর UI বানানো
        """
        self.root = tk.Tk()
        self.root.title(f"RDP ক্লায়েন্ট - {self.server_host}")
        self.root.geometry(f"{CLIENT_WINDOW_WIDTH}x{CLIENT_WINDOW_HEIGHT}")
        
        # মিনিমাম সাইজ সেট করা
        self.root.minsize(640, 480)
        
        # স্টাইলিং
        style = ttk.Style()
        style.theme_use('clam')
        
        # মেনু বার
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # ফাইল মেনু
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ফাইল", menu=file_menu)
        file_menu.add_command(label="ডিসকানেক্ট", command=self.disconnect)
        file_menu.add_separator()
        file_menu.add_command(label="এক্সিট", command=self._quit)
        
        # হেল্প মেনু
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="হেল্প", menu=help_menu)
        help_menu.add_command(label="কানেকশন ইনফো", command=self._show_connection_info)
        help_menu.add_command(label="কন্ট্রোলস", command=self._show_controls)
        
        # স্ট্যাটাস বার
        self.status_label = tk.Label(
            self.root, 
            text="✅ সংযুক্ত", 
            bg="#4CAF50", 
            fg="white",
            font=("Arial", 10),
            padx=5
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        # টুল বার
        toolbar = tk.Frame(self.root, bg="#f0f0f0", height=35)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # বাটন
        disconnect_btn = tk.Button(
            toolbar, 
            text="🔌 ডিসকানেক্ট", 
            command=self.disconnect,
            bg="#ff4444",
            fg="white",
            padx=10
        )
        disconnect_btn.pack(side=tk.LEFT, padx=5, pady=2)
        
        # অবস্থা দেখানোর লেবেল
        self.fps_label = tk.Label(toolbar, text="FPS: --", bg="#f0f0f0")
        self.fps_label.pack(side=tk.RIGHT, padx=10)
        
        # স্ক্রিন দেখানোর ক্যানভাস
        self.canvas = tk.Canvas(self.root, bg='#1a1a1a', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # মাউস ইভেন্ট বাইন্ড
        self._bind_mouse_events()
        
        # কিবোর্ড ইভেন্ট বাইন্ড
        self.root.bind('<Key>', self._send_keyboard_event)
        
        # উইন্ডো সাইজ চেঞ্জ ইভেন্ট
        self.root.bind('<Configure>', self._on_window_resize)
        
        # ফুলস্ক্রিন টগল
        self.root.bind('<F11>', self._toggle_fullscreen)
        
        self.log("✅ GUI তৈরি হয়েছে")
        
    def _bind_mouse_events(self):
        """মাউস ইভেন্ট ক্যানভাসের সাথে বাইন্ড করা"""
        self.canvas.bind('<Button-1>', lambda e: self._send_mouse_event('click', e.x, e.y, 'left'))
        self.canvas.bind('<Button-2>', lambda e: self._send_mouse_event('click', e.x, e.y, 'middle'))
        self.canvas.bind('<Button-3>', lambda e: self._send_mouse_event('click', e.x, e.y, 'right'))
        self.canvas.bind('<Double-Button-1>', lambda e: self._send_mouse_event('double_click', e.x, e.y))
        self.canvas.bind('<B1-Motion>', lambda e: self._send_mouse_event('move', e.x, e.y))
        self.canvas.bind('<Motion>', lambda e: self._send_mouse_event('move', e.x, e.y))
        self.canvas.bind('<MouseWheel>', lambda e: self._send_mouse_scroll(e.delta))
        
    def _send_mouse_event(self, action, x, y, button='left'):
        """মাউস ইভেন্ট সার্ভারে পাঠানো"""
        if not self.running:
            return
            
        # ক্যানভাসের সাইজ বের করা
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width == 0 or canvas_height == 0:
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
        """মাউস স্ক্রল ইভেন্ট"""
        if not self.running:
            return
            
        # ডেল্টা থেকে ডিরেকশন বের করা
        amount = 1 if delta > 0 else -1
        
        packet = {
            'type': 'mouse',
            'action': 'scroll',
            'amount': amount
        }
        self._send_packet(packet)
        
    def _send_keyboard_event(self, event):
        """কিবোর্ড ইভেন্ট পাঠানো"""
        if not self.running:
            return
            
        # বিশেষ কিবোর্ড কিরে হ্যান্ডলিং
        key = event.keysym.lower()
        
        # মডিফায়ার কিরে ম্যাপিং
        modifier_map = {
            'control_l': 'ctrl',
            'control_r': 'ctrl',
            'alt_l': 'alt',
            'alt_r': 'alt',
            'shift_l': 'shift',
            'shift_r': 'shift'
        }
        
        if key in modifier_map:
            key = modifier_map[key]
            
        # অক্ষর বের করা
        if hasattr(event, 'char') and event.char and event.char != '':
            key_to_send = event.char
        else:
            key_to_send = key
            
        packet = {
            'type': 'keyboard',
            'action': 'press',
            'key': key_to_send
        }
        self._send_packet(packet)
        
    def _send_packet(self, packet):
        """
        প্যাকেট এনকোড ও সেন্ড করা
        
        Structure: [4 bytes: size][bytes: pickled data]
        """
        if not self.running or not self.socket:
            return
            
        try:
            data = pickle.dumps(packet)
            size = struct.pack('>I', len(data))
            self.socket.send(size)
            self.socket.send(data)
        except (BrokenPipeError, ConnectionResetError):
            self.log("⚠️ সংযোগ হারিয়েছে")
            self.disconnect()
        except Exception as e:
            if self.running:
                self.log(f"⚠️ প্যাকেট সেন্ডে এরর: {e}")
                
    def _receive_screen(self):
        """
        সার্ভার থেকে স্ক্রিন ডাটা রিসিভ করা
        অবিরাম লুপে চলে যতক্ষণ কানেকশন থাকে
        """
        self.log("📡 স্ক্রিন রিসিভার থ্রেড শুরু")
        
        while self.running:
            try:
                # 1. সাইজ রিসিভ (4 বাইট)
                raw_size = self.socket.recv(4)
                if not raw_size:
                    self.log("❌ সার্ভার সংযোগ বন্ধ করেছে")
                    break
                    
                size = struct.unpack('>I', raw_size)[0]
                
                # 2. পুরো ডাটা রিসিভ
                data = b''
                while len(data) < size:
                    chunk = self.socket.recv(size - len(data))
                    if not chunk:
                        break
                    data += chunk
                    
                # 3. প্যাকেট ডিসিরিয়ালাইজ
                packet = pickle.loads(data)
                
                if packet['type'] == 'screen':
                    # 4. ইমেজ ডিকোড
                    img_array = np.frombuffer(packet['data'], np.uint8)
                    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    
                    if img is not None:
                        # 5. BGR থেকে RGB
                        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        
                        # 6. GUI আপডেট (থ্রেড সেফ)
                        self.root.after(10, self._update_display, img_rgb)
                        self.frame_count += 1
                        
            except (ConnectionResetError, BrokenPipeError):
                self.log("❌ সংযোগ বিচ্ছিন্ন হয়েছে")
                break
            except struct.error as e:
                self.log(f"⚠️ ডাটা স্ট্রাকচার এরর: {e}")
                break
            except Exception as e:
                if self.running:
                    self.log(f"⚠️ রিসিভিং এ এরর: {e}")
                    
        self.log("📡 স্ক্রিন রিসিভার থ্রেড বন্ধ")
        self.disconnect()
        
    def _update_display(self, img_rgb):
        """
        GUI তে ইমেজ আপডেট করা
        ক্যানভাসের সাইজ অনুযায়ী ইমেজ রিসাইজ
        """
        if not self.running or not self.canvas:
            return
            
        try:
            # ক্যানভাসের বর্তমান সাইজ
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                # ইমেজ রিসাইজ
                pil_img = Image.fromarray(img_rgb)
                pil_img = pil_img.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
                
                # টিকিন্টার ফরম্যাটে কনভার্ট
                self.current_image = ImageTk.PhotoImage(pil_img)
                
                # ক্যানভাসে দেখানো
                self.canvas.delete("all")
                self.canvas.create_image(
                    canvas_width//2, 
                    canvas_height//2, 
                    anchor=tk.CENTER, 
                    image=self.current_image
                )
        except Exception as e:
            self.log(f"⚠️ ডিসপ্লে আপডেটে এরর: {e}")
            
    def _on_window_resize(self, event):
        """উইন্ডো রিসাইজ হলে ক্যানভাসও রিসাইজ হবে"""
        if event.widget == self.root:
            # ক্যানভাসের সাইজ আপডেট
            pass
            
    def _toggle_fullscreen(self, event=None):
        """ফুলস্ক্রিন মোড টগল"""
        current = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not current)
        
    def _monitor_performance(self):
        """পারফরম্যান্স মনিটর - FPS ক্যালকুলেট"""
        while self.running:
            time.sleep(1)
            if self.start_time:
                fps = self.frame_count / (time.time() - self.start_time)
                self.frame_count = 0
                self.start_time = time.time()
                
                # FPS GUI তে দেখানো
                self.root.after(0, lambda: self.fps_label.config(text=f"FPS: {fps:.1f}"))
                
    def _show_connection_info(self):
        """কানেকশন ইনফো দেখানো"""
        info = f"""
        📡 সংযোগের তথ্য:
        
        সার্ভার আইপি: {self.server_host}
        পোর্ট: {self.server_port}
        স্ট্যাটাস: {'সংযুক্ত' if self.running else 'বিচ্ছিন্ন'}
        
        🖥️ কন্ট্রোল নির্দেশিকা:
        • মাউস মুভ করুন → পয়েন্টার মুভ হবে        • ক্লিক করুন → রিমোট ক্লিক
        • কিবোর্ড টাইপ করুন → রিমোট টাইপ
        • F11 → ফুলস্ক্রিন টগল
        """
        messagebox.showinfo("সংযোগের তথ্য", info)
        
    def _show_controls(self):
        """কন্ট্রোল নির্দেশিকা"""
        controls = """
        🎮 কন্ট্রোল নির্দেশিকা:
        
        মাউস:
        • লেফট ক্লিক → রিমোট লেফট ক্লিক
        • রাইট ক্লিক → রিমোট রাইট ক্লিক
        • ডাবল ক্লিক → রিমোট ডাবল ক্লিক
        • স্ক্রল → রিমোট স্ক্রল
        
        কিবোর্ড:
        • সব সাধারণ কিরে কাজ করে
        • Ctrl, Alt, Shift সাপোর্টেড
        
        শর্টকাট:
        • F11 → ফুলস্ক্রিন
        • Alt+F4 → উইন্ডো বন্ধ
        """
        messagebox.showinfo("কন্ট্রোল নির্দেশিকা", controls)
        
    def disconnect(self):
        """সংযোগ বিচ্ছিন্ন করা - ক্লিনআপ"""
        if not self.running:
            return
            
        self.log("🔌 সংযোগ বিচ্ছিন্ন করা হচ্ছে...")
        self.running = False
        
        # সকেট বন্ধ
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            
        # স্ট্যাটাস আপডেট
        if self.status_label:
            self.status_label.config(text="❌ বিচ্ছিন্ন", bg="#ff4444")
            
        self.log("✅ সংযোগ বিচ্ছিন্ন হয়েছে")
        
        # প্রয়োজনে GUI বন্ধ করবেন না, ব্যবহারকারী নিজে করবে
        
    def _quit(self):
        """অ্যাপ্লিকেশন বন্ধ করা"""
        self.disconnect()
        if self.root:
            self.root.quit()
            self.root.destroy()
            
    def run(self):
        """মেইন লুপ চালানো"""
        if self.connect():
            self.log("🟢 ক্লায়েন্ট চলছে...")
            self.root.mainloop()
        else:
            self.log("🔴 ক্লায়েন্ট বন্ধ হচ্ছে...")
            
def main():
    """মেইন ফাংশন"""
    print("""
    ╔══════════════════════════════════════════╗
    ║     💻 RDP ক্লায়েন্ট - VS Code Version    ║
    ╚══════════════════════════════════════════╝
    """)
    print("📋 নির্দেশনা:")
    print("   1. সার্ভার চালু আছে কিনা চেক করুন")
    print("   2. server.py অন্য PC তে চলছে কিনা")
    print("   3. config.py এ সার্ভারের IP সঠিক দিন")
    print("="*50)
    
    # কনফিগ ফাইল চেক
    try:
        from config import REMOTE_SERVER_IP, SERVER_PORT
        print(f"🎯 টার্গেট সার্ভার: {REMOTE_SERVER_IP}:{SERVER_PORT}")
    except:
        print("⚠️ config.py পাওয়া যায়নি, ডিফল্ট 127.0.0.1 ব্যবহার হচ্ছে")
        
    client = RDPClient()
    client.run()

if __name__ == "__main__":
    import time
    main()