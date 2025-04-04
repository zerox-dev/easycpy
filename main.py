import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
import os
import platform

class ScrcpyController:
    def __init__(self, master):
        self.master = master
        master.title("easycpy")
        master.geometry("400x350")  # Уменьшил высоту окна, так как убрали выбор языка
        
        # Создание элементов интерфейса
        self.create_components()
        
        # Инициализация данных устройства
        self.device_info = None
        self.is_connected = False

    def create_components(self):
        """Создание графических элементов интерфейса"""
        self.frame = ttk.Frame(self.master, padding=20)
        self.frame.pack()

        # Основные элементы интерфейса
        self.ip_label = ttk.Label(self.frame, text="Device IP (Working only on Quest):")
        self.ip_label.pack(pady=5)
        self.ip_entry = ttk.Entry(self.frame, width=25)
        self.ip_entry.pack(pady=5)
        self.check_btn = ttk.Button(
            self.frame,
            text="Check Device",
            command=self.start_device_check,
            width=25
        )
        self.check_btn.pack(pady=10)
        self.stream_btn = ttk.Button(
            self.frame,
            text="Start Stream!",
            command=self.start_scrcpy,
            width=30,
            state="disabled"
        )
        self.stream_btn.pack(pady=10)

        # Добавление тумблера "Stream one eye"
        self.one_eye_stream_var = tk.BooleanVar(value=False)
        self.one_eye_stream_toggle = ttk.Checkbutton(
            self.frame,
            text="Stream one eye",
            variable=self.one_eye_stream_var,
            onvalue=True,
            offvalue=False
        )
        self.one_eye_stream_toggle.pack(pady=5)

        self.status_label = ttk.Label(self.frame, text="Not connected", foreground="red")
        self.status_label.pack(pady=5)

    def get_adb_path(self):
        """Путь к ADB"""
        return os.path.join(os.path.dirname(__file__), 'scrcpy', 'adb.exe' if platform.system() == 'Windows' else 'adb')

    def start_device_check(self):
        """Запуск проверки подключения в отдельном потоке"""
        threading.Thread(target=self.check_device_connection, daemon=True).start()

    def check_device_connection(self):
        """Проверка подключения устройства с таймером"""
        adb = self.get_adb_path()
        try:
            self.status_label.config(text="Fixies is looking for your device...", foreground="orange")
            subprocess.run([adb, 'kill-server'], check=True)
            subprocess.run([adb, 'start-server'], check=True)
            manual_ip = self.ip_entry.get().strip()
            if manual_ip and not self.validate_ip(manual_ip):
                self.show_error("IP is not valid.")
                return
            device_ip = manual_ip if manual_ip else self.auto_detect_ip(adb)
            if not device_ip:
                self.show_error("Fixies said that device is not found. Check if ADB is properly connected.")
                return
            subprocess.run([adb, 'tcpip', '5555'], check=True, timeout=5)
            connect_result = subprocess.run([adb, 'connect', f'{device_ip}:5555'], capture_output=True, text=True)

            # Запуск таймера на 20 секунд
            start_time = time.time()
            remaining_time = 20
            while time.time() - start_time < 20:
                devices = subprocess.run([adb, 'devices', '-l'], capture_output=True, text=True).stdout
                if self.is_device_connected(devices):
                    self.device_info = self.parse_device_info(devices, device_ip)
                    self.update_connection_status(True)
                    return
                remaining_time = max(0, 20 - int(time.time() - start_time))
                self.status_label.config(text=f"Waiting for ADB confirmation... {remaining_time}s", foreground="orange")
                time.sleep(1)

            self.update_connection_status(False)
            self.status_label.config(text="Connection timed out. Trying again.", foreground="red")
            self.disconnect_device()
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}", foreground="red")
            self.update_connection_status(False)

    def auto_detect_ip(self, adb_path):
        """Автоопределение IP устройства"""
        try:
            result = subprocess.run([adb_path, 'shell', 'ip route'], capture_output=True, text=True)
            return self.parse_ip(result.stdout)
        except Exception:
            return None

    def parse_ip(self, ip_output):
        """Парсинг IP-адреса"""
        for line in ip_output.split('\n'):
            if 'wlan0' in line or 'rmnet_data' in line:
                parts = line.strip().split()
                if len(parts) > 0:
                    return parts[-1]
        return None

    def validate_ip(self, ip):
        """Валидация IP-адреса"""
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit() or not 0 <= int(part) <= 255:
                return False
        return True

    def is_device_connected(self, devices_output):
        """Проверить, подключено ли устройство"""
        return 'device:' in devices_output and 'unauthorized' not in devices_output

    def parse_device_info(self, devices_output, device_ip):
        """Получить информацию о устройстве"""
        device_id = None
        for line in devices_output.split('\n'):
            if 'device:' in line:
                device_id = line.split()[0]
                break
        model = self.get_device_property('ro.product.model')
        return {'id': device_id, 'ip': device_ip, 'model': model}

    def get_device_property(self, property_name):
        """Получить свойство устройства"""
        adb = self.get_adb_path()
        try:
            result = subprocess.run([adb, 'shell', 'getprop', property_name], capture_output=True, text=True,
                                    check=True)
            return result.stdout.strip()
        except:
            return "Unknown"

    def update_connection_status(self, is_connected):
        """Обновить статус подключения"""
        self.is_connected = is_connected
        self.stream_btn['state'] = 'normal' if is_connected else 'disabled'
        status_text = f"Connected to {self.device_info['model']} (Serial: {self.device_info['id']})" if is_connected else "Not connected"
        self.status_label.config(text=status_text, foreground="green" if is_connected else "red")

    def disconnect_device(self):
        """Отключить устройство"""
        if self.device_info:
            subprocess.run([self.get_adb_path(), 'disconnect', f"{self.device_info['ip']}:5555"])
            self.device_info = None
            self.is_connected = False
            self.update_connection_status(False)

    def start_scrcpy(self):
        """Запуск scrcpy"""
        if not self.is_connected:
            self.show_error("Connect device first!")
            return
        try:
            scrcpy_path = os.path.join(os.path.dirname(__file__), 'scrcpy',
                                       'scrcpy.exe' if platform.system() == 'Windows' else 'scrcpy')
            # Базовые параметры
            base_params = [scrcpy_path, '--serial', self.device_info['id'], '--max-size', '1920', '--window-title', 'Quest Stream']
            # Проверка состояния тумблера
            if self.one_eye_stream_var.get():
                base_params.extend(['--crop', '1730:974:1934:450', '--max-fps', '60'])
            subprocess.Popen(base_params)
        except Exception as e:
            self.show_error(f"Failed to start scrcpy: {str(e)}")

    def show_error(self, message):
        """Показать сообщение об ошибке"""
        messagebox.showerror("Error", message)

if __name__ == "__main__":
    root = tk.Tk()
    app = ScrcpyController(root)
    root.mainloop()
