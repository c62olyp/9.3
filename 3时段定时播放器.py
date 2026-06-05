import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import os
import time
import threading
from datetime import datetime
import configparser
import sys
import winreg

APP_REG_NAME = "定时音频播放器"


class TimeAudioPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("三时段定时播放器")
        self.root.geometry("700x550")
        self.root.resizable(True, True)
        self.root.configure(bg="#FFF5E6")
        self.ini_file = "config.ini"
        self.cfg = configparser.ConfigParser()

        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.style.configure("Card.TLabelframe",
                             background="#FFE8CC",
                             relief="groove",
                             borderwidth=2)
        self.style.configure("Card.TLabelframe.Label",
                             font=("微软雅黑", 10, "bold"),
                             foreground="#D2691E",
                             background="#FFE8CC")

        self.style.configure("MainBtn.TButton",
                             font=("微软雅黑", 9),
                             background="#FF9500",
                             foreground="white",
                             borderwidth=0)
        self.style.map("MainBtn.TButton",
                       background=[('active', '#FF7700')])

        self.style.configure("Check.TCheckbutton",
                             background="#FFF5E6",
                             font=("微软雅黑", 9))

        def get_ffplay_path():
            if hasattr(sys, '_MEIPASS'):
                return os.path.join(sys._MEIPASS, "ffplay.exe")
            return os.path.join(os.path.abspath("."), "ffplay.exe")

        self.ff_bin = get_ffplay_path()

        self._audio_cache = {"p1": [], "p2": [], "p3": []}
        self._last_slot = -1
        self.path_changed = [False, False, False]
        self.config_modified = False

        self.playlist1 = []
        self.playlist2 = []
        self.playlist3 = []
        self.current_playlist = []
        self.current_index = 0
        self.ffplay_process = None
        self.is_playing = False
        self.running = True

        self.path1 = tk.StringVar()
        self.path2 = tk.StringVar()
        self.path3 = tk.StringVar()

        self.vol1 = tk.IntVar(value=80)
        self.vol2 = tk.IntVar(value=80)
        self.vol3 = tk.IntVar(value=80)
        self.auto_start_var = tk.BooleanVar()

        self.t1h = tk.StringVar(value="08")
        self.t1m = tk.StringVar(value="00")
        self.t1s = tk.StringVar(value="00")
        self.t1eh = tk.StringVar(value="12")
        self.t1em = tk.StringVar(value="00")
        self.t1es = tk.StringVar(value="00")

        self.t2h = tk.StringVar(value="12")
        self.t2m = tk.StringVar(value="00")
        self.t2s = tk.StringVar(value="00")
        self.t2eh = tk.StringVar(value="18")
        self.t2em = tk.StringVar(value="00")
        self.t2es = tk.StringVar(value="00")

        self.t3h = tk.StringVar(value="18")
        self.t3m = tk.StringVar(value="00")
        self.t3s = tk.StringVar(value="00")
        self.t3eh = tk.StringVar(value="23")
        self.t3em = tk.StringVar(value="59")
        self.t3es = tk.StringVar(value="59")

        self.h_list = [f"{i:02d}" for i in range(24)]
        self.ms_list = [f"{i:02d}" for i in range(60)]

        self.setup_ui()
        self.auto_start_var.set(self.check_auto_start_reg())
        self.load_config()
        self.bind_modified_mark()
        self.auto_start_var.trace("w", self.on_auto_start_change)

        self.path_changed = [True, True, True]
        self.refresh_all_audio_cache()
        self.path_changed = [False, False, False]

        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)
        self.time_thread = threading.Thread(target=self.time_detect_loop, daemon=True)
        self.time_thread.start()
        self.root.after(350, self.start_play)

    def get_run_cmd(self):
        exe_path = os.path.abspath(sys.argv[0])
        if hasattr(sys, '_MEIPASS'):
            return '"{}"'.format(exe_path)
        pyw = sys.executable.replace("python.exe", "pythonw.exe")
        return '"{}" "{}"'.format(pyw, exe_path)

    def check_auto_start_reg(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                 winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_REG_NAME)
            winreg.CloseKey(key)
            return True
        except:
            return False

    def set_auto_start_reg(self, is_open):
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_WRITE)
            if is_open:
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, self.get_run_cmd())
            else:
                winreg.DeleteValue(key, APP_REG_NAME)
            winreg.CloseKey(key)
        except Exception as e:
            self.status_var.set("自启设置异常")

    def on_auto_start_change(self, *args):
        self.set_auto_start_reg(self.auto_start_var.get())

    def on_close_window(self):
        self.running = False
        self.kill_ff()
        self.root.destroy()

    def get_time_str(self, h, m, s):
        return "{}:{}:{}".format(h.get(), m.get(), s.get())

    def limit_num(self, var, minv, maxv):
        def check(*args):
            self.config_modified = True
            try:
                self.update_status_tip()
            except:
                pass
        var.trace("w", check)

    def bind_modified_mark(self):
        def mark_p1(*a):
            self.path_changed = [True, self.path_changed[1], self.path_changed[2]]
            self.config_modified = True
            self.update_status_tip()

        def mark_p2(*a):
            self.path_changed = [self.path_changed[0], True, self.path_changed[2]]
            self.config_modified = True
            self.update_status_tip()

        def mark_p3(*a):
            self.path_changed = [self.path_changed[0], self.path_changed[1], True]
            self.config_modified = True
            self.update_status_tip()

        self.path1.trace("w", mark_p1)
        self.path2.trace("w", mark_p2)
        self.path3.trace("w", mark_p3)

    def update_status_tip(self):
        if not hasattr(self, 'status'):
            return
        if self.config_modified:
            self.status.config(fg="#E63946")
            self.status_var.set("⚠ 配置已修改，请保存")
        else:
            self.status.config(fg="#2E7D32")
            self.status_var.set("✅ 运行正常")

    def load_config(self):
        time_vars = [
            (self.t1h, 0, 23), (self.t1m, 0, 59), (self.t1s, 0, 59),
            (self.t1eh, 0, 23), (self.t1em, 0, 59), (self.t1es, 0, 59),
            (self.t2h, 0, 23), (self.t2m, 0, 59), (self.t2s, 0, 59),
            (self.t2eh, 0, 23), (self.t2em, 0, 59), (self.t2es, 0, 59),
            (self.t3h, 0, 23), (self.t3m, 0, 59), (self.t3s, 0, 59),
            (self.t3eh, 0, 23), (self.t3em, 0, 59), (self.t3es, 0, 59),
        ]
        for v, mi, ma in time_vars:
            self.limit_num(v, mi, ma)

        if os.path.exists(self.ini_file):
            try:
                self.cfg.read(self.ini_file, encoding="utf-8")
                self.path1.set(self.cfg.get("PATH", "p1", fallback=""))
                self.path2.set(self.cfg.get("PATH", "p2", fallback=""))
                self.path3.set(self.cfg.get("PATH", "p3", fallback=""))
                self.vol1.set(self.cfg.getint("VOLUME", "v1", fallback=80))
                self.vol2.set(self.cfg.getint("VOLUME", "v2", fallback=80))
                self.vol3.set(self.cfg.getint("VOLUME", "v3", fallback=80))

                def split_tm(timestr, vh, vm, vs):
                    try:
                        hh, mm, ss = timestr.split(":")
                        vh.set(hh)
                        vm.set(mm)
                        vs.set(ss)
                    except:
                        pass

                split_tm(self.cfg.get("TIME", "t1s", fallback="08:00:00"), self.t1h, self.t1m, self.t1s)
                split_tm(self.cfg.get("TIME", "t1e", fallback="12:00:00"), self.t1eh, self.t1em, self.t1es)
                split_tm(self.cfg.get("TIME", "t2s", fallback="12:00:00"), self.t2h, self.t2m, self.t2s)
                split_tm(self.cfg.get("TIME", "t2e", fallback="18:00:00"), self.t2eh, self.t2em, self.t2es)
                split_tm(self.cfg.get("TIME", "t3s", fallback="18:00:00"), self.t3h, self.t3m, self.t3s)
                split_tm(self.cfg.get("TIME", "t3e", fallback="23:59:59"), self.t3eh, self.t3em, self.t3es)
            except:
                pass
        self.config_modified = False
        self.update_status_tip()

    def save_config_manual(self):
        self.cfg["PATH"] = {"p1": self.path1.get(), "p2": self.path2.get(), "p3": self.path3.get()}
        self.cfg["VOLUME"] = {"v1": str(self.vol1.get()), "v2": str(self.vol2.get()), "v3": str(self.vol3.get())}
        self.cfg["TIME"] = {
            "t1s": self.get_time_str(self.t1h, self.t1m, self.t1s),
            "t1e": self.get_time_str(self.t1eh, self.t1em, self.t1es),
            "t2s": self.get_time_str(self.t2h, self.t2m, self.t2s),
            "t2e": self.get_time_str(self.t2eh, self.t2em, self.t2es),
            "t3s": self.get_time_str(self.t3h, self.t3m, self.t3s),
            "t3e": self.get_time_str(self.t3eh, self.t3em, self.t3es),
        }
        with open(self.ini_file, "w", encoding="utf-8") as f:
            self.cfg.write(f)
        self.refresh_all_audio_cache()
        self.config_modified = False
        self.path_changed = [False, False, False]
        self.update_status_tip()

    def create_combo(self, parent, var, vlist):
        cb = ttk.Combobox(parent, textvariable=var, values=vlist, width=3, state="normal", font=("微软雅黑", 9))
        return cb

    def setup_ui(self):
        tk.Label(self.root, text="⏰ 三时段定时播放器", font=("微软雅黑", 13, "bold"),
                 bg="#FFF5E6", fg="#CC5500").pack(pady=5)

        frame_time = ttk.LabelFrame(self.root, text="时段设置", style="Card.TLabelframe")
        frame_time.pack(fill="x", padx=10, pady=4)
        ft = ("微软雅黑", 9)

        ttk.Label(frame_time, text="时段1:", font=ft).grid(row=0, column=0, pady=3, padx=3)
        cb1h = self.create_combo(frame_time, self.t1h, self.h_list)
        cb1h.grid(row=0, column=1)
        ttk.Label(frame_time, text=":", font=ft).grid(row=0, column=2)
        cb1m = self.create_combo(frame_time, self.t1m, self.ms_list)
        cb1m.grid(row=0, column=3)
        ttk.Label(frame_time, text=":", font=ft).grid(row=0, column=4)
        cb1s = self.create_combo(frame_time, self.t1s, self.ms_list)
        cb1s.grid(row=0, column=5)
        ttk.Label(frame_time, text="—", font=ft).grid(row=0, column=6, padx=2)
        cb1eh = self.create_combo(frame_time, self.t1eh, self.h_list)
        cb1eh.grid(row=0, column=7)
        ttk.Label(frame_time, text=":", font=ft).grid(row=0, column=8)
        cb1em = self.create_combo(frame_time, self.t1em, self.ms_list)
        cb1em.grid(row=0, column=9)
        ttk.Label(frame_time, text=":", font=ft).grid(row=0, column=10)
        cb1es = self.create_combo(frame_time, self.t1es, self.ms_list)
        cb1es.grid(row=0, column=11)
        ttk.Label(frame_time, text="音量", font=ft).grid(row=0, column=12, padx=4)
        ttk.Scale(frame_time, from_=0, to=100, variable=self.vol1, length=100, orient="horizontal").grid(row=0, column=13)

        ttk.Label(frame_time, text="时段2:", font=ft).grid(row=1, column=0, pady=3, padx=3)
        cb2h = self.create_combo(frame_time, self.t2h, self.h_list)
        cb2h.grid(row=1, column=1)
        ttk.Label(frame_time, text=":", font=ft).grid(row=1, column=2)
        cb2m = self.create_combo(frame_time, self.t2m, self.ms_list)
        cb2m.grid(row=1, column=3)
        ttk.Label(frame_time, text=":", font=ft).grid(row=1, column=4)
        cb2s = self.create_combo(frame_time, self.t2s, self.ms_list)
        cb2s.grid(row=1, column=5)
        ttk.Label(frame_time, text="—", font=ft).grid(row=1, column=6, padx=2)
        cb2eh = self.create_combo(frame_time, self.t2eh, self.h_list)
        cb2eh.grid(row=1, column=7)
        ttk.Label(frame_time, text=":", font=ft).grid(row=1, column=8)
        cb2em = self.create_combo(frame_time, self.t2em, self.ms_list)
        cb2em.grid(row=1, column=9)
        ttk.Label(frame_time, text=":", font=ft).grid(row=1, column=10)
        cb2es = self.create_combo(frame_time, self.t2es, self.ms_list)
        cb2es.grid(row=1, column=11)
        ttk.Label(frame_time, text="音量", font=ft).grid(row=1, column=12, padx=4)
        ttk.Scale(frame_time, from_=0, to=100, variable=self.vol2, length=100, orient="horizontal").grid(row=1, column=13)

        ttk.Label(frame_time, text="时段3:", font=ft).grid(row=2, column=0, pady=3, padx=3)
        cb3h = self.create_combo(frame_time, self.t3h, self.h_list)
        cb3h.grid(row=2, column=1)
        ttk.Label(frame_time, text=":", font=ft).grid(row=2, column=2)
        cb3m = self.create_combo(frame_time, self.t3m, self.ms_list)
        cb3m.grid(row=2, column=3)
        ttk.Label(frame_time, text=":", font=ft).grid(row=2, column=4)
        cb3s = self.create_combo(frame_time, self.t3s, self.ms_list)
        cb3s.grid(row=2, column=5)
        ttk.Label(frame_time, text="—", font=ft).grid(row=2, column=6, padx=2)
        cb3eh = self.create_combo(frame_time, self.t3eh, self.h_list)
        cb3eh.grid(row=2, column=7)
        ttk.Label(frame_time, text=":", font=ft).grid(row=2, column=8)
        cb3em = self.create_combo(frame_time, self.t3em, self.ms_list)
        cb3em.grid(row=2, column=9)
        ttk.Label(frame_time, text=":", font=ft).grid(row=2, column=10)
        cb3es = self.create_combo(frame_time, self.t3es, self.ms_list)
        cb3es.grid(row=2, column=11)
        ttk.Label(frame_time, text="音量", font=ft).grid(row=2, column=12, padx=4)
        ttk.Scale(frame_time, from_=0, to=100, variable=self.vol3, length=100, orient="horizontal").grid(row=2, column=13)

        frame_path = ttk.LabelFrame(self.root, text="音频目录", style="Card.TLabelframe")
        frame_path.pack(fill="x", padx=10, pady=4)
        path_info = [(self.path1, "时段1:"), (self.path2, "时段2:"), (self.path3, "时段3:")]
        for idx, (var, name) in enumerate(path_info):
            ttk.Label(frame_path, text=name, font=("微软雅黑", 9)).grid(row=idx, column=0, pady=3, padx=4)
            ttk.Entry(frame_path, textvariable=var, width=42, font=("微软雅黑", 9)).grid(row=idx, column=1, padx=3)
            ttk.Button(frame_path, text="浏览", command=lambda v=var, i=idx: self.select_folder(v, i),
                       style="MainBtn.TButton").grid(row=idx, column=2, padx=2)

        frame_list = ttk.LabelFrame(self.root, text="播放列表", style="Card.TLabelframe")
        frame_list.pack(fill="both", expand=True, padx=10, pady=4)
        list_font = ("微软雅黑", 9)

        self.lb1 = tk.Listbox(frame_list, selectbackground="#FF9500",
                              selectforeground="white", font=list_font,
                              bg="#FFFAF0", bd=1, relief="solid")
        self.lb2 = tk.Listbox(frame_list, selectbackground="#FF9500",
                              selectforeground="white", font=list_font,
                              bg="#FFFAF0", bd=1, relief="solid")
        self.lb3 = tk.Listbox(frame_list, selectbackground="#FF9500",
                              selectforeground="white", font=list_font,
                              bg="#FFFAF0", bd=1, relief="solid")

        self.lb1.grid(row=0, column=0, sticky="nsew", padx=2, pady=3)
        self.lb2.grid(row=0, column=1, sticky="nsew", padx=2, pady=3)
        self.lb3.grid(row=0, column=2, sticky="nsew", padx=2, pady=3)
        frame_list.grid_columnconfigure(0, weight=1)
        frame_list.grid_columnconfigure(1, weight=1)
        frame_list.grid_columnconfigure(2, weight=1)
        frame_list.grid_rowconfigure(0, weight=1)

        frame_btn = tk.Frame(self.root, bg="#FFF5E6")
        frame_btn.pack(pady=4)
        self.btn_start = ttk.Button(frame_btn, text="开始播放", command=self.start_play, style="MainBtn.TButton")
        self.btn_stop = ttk.Button(frame_btn, text="停止播放", command=self.stop_play, state="disabled",
                                   style="MainBtn.TButton")
        self.btn_save = ttk.Button(frame_btn, text="保存配置", command=self.save_config_manual, style="MainBtn.TButton")
        self.check_auto = ttk.Checkbutton(frame_btn, text="开机自启", variable=self.auto_start_var,
                                          style="Check.TCheckbutton")

        self.btn_start.grid(row=0, column=0, padx=4)
        self.btn_stop.grid(row=0, column=1, padx=4)
        self.btn_save.grid(row=0, column=2, padx=6)
        self.check_auto.grid(row=0, column=3, padx=4)

        self.status_var = tk.StringVar(value="✅ 运行正常")
        self.status = tk.Label(self.root, textvariable=self.status_var, font=("微软雅黑", 9),
                               bg="#FFF5E6", fg="#2E7D32")
        self.status.pack(pady=2)

    def select_folder(self, var, idx):
        folder = filedialog.askdirectory()
        if folder:
            var.set(folder)
            self.path_changed[idx] = True

    def get_audio(self, path):
        if not os.path.isdir(path):
            return []
        ext = (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg")
        try:
            return sorted([os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(ext)])
        except:
            return []

    def refresh_all_audio_cache(self):
        if self.path_changed[0]:
            self._audio_cache["p1"] = self.get_audio(self.path1.get())
        if self.path_changed[1]:
            self._audio_cache["p2"] = self.get_audio(self.path2.get())
        if self.path_changed[2]:
            self._audio_cache["p3"] = self.get_audio(self.path3.get())
        self.playlist1 = self._audio_cache["p1"]
        self.playlist2 = self._audio_cache["p2"]
        self.playlist3 = self._audio_cache["p3"]
        self.refresh_list_ui()

    def refresh_list_ui(self):
        if not hasattr(self, 'lb1'):
            return
        self.lb1.delete(0, tk.END)
        self.lb2.delete(0, tk.END)
        self.lb3.delete(0, tk.END)
        for f in self.playlist1:
            self.lb1.insert(tk.END, os.path.basename(f))
        for f in self.playlist2:
            self.lb2.insert(tk.END, os.path.basename(f))
        for f in self.playlist3:
            self.lb3.insert(tk.END, os.path.basename(f))
        self.clear_all_select()

    def clear_all_select(self):
        if not hasattr(self, 'lb1'):
            return
        self.lb1.selection_clear(0, tk.END)
        self.lb2.selection_clear(0, tk.END)
        self.lb3.selection_clear(0, tk.END)

    def set_highlight(self, slot, idx):
        self.clear_all_select()
        if slot == 1:
            self.lb1.selection_set(idx)
            self.lb1.see(idx)
        elif slot == 2:
            self.lb2.selection_set(idx)
            self.lb2.see(idx)
        elif slot == 3:
            self.lb3.selection_set(idx)
            self.lb3.see(idx)

    def time2sec(self, timestr):
        try:
            h, m, s = timestr.split(":")
            return int(h) * 3600 + int(m) * 60 + int(s)
        except:
            return -1

    def get_now_slot(self):
        now = datetime.now()
        ns = now.hour * 3600 + now.minute * 60 + now.second
        s1 = self.time2sec(self.get_time_str(self.t1h, self.t1m, self.t1s))
        e1 = self.time2sec(self.get_time_str(self.t1eh, self.t1em, self.t1es))
        s2 = self.time2sec(self.get_time_str(self.t2h, self.t2m, self.t2s))
        e2 = self.time2sec(self.get_time_str(self.t2eh, self.t2em, self.t2es))
        s3 = self.time2sec(self.get_time_str(self.t3h, self.t3m, self.t3s))
        e3 = self.time2sec(self.get_time_str(self.t3eh, self.t3em, self.t3es))

        def in_range(now, s, e):
            if s == -1 or e == -1:
                return False
            if e > s:
                return s <= now < e
            else:
                return now >= s or now < e

        if in_range(ns, s1, e1):
            return 1
        if in_range(ns, s2, e2):
            return 2
        if in_range(ns, s3, e3):
            return 3
        return 0

    def switch_playlist(self):
        slot = self.get_now_slot()
        vol = 80
        if slot == 1:
            self.current_playlist = self._audio_cache["p1"]
            vol = self.vol1.get()
        elif slot == 2:
            self.current_playlist = self._audio_cache["p2"]
            vol = self.vol2.get()
        elif slot == 3:
            self.current_playlist = self._audio_cache["p3"]
            vol = self.vol3.get()
        else:
            self.current_playlist = []
        self.current_index = 0
        return vol, slot

    def kill_ff(self):
        if self.ffplay_process:
            try:
                self.ffplay_process.terminate()
            except:
                pass
        self.ffplay_process = None

    def play_song(self, path, vol):
        self.kill_ff()
        cmd = [self.ff_bin, "-nodisp", "-autoexit", "-hide_banner", "-loglevel", "error", "-volume", str(vol), path]
        try:
            self.ffplay_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                   creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            self.status_var.set("音频播放异常")

    def play_loop(self):
        while self.is_playing and self.running:
            vol, slot = self.switch_playlist()
            if not self.current_playlist:
                self.status_var.set("当前时段无音频")
                self.clear_all_select()
                time.sleep(1)
                continue
            song = self.current_playlist[self.current_index]
            self.status_var.set("▶ {} | 音量:{}%".format(os.path.basename(song), vol))
            self.root.after(0, lambda: self.set_highlight(slot, self.current_index))
            self.play_song(song, vol)
            while self.ffplay_process and self.ffplay_process.poll() is None and self.is_playing and self.running:
                time.sleep(0.3)
            self.current_index = (self.current_index + 1) % len(self.current_playlist)
        self.kill_ff()
        self.clear_all_select()

    def start_play(self):
        if self.is_playing:
            return
        self.switch_playlist()
        self.is_playing = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        threading.Thread(target=self.play_loop, daemon=True).start()

    def stop_play(self):
        self.is_playing = False
        self.kill_ff()
        self.clear_all_select()
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.status_var.set("⏹ 已停止")
        self.status.config(fg="#C53030")

    def time_detect_loop(self):
        while self.running:
            new_slot = self.get_now_slot()
            if self.is_playing and new_slot != self._last_slot:
                self._last_slot = new_slot
                self.current_index = 0
                self.kill_ff()
            time.sleep(1)


if __name__ == "__main__":
    root = tk.Tk()
    app = TimeAudioPlayer(root)
    root.mainloop()