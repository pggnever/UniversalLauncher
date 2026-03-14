import customtkinter as ctk
from tkinter import filedialog
import json
import os
import time
import webbrowser
import threading
import psutil
import pystray
from PIL import Image, ImageDraw
import winreg
import sys

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- СЛОВАРЬ ПЕРЕВОДОВ ---
LANGUAGES = {
    "RU": {
        "main_title": "Мои игровые связки",
        "add_seq": "+ Добавить связку",
        "autostart": "Запускать вместе с Windows",
        "empty": "Пока нет ни одной связки. Нажми кнопку ниже!",
        "on": "Включено",
        "del": "Удалить",
        "edit": "Редактировать",
        "new_seq_title": "Новая связка",
        "edit_seq_title": "Редактирование связки",
        "seq_name": "Название связки",
        "auto_close": "Закрывать всё после выхода из главной программы",
        "run_order": "Запускать по порядку",
        "add_app": "+ Добавить еще приложение",
        "save": "Сохранить связку",
        "path": "Путь / Ссылка",
        "browse": "Обзор",
        "delay": "Пауза",
        "tray_expand": "Развернуть",
        "tray_exit": "Выход"
    },
    "EN": {
        "main_title": "My Game Sequences",
        "add_seq": "+ Add Sequence",
        "autostart": "Start with Windows",
        "empty": "No sequences yet. Click the button below!",
        "on": "Enabled",
        "del": "Delete",
        "edit": "Edit",
        "new_seq_title": "New Sequence",
        "edit_seq_title": "Edit Sequence",
        "seq_name": "Sequence Name",
        "auto_close": "Close all apps after the main program exits",
        "run_order": "Run in order",
        "add_app": "+ Add another app",
        "save": "Save Sequence",
        "path": "Path / Link",
        "browse": "Browse",
        "delay": "Delay",
        "tray_expand": "Expand",
        "tray_exit": "Exit"
    }
}

class UniversalLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- НАСТРОЙКИ ПУТЕЙ (AppData) ---
        self.app_data_path = os.path.join(os.environ['APPDATA'], 'UniversalLauncher')
        if not os.path.exists(self.app_data_path):
            os.makedirs(self.app_data_path)
        # Теперь конфиг всегда будет храниться в системной папке
        self.config_file = os.path.join(self.app_data_path, 'config.json')
        # ---------------------------------

        self.title("Universal Launcher")
        self.geometry("650x550")
        self.minsize(550, 450)

        self.protocol('WM_DELETE_WINDOW', self.hide_window)

        # Загружаем настройки и профили
        config_data = self.load_config()
        self.current_lang = config_data.get("language", "RU")
        self.profiles = config_data.get("profiles", {})

        # --- ВЫБОР ЯЗЫКА (Dropdown) ---
        self.lang_var = ctk.StringVar(value=self.current_lang)
        self.lang_menu = ctk.CTkOptionMenu(self, values=["RU", "EN"], variable=self.lang_var, command=self.change_language, width=70)
        self.lang_menu.place(relx=0.95, rely=0.05, anchor="ne")

        # Элементы главного окна
        self.label = ctk.CTkLabel(self, text=self._t("main_title"), font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=20)

        self.scrollable_frame = ctk.CTkScrollableFrame(self, width=550, height=250)
        self.scrollable_frame.pack(pady=10, padx=20, fill="both", expand=True)

        self.add_button = ctk.CTkButton(self, text=self._t("add_seq"), command=self.add_sequence_click, font=ctk.CTkFont(size=14, weight="bold"), height=40)
        self.add_button.pack(pady=10)

        self.autostart_var = ctk.BooleanVar(value=self.check_autostart())
        self.autostart_cb = ctk.CTkCheckBox(self, text=self._t("autostart"), variable=self.autostart_var, command=self.toggle_autostart, font=ctk.CTkFont(weight="bold"))
        self.autostart_cb.pack(pady=(0, 15))

        self.render_profiles()

        self.triggered_profiles = set()
        monitor_thread = threading.Thread(target=self.process_monitor, daemon=True)
        monitor_thread.start()

    # --- МЕТОДЫ ПЕРЕВОДА ---
    def _t(self, key):
        return LANGUAGES[self.current_lang].get(key, key)

    def change_language(self, choice):
        self.current_lang = choice
        self.save_config()
        self.update_main_ui_texts()
        self.render_profiles()

    def update_main_ui_texts(self):
        self.label.configure(text=self._t("main_title"))
        self.add_button.configure(text=self._t("add_seq"))
        self.autostart_cb.configure(text=self._t("autostart"))
    # -----------------------

    def check_autostart(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "UniversalLauncher")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False

    def toggle_autostart(self):
        enable = self.autostart_var.get()
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "UniversalLauncher"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                if getattr(sys, 'frozen', False):
                    path = f'"{sys.executable}"'
                else:
                    path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, path)
            else:
                try: winreg.DeleteValue(key, app_name)
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception:
            pass

    def resource_path(self, relative_path):
        """ Получаем путь к ресурсам внутри собранного .exe """
        try:
            # PyInstaller создает временную папку _MEIPASS при запуске
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def create_image(self):
        """ Загружаем нашу иконку для трея """
        icon_path = self.resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            return Image.open(icon_path)
        else:
            # Заглушка, если файл чудом не найдется (тот самый синий квадрат)
            image = Image.new('RGB', (64, 64), color=(30, 30, 30))
            dc = ImageDraw.Draw(image)
            dc.rectangle((16, 16, 48, 48), fill=(29, 107, 201))
            return image
    def hide_window(self):
        self.withdraw()
        menu = pystray.Menu(
            pystray.MenuItem(self._t("tray_expand"), self.show_window), 
            pystray.MenuItem(self._t("tray_exit"), self.quit_window)
        )
        self.tray_icon = pystray.Icon("UniversalLauncher", self.create_image(), "Universal Launcher", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon, item):
        self.tray_icon.stop()
        self.after(0, self.deiconify)

    def quit_window(self, icon, item):
        self.tray_icon.stop()
        self.quit()

    def process_monitor(self):
        while True:
            time.sleep(2)
            running_processes = set(p.name().lower() for p in psutil.process_iter(['name']))

            for name, data in self.profiles.items():
                if not data.get("is_active", True): continue
                apps = data.get("apps", [])
                if len(apps) < 2: continue
                
                first_app_path = apps[0]["path"]
                first_exe = os.path.basename(first_app_path).lower()
                
                if first_exe.startswith("http") or first_exe.startswith("steam"): continue

                is_running = first_exe in running_processes
                
                if is_running and name not in self.triggered_profiles:
                    self.triggered_profiles.add(name)
                    threading.Thread(target=self._execute_rest_of_apps, args=(apps,), daemon=True).start()
                    
                elif not is_running and name in self.triggered_profiles:
                    self.triggered_profiles.remove(name)
                    if data.get("auto_close", False):
                        for i in range(1, len(apps)):
                            app_path = apps[i]["path"]
                            app_exe = os.path.basename(app_path).lower()
                            if app_exe.startswith("http") or app_exe.startswith("steam"): continue
                            for proc in psutil.process_iter(['name']):
                                if proc.name().lower() == app_exe:
                                    try: proc.terminate()
                                    except Exception: pass

    def _execute_rest_of_apps(self, apps):
        first_delay = int(apps[0].get("delay", 0))
        if first_delay > 0: time.sleep(first_delay)
            
        for i in range(1, len(apps)):
            app = apps[i]
            path = app["path"].strip()
            delay = int(app["delay"])
            
            try:
                if path.startswith("http://") or path.startswith("https://") or path.startswith("steam://"):
                    webbrowser.open(path)
                else:
                    os.startfile(path) 
            except Exception: pass
            
            if delay > 0 and i < len(apps) - 1:
                time.sleep(delay)

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, "r", encoding="utf-8") as f:
                try: 
                    data = json.load(f)
                    if "profiles" not in data:
                        return {"language": "RU", "profiles": data}
                    return data
                except json.JSONDecodeError: return {}
        return {"language": "RU", "profiles": {}}

    def save_config(self):
        data = {
            "language": self.current_lang,
            "profiles": self.profiles
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def render_profiles(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not self.profiles:
            empty_lbl = ctk.CTkLabel(self.scrollable_frame, text=self._t("empty"), text_color="gray")
            empty_lbl.pack(pady=20)
            return

        for name, data in self.profiles.items():
            profile_frame = ctk.CTkFrame(self.scrollable_frame)
            profile_frame.pack(fill="x", pady=5, padx=5)

            name_lbl = ctk.CTkLabel(profile_frame, text=name, font=ctk.CTkFont(weight="bold", size=16))
            name_lbl.pack(side="left", padx=15, pady=10)

            is_active = data.get("is_active", True)
            switch_var = ctk.BooleanVar(value=is_active)
            
            def toggle_active(n=name, var=switch_var):
                self.profiles[n]["is_active"] = var.get()
                self.save_config()

            active_switch = ctk.CTkSwitch(profile_frame, text=self._t("on"), variable=switch_var, command=toggle_active)
            active_switch.pack(side="left", padx=20)

            del_btn = ctk.CTkButton(profile_frame, text=self._t("del"), width=60, fg_color="#c93434", hover_color="#8f2424", command=lambda n=name: self.delete_profile(n))
            del_btn.pack(side="right", padx=5, pady=10)

            edit_btn = ctk.CTkButton(profile_frame, text=self._t("edit"), width=90, fg_color="#cf8c17", hover_color="#a87214", command=lambda n=name: self.add_sequence_click(edit_name=n))
            edit_btn.pack(side="right", padx=5, pady=10)

    def delete_profile(self, name):
        if name in self.profiles:
            del self.profiles[name]
            self.save_config()
            self.render_profiles()

    def add_sequence_click(self, edit_name=None):
        dialog = ctk.CTkToplevel(self)
        dialog.title(self._t("edit_seq_title") if edit_name else self._t("new_seq_title"))
        dialog.geometry("680x600")
        dialog.grab_set()

        name_entry = ctk.CTkEntry(dialog, placeholder_text=self._t("seq_name"), width=400)
        name_entry.pack(pady=(20, 10))

        self.auto_close_var = ctk.BooleanVar(value=False)
        auto_close_checkbox = ctk.CTkCheckBox(dialog, text=self._t("auto_close"), variable=self.auto_close_var, font=ctk.CTkFont(weight="bold"))
        auto_close_checkbox.pack(pady=5)

        self.run_in_order_var = ctk.BooleanVar(value=True)
        order_checkbox = ctk.CTkCheckBox(dialog, text=self._t("run_order"), variable=self.run_in_order_var, font=ctk.CTkFont(weight="bold"))
        order_checkbox.pack(pady=5)

        self.apps_container = ctk.CTkFrame(dialog, fg_color="transparent")
        self.apps_container.pack(pady=10, fill="both", expand=True, padx=10)

        self.app_rows = [] 
        
        if edit_name:
            name_entry.insert(0, edit_name)
            profile_data = self.profiles[edit_name]
            self.run_in_order_var.set(profile_data.get("run_in_order", True))
            self.auto_close_var.set(profile_data.get("auto_close", False))
            for app in profile_data.get("apps", []):
                self.add_app_row(app.get("path", ""), app.get("delay", ""))
        else:
            self.add_app_row()

        add_step_btn = ctk.CTkButton(dialog, text=self._t("add_app"), fg_color="#555555", hover_color="#444444", command=self.add_app_row)
        add_step_btn.pack(pady=10)

        save_btn = ctk.CTkButton(dialog, text=self._t("save"), fg_color="green", hover_color="darkgreen",
                                 command=lambda: self.save_profile(name_entry.get(), dialog, old_name=edit_name))
        save_btn.pack(pady=20)

    def add_app_row(self, path_val="", delay_val=""):
        row_frame = ctk.CTkFrame(self.apps_container, fg_color="transparent")
        row_frame.pack(fill="x", pady=5)

        lbl = ctk.CTkLabel(row_frame, text="", font=ctk.CTkFont(weight="bold"), width=25)
        lbl.pack(side="left", padx=(0, 5))

        path_entry = ctk.CTkEntry(row_frame, placeholder_text=self._t("path"), width=200)
        path_entry.pack(side="left", padx=(0, 5))
        if path_val: path_entry.insert(0, path_val)

        btn = ctk.CTkButton(row_frame, text=self._t("browse"), width=60, command=lambda e=path_entry: self.browse_file(e))
        btn.pack(side="left", padx=(0, 5))

        delay_entry = ctk.CTkEntry(row_frame, placeholder_text=self._t("delay"), width=60)
        delay_entry.pack(side="left", padx=(0, 5))
        if delay_val: delay_entry.insert(0, delay_val)

        row_dict = {"frame": row_frame, "label": lbl, "path": path_entry, "delay": delay_entry}

        up_btn = ctk.CTkButton(row_frame, text="↑", width=25, fg_color="#555555", hover_color="#777777", command=lambda r=row_dict: self.move_row_up(r))
        up_btn.pack(side="left", padx=(2, 2))

        down_btn = ctk.CTkButton(row_frame, text="↓", width=25, fg_color="#555555", hover_color="#777777", command=lambda r=row_dict: self.move_row_down(r))
        down_btn.pack(side="left", padx=(2, 5))

        del_btn = ctk.CTkButton(row_frame, text="X", width=30, fg_color="#c93434", hover_color="#8f2424", command=lambda r=row_dict: self.delete_app_row(r))
        del_btn.pack(side="left")

        self.app_rows.append(row_dict)
        self.update_row_numbers()

    def move_row_up(self, row_dict):
        index = self.app_rows.index(row_dict)
        if index > 0: self.swap_rows(index, index - 1)

    def move_row_down(self, row_dict):
        index = self.app_rows.index(row_dict)
        if index < len(self.app_rows) - 1: self.swap_rows(index, index + 1)

    def swap_rows(self, idx1, idx2):
        path1 = self.app_rows[idx1]["path"].get()
        delay1 = self.app_rows[idx1]["delay"].get()
        path2 = self.app_rows[idx2]["path"].get()
        delay2 = self.app_rows[idx2]["delay"].get()
        
        self.app_rows[idx1]["path"].delete(0, 'end')
        self.app_rows[idx1]["path"].insert(0, path2)
        self.app_rows[idx1]["delay"].delete(0, 'end')
        self.app_rows[idx1]["delay"].insert(0, delay2)
        
        self.app_rows[idx2]["path"].delete(0, 'end')
        self.app_rows[idx2]["path"].insert(0, path1)
        self.app_rows[idx2]["delay"].delete(0, 'end')
        self.app_rows[idx2]["delay"].insert(0, delay1)

    def delete_app_row(self, row_dict):
        row_dict["frame"].destroy()
        self.app_rows.remove(row_dict)
        self.update_row_numbers()

    def update_row_numbers(self):
        for i, row in enumerate(self.app_rows):
            row["label"].configure(text=f"{i + 1}.")

    def browse_file(self, entry_widget):
        filepath = filedialog.askopenfilename(filetypes=[("Programs/Программы", "*.exe;*.url;*.lnk;*.bat"), ("All files/Все файлы", "*.*")])
        if filepath:
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, filepath)

    def save_profile(self, name, dialog, old_name=None):
        if not name.strip():
            name = f"Sequence {len(self.profiles) + 1}"

        run_in_order = self.run_in_order_var.get()
        auto_close = self.auto_close_var.get()
        apps_data = []

        for row in self.app_rows:
            path = row["path"].get().strip()
            delay = row["delay"].get().strip()
            if path:
                delay_val = delay if delay.isdigit() else "0"
                apps_data.append({"path": path, "delay": delay_val})
        
        if apps_data:
            is_active = True
            if old_name and old_name in self.profiles:
                is_active = self.profiles[old_name].get("is_active", True)

            if old_name and old_name != name and old_name in self.profiles:
                del self.profiles[old_name]
                if old_name in self.triggered_profiles:
                    self.triggered_profiles.remove(old_name)
                    self.triggered_profiles.add(name)

            self.profiles[name] = {
                "is_active": is_active,
                "run_in_order": run_in_order,
                "auto_close": auto_close,
                "apps": apps_data
            }
            self.save_config()
            self.render_profiles()
            dialog.destroy()

if __name__ == "__main__":
    app = UniversalLauncher()
    app.mainloop()