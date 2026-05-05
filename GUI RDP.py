import sys
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, 
    QVBoxLayout, QPushButton, QLineEdit, QFormLayout, 
    QDialog, QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt

class RDPConnectionDialog(QDialog):
    """নতুন RDP সংযোগের জন্য ডায়ালগ বক্স"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("নতুন RDP সংযোগ")
        self.setModal(True)
        
        layout = QFormLayout()
        
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("192.168.1.100 বা computer.com")
        layout.addRow("সার্ভার আইপি:", self.server_input)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("ব্যবহারকারীর নাম")
        layout.addRow("ইউজারনেম:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("পাসওয়ার্ড")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("পাসওয়ার্ড:", self.password_input)
        
        self.port_input = QLineEdit("3389")
        layout.addRow("পোর্ট:", self.port_input)
        
        self.resolution_combo = QLineEdit("1920x1080")
        layout.addRow("রেজোলিউশন:", self.resolution_combo)
        
        buttons = QHBoxLayout()
        connect_btn = QPushButton("সংযোগ করুন")
        connect_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("বাতিল")
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(connect_btn)
        buttons.addWidget(cancel_btn)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def get_connection_info(self):
        return {
            'server': self.server_input.text(),
            'username': self.username_input.text(),
            'password': self.password_input.text(),
            'port': self.port_input.text(),
            'resolution': self.resolution_combo.text()
        }

class MainWindow(QMainWindow):
    """মেইন GUI উইন্ডো - একাধিক ট্যাব সাপোর্ট করে"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("পাইথন RDP ক্লায়েন্ট - মাল্টি ইউজার")
        self.setGeometry(100, 100, 1200, 800)
        
        # মেইন লেআউট
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # টুলবার
        toolbar = QHBoxLayout()
        self.new_connection_btn = QPushButton("+ নতুন সংযোগ")
        self.new_connection_btn.clicked.connect(self.new_connection)
        toolbar.addWidget(self.new_connection_btn)
        
        self.disconnect_btn = QPushButton("সংযোগ বিচ্ছিন্ন")
        self.disconnect_btn.clicked.connect(self.disconnect_current)
        toolbar.addWidget(self.disconnect_btn)
        
        layout.addLayout(toolbar)
        
        # ট্যাব উইজেট
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tab_widget)
        
        self.connections = []  # সক্রিয় সংযোগের তালিকা
    
    def new_connection(self):
        """নতুন RDP সংযোগ উইন্ডো খোলে"""
        dialog = RDPConnectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            info = dialog.get_connection_info()
            if info['server']:
                self.create_rdp_tab(info)
    
    def create_rdp_tab(self, connection_info):
        """একটি নতুন ট্যাব তৈরি করে এবং RDP সংযোগ স্থাপন করে"""
        tab_name = f"{connection_info['server']} - {connection_info['username']}"
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # RDP সংযোগের জন্য কমান্ড
        # rdpyqt ব্যবহার করে সংযোগ স্থাপন
        cmd = [
            'rdpyqt6',
            '-u', connection_info['username'],
            '-p', connection_info['password'],
            '-w', connection_info['resolution'].split('x')[0],
            '-h', connection_info['resolution'].split('x')[1],
            f"{connection_info['server']}:{connection_info['port']}"
        ]
        
        # স্ট্যাটাস লেবেল
        from PyQt6.QtWidgets import QLabel
        status_label = QLabel(f"সংযোগ স্থাপন হচ্ছে...\nসার্ভার: {connection_info['server']}")
        layout.addWidget(status_label)
        
        # ট্যাব যোগ করুন
        self.tab_widget.addTab(tab, tab_name)
        self.tab_widget.setCurrentWidget(tab)
        
        # সংযোগ সংরক্ষণ
        self.connections.append({
            'tab': tab,
            'info': connection_info,
            'process': None
        })
        
        QMessageBox.information(self, "সংযোগ", 
            f"RDP সংযোগ শুরু হচ্ছে {connection_info['server']}-এ\n"
            "নোট: rdpyqt স্বতন্ত্র উইন্ডোতে খুলবে")
        
        # rdpyqt চালান (এটি আলাদা উইন্ডোতে খোলে)
        try:
            subprocess.Popen(cmd)
        except FileNotFoundError:
            QMessageBox.warning(self, "এরর", 
                "rdpyqt পাওয়া যায়নি!\nইনস্টল করুন: pip install rdpyqt")
    
    def disconnect_current(self):
        """বর্তমান ট্যাবের সংযোগ বিচ্ছিন্ন করে"""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)
    
    def close_tab(self, index):
        """ট্যাব বন্ধ করে"""
        if index >= 0:
            self.tab_widget.removeTab(index)
            # সংযোগ তালিকা থেকে সরান
            if index < len(self.connections):
                self.connections.pop(index)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()