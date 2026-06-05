import os
import sys
import json
import subprocess
import threading
import time
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QSlider, QLineEdit, QTextEdit, QFileDialog,
                             QGroupBox, QFormLayout, QCheckBox)
from PyQt5.QtCore import Qt, QTimer

CONFIG_PATH = "player_config.json"
WARM_STYLE = """
QMainWindow {background-color: #FFF5E6;}
QWidget {background-color: #FFF5E6; font-family: "微软雅黑"; font-size:10pt; color:#693710;}
QGroupBox {
    border:2px solid #FFBC80;
    border-radius:8px;
    margin-top:8px;
    padding-top:12px;
    color:#7a3e0c;
    font-weight:bold;
}
QGroupBox::title {subcontrol-origin: margin; left:10px;}
QPushButton {
    background-color:#FFA960;
    color:#492808;
    border:none;
    border-radius:6px;
    padding:7px 0;
}
QPushButton:hover {background-color:#FF9038;}
QLineEdit {
    border:1px solid #FFC998;
    border-radius:4px;
    background:#FFFAF0;
    padding:4px;
}
QTextEdit {
    border:1px solid #FFC998;
    border-radius:4px;
    background:#FFFAF0;
}
QSlider::groove:horizontal {
    background:#FFDDBB;
    height:8px;
    border-radius:4px;
}
QSlider::handle:horizontal {
    background:#FF8530;
    width:16px;
    height:16px;
    border-radius:8px;
    margin:-4px 0;
}
QCheckBox {color:#65320e;}
"""

class WarmPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("暖色调定时音频播放器")
        self.resize(690, 600)
        self.setStyleSheet(WARM_STYLE)

        self.ff_proc = None
        self.cur_idx = 0
        self.music_list = []
        self.loop_flag = False
        self.cur_volume = 80
        self.is_playing = False
        self.running = True

        self.cfg = self.load_cfg()
        self.build_ui()

        folder = self.cfg.get("folder_path", "")
        if os.path.isdir(folder):
            self.inp_path.setText(folder)
            self.load_music_folder(folder)

        self.cb_loop.setChecked(self.cfg.get("loop", False))
        self.loop_flag = self.cb_loop.isChecked()
        vol = self.cfg.get("volume", 80)
        self.slider_vol.setValue(vol)
        self.cur_volume = vol

        self.inp_st_h.setText(self.cfg.get("start_h", "08"))
        self.inp_st_m.setText(self.cfg.get("start_m", "00"))
        self.inp_st_s.setText(self.cfg.get("start_s", "00"))
        self.inp_ed_h.setText(self.cfg.get("end_h", "07"))
        self.inp_ed_m.setText(self.cfg.get("end_m", "00"))
        self.inp_ed_s.setText(self.cfg.get("end_s", "00"))

        edits = [self.inp_st_h, self.inp_st_m, self.inp_st_s, self.inp_ed_h, self.inp_ed_m, self.inp_ed_s]
        for ed in edits:
            ed.editingFinished.connect(self.save_current_config)

        # 独立时间检测线程
        self.time_thread = threading.Thread(target=self.time_detect_loop, daemon=True)
        self.time_thread.start()
        # 启动延迟自检
        QTimer.singleShot(350, self.auto_start_check)

    def auto_start_check(self):
        if self.check_in_time() and len(self.music_list) > 0 and not self.is_playing:
            self.start_play()

    def time2sec(self, h, m, s):
        try:
            return int(h)*3600 + int(m)*60 + int(s)
        except:
            return -1

    # 核心跨天算法：start=8*3600，end=7*3600（次日7点），大于开始或小于结束都生效
    def check_in_time(self):
        now = datetime.now()
        now_sec = now.hour*3600 + now.minute*60 + now.second
        s = self.time2sec(self.inp_st_h.text(), self.inp_st_m.text(), self.inp_st_s.text())
        e = self.time2sec(self.inp_ed_h.text(), self.inp_ed_m.text(), self.inp_ed_s.text())
        if s < 0 or e < 0:
            return False
        # 结束时刻 < 开始时刻 = 跨天时段（当天8:00 ~ 次日7:00）
        if e < s:
            return now_sec >= s or now_sec < e
        else:
            return s <= now_sec < e

    # 后台每秒循环检测
    def time_detect_loop(self):
        while self.running:
            in_slot = self.check_in_time()
            if in_slot and not self.is_playing and len(self.music_list) > 0:
                self.start_play()
            if not in_slot and self.is_playing:
                self.stop_play()
            time.sleep(1)

    def build_ui(self):
        center = QWidget()
        self.setCentralWidget(center)
        main_layout = QVBoxLayout(center)
        main_layout.setSpacing(11)
        main_layout.setContentsMargins(14,14,14,14)

        g_folder = QGroupBox("音频文件夹路径")
        lay_f = QHBoxLayout(g_folder)
        self.inp_path = QLineEdit()
        btn_sel = QPushButton("浏览选择")
        btn_sel.clicked.connect(self.select_dir)
        lay_f.addWidget(self.inp_path)
        lay_f.addWidget(btn_sel)
        main_layout.addWidget(g_folder)

        g_list = QGroupBox("播放清单")
        lay_list = QVBoxLayout(g_list)
        self.text_list = QTextEdit()
        self.text_list.setReadOnly(True)
        lay_list.addWidget(self.text_list)
        main_layout.addWidget(g_list)

        lay_btn = QHBoxLayout()
        self.btn_start = QPushButton("▶开始播放")
        self.btn_stop = QPushButton("■停止播放")
        self.btn_start.clicked.connect(self.start_play)
        self.btn_stop.clicked.connect(self.stop_play)
        lay_btn.addWidget(self.btn_start)
        lay_btn.addWidget(self.btn_stop)
        main_layout.addLayout(lay_btn)

        lay_vol = QHBoxLayout()
        lay_vol.addWidget(QLabel("音量"))
        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0,100)
        self.slider_vol.setValue(80)
        self.slider_vol.valueChanged.connect(self.set_vol)
        self.lab_vol = QLabel("80")
        lay_vol.addWidget(self.slider_vol)
        lay_vol.addWidget(self.lab_vol)
        main_layout.addLayout(lay_vol)

        self.cb_loop = QCheckBox("开启整列表循环播放")
        self.cb_loop.stateChanged.connect(self.switch_loop)
        main_layout.addWidget(self.cb_loop)

        g_time = QGroupBox("定时区间 | 时:分:秒")
        lay_time = QFormLayout(g_time)
        lay_start = QHBoxLayout()
        self.inp_st_h = QLineEdit("08")
        self.inp_st_m = QLineEdit("00")
        self.inp_st_s = QLineEdit("00")
        lay_start.addWidget(self.inp_st_h)
        lay_start.addWidget(QLabel("时"))
        lay_start.addWidget(self.inp_st_m)
        lay_start.addWidget(QLabel("分"))
        lay_start.addWidget(self.inp_st_s)
        lay_start.addWidget(QLabel("秒"))
        lay_time.addRow("开始:", lay_start)

        lay_end = QHBoxLayout()
        self.inp_ed_h = QLineEdit("07")
        self.inp_ed_m = QLineEdit("00")
        self.inp_ed_s = QLineEdit("00")
        lay_end.addWidget(self.inp_ed_h)
        lay_end.addWidget(QLabel("时"))
        lay_end.addWidget(self.inp_ed_m)
        lay_end.addWidget(QLabel("分"))
        lay_end.addWidget(self.inp_ed_s)
        lay_end.addWidget(QLabel("秒"))
        lay_time.addRow("结束:", lay_end)
        main_layout.addWidget(g_time)

        self.btn_save = QPushButton("💾保存配置")
        self.btn_save.clicked.connect(self.save_current_config)
        main_layout.addWidget(self.btn_save)

        info_group = QGroupBox("播放信息")
        info_lay = QVBoxLayout(info_group)
        self.lab_now = QLabel("当前曲目：无")
        self.lab_next = QLabel("下一首：无")
        info_lay.addWidget(self.lab_now)
        info_lay.addWidget(self.lab_next)
        main_layout.addWidget(info_group)
        self.lab_status = QLabel("●待机就绪")
        main_layout.addWidget(self.lab_status)

    def load_music_folder(self,path):
        self.kill_ff()
        self.music_list.clear()
        self.text_list.clear()
        self.cur_idx=0
        ext = (".mp3",".wav",".flac",".ogg",".m4a")
        try:
            files = sorted([os.path.join(path,f) for f in os.listdir(path) if f.lower().endswith(ext)])
        except:
            files=[]
        self.music_list = files
        for f in files:
            self.text_list.append(os.path.basename(f))
        self.lab_status.setText(f"载入{len(files)}首音频")

    def select_dir(self):
        p = QFileDialog.getExistingDirectory()
        if p:
            self.inp_path.setText(p)
            self.load_music_folder(p)
            self.save_current_config()

    def kill_ff(self):
        if self.ff_proc:
            try:
                self.ff_proc.terminate()
            except:pass
        self.ff_proc = None

    def play_one(self):
        if not self.music_list:
            return
        self.kill_ff()
        path = self.music_list[self.cur_idx]
        cmd = ["ffplay.exe","-nodisp","-autoexit","-volume",str(self.cur_volume),path]
        try:
            self.ff_proc = subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            self.lab_now.setText(f"当前曲目：{os.path.basename(path)}")
        except:
            self.lab_status.setText("缺少ffplay.exe")

    def play_loop_func(self):
        while self.is_playing and self.running:
            if not self.check_in_time() or len(self.music_list)==0:
                time.sleep(0.5)
                continue
            self.play_one()
            while self.ff_proc and self.ff_proc.poll() is None and self.is_playing:
                time.sleep(0.3)
            self.cur_idx +=1
            if self.cur_idx >= len(self.music_list):
                self.cur_idx = 0 if self.loop_flag else len(self.music_list)-1

    def start_play(self):
        if self.is_playing:
            return
        self.is_playing = True
        threading.Thread(target=self.play_loop_func,daemon=True).start()
        self.lab_status.setText("正在自动播放")

    def stop_play(self):
        self.is_playing = False
        self.kill_ff()
        self.lab_status.setText("已停止")

    def set_vol(self,val):
        self.cur_volume = val
        self.lab_vol.setText(str(val))

    def switch_loop(self):
        self.loop_flag = self.cb_loop.isChecked()

    def save_current_config(self):
        self.cfg["folder_path"] = self.inp_path.text()
        self.cfg["start_h"]=self.inp_st_h.text()
        self.cfg["start_m"]=self.inp_st_m.text()
        self.cfg["start_s"]=self.inp_st_s.text()
        self.cfg["end_h"]=self.inp_ed_h.text()
        self.cfg["end_m"]=self.inp_ed_m.text()
        self.cfg["end_s"]=self.inp_ed_s.text()
        self.cfg["volume"]=self.cur_volume
        self.cfg["loop"]=self.loop_flag
        with open(CONFIG_PATH,"w",encoding="utf-8") as f:
            json.dump(self.cfg,f,ensure_ascii=False,indent=2)
        self.lab_status.setText("配置已保存")

    def load_cfg(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH,"r",encoding="utf-8") as f:
                return json.load(f)
        return {}

    def closeEvent(self,e):
        self.running=False
        self.stop_play()
        self.save_current_config()
        e.accept()

if __name__ == "__main__":
    app=QApplication(sys.argv)
    win=WarmPlayer()
    win.show()
    sys.exit(app.exec_())
