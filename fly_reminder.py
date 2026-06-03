#!/usr/bin/env python3
"""
飞机提醒 - Windows 桌面定时提醒工具
到时间后小飞机从屏幕左向右划过
"""

import sys
import os
import math
import time
import random
import threading
import datetime
import json
import hashlib
import urllib.request
import urllib.error
import tempfile
import subprocess
import shutil
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

# ---------- 版本号 ----------
APP_VERSION = "1.1.0"
VERSION_CHECK_URL = "https://api.github.com/repos/nickw116/fly-reminder/releases/latest"

# ---------- 平台检测 ----------
IS_WINDOWS = sys.platform == "win32"

# ---------- 飞机多边形顶点 ----------
PLANE_BODY = [(0, 0), (30, -3), (35, -3), (38, -1), (38, 1), (35, 3), (30, 3), (0, 0)]
PLANE_TOP_WING = [(8, -2), (14, -18), (22, -18), (18, -2)]
PLANE_BOTTOM_WING = [(8, 2), (14, 18), (22, 18), (18, 2)]
PLANE_TAIL_TOP = [(30, -3), (34, -12), (38, -12), (35, -3)]
PLANE_TAIL_BOT = [(30, 3), (34, 12), (38, 12), (35, 3)]

# ---------- 配色 ----------
C = {
    "bg": "#1e1e2e", "panel": "#181825", "card": "#313244",
    "accent": "#f38ba8", "accent2": "#fab387", "text": "#cdd6f4",
    "dim": "#6c7086", "input": "#11111b",
    "btn": "#f38ba8", "btn_hi": "#f5c2e7",
    "plane": "#eff1f5", "wing": "#bac2de", "tail_c": "#a6adc8",
    "sky1": "#89b4fa", "sky2": "#cdd6f4", "sun": "#f9e2af",
    "trail": "#f38ba8",
    "green": "#a6e3a1", "yellow": "#f9e2af",
}

DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "FlyReminder"


# ==============================================================
#  版本检测 & 更新
# ==============================================================
class Updater:

    def __init__(self, root):
        self.root = root
        self._latest = None

    def check(self, silent=True):
        """后台检测新版本，silent=True 时不弹窗提示已最新"""
        threading.Thread(target=self._do_check, args=(silent,), daemon=True).start()

    def _do_check(self, silent):
        if not VERSION_CHECK_URL:
            if not silent:
                self.root.after(0, lambda: messagebox.showinfo("检查更新", "未配置版本检测地址"))
            return
        try:
            req = urllib.request.Request(VERSION_CHECK_URL, headers={"User-Agent": "FlyReminder"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            raw_tag = data.get("tag_name", "")
            tag = raw_tag.removeprefix("v")
            url = ""
            for asset in data.get("assets", []):
                if asset["name"].endswith(".exe") and "Setup" in asset["name"]:
                    url = asset["browser_download_url"]
                    break
            if not url:
                url = data.get("html_url", "")
            self._latest = dict(version=tag, url=url, notes=data.get("body", ""))
        except Exception as e:
            if not silent:
                self.root.after(0, lambda: messagebox.showwarning("检测失败", f"无法检查更新:\n{e}"))
            return

        if self._latest and self._newer(self._latest["version"]):
            self.root.after(0, self._prompt_update)
        elif not silent:
            self.root.after(0, lambda: messagebox.showinfo("检查更新", f"当前已是最新版本 v{APP_VERSION}"))

    @staticmethod
    def _newer(remote):
        try:
            rp = [int(x) for x in remote.split(".")]
            lp = [int(x) for x in APP_VERSION.split(".")]
            # 补齐长度后逐段比较
            length = max(len(rp), len(lp))
            rp += [0] * (length - len(rp))
            lp += [0] * (length - len(lp))
            return rp > lp
        except Exception:
            return False

    def _prompt_update(self):
        v = self._latest["version"]
        win = tk.Toplevel(self.root)
        win.title("发现新版本")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()
        self._center(win, 400, 240)

        tk.Label(win, text="✈ 发现新版本!", font=("Microsoft YaHei UI", 16, "bold"),
                 fg=C["accent"], bg=C["bg"]).pack(pady=(20, 4))
        tk.Label(win, text=f"当前版本: v{APP_VERSION}    →    最新版本: v{v}",
                 font=("Microsoft YaHei UI", 10), fg=C["text"], bg=C["bg"]).pack(pady=4)

        notes = self._latest.get("notes", "")
        if notes:
            tk.Label(win, text=notes[:200], font=("Microsoft YaHei UI", 9),
                     fg=C["dim"], bg=C["panel"], wraplength=360, justify="left").pack(padx=20, pady=6, ipady=4)

        bf = tk.Frame(win, bg=C["bg"])
        bf.pack(pady=(8, 16))
        tk.Button(bf, text="立即更新", font=("Microsoft YaHei UI", 10, "bold"),
                  bg=C["green"], fg="#11111b", relief="flat", cursor="hand2", width=10,
                  command=lambda: [win.destroy(), self._do_update()]).pack(side="left", padx=8)
        tk.Button(bf, text="稍后再说", font=("Microsoft YaHei UI", 10),
                  bg=C["card"], fg=C["text"], relief="flat", cursor="hand2", width=10,
                  command=win.destroy).pack(side="left", padx=8)

    def _do_update(self):
        if not self._latest:
            return
        url = self._latest["url"]
        if not url:
            messagebox.showinfo("更新", "请在浏览器中手动下载更新。")
            return

        # 显示下载进度窗口
        pw = tk.Toplevel(self.root)
        pw.title("正在更新")
        pw.configure(bg=C["bg"])
        pw.resizable(False, False)
        pw.grab_set()
        self._center(pw, 360, 120)
        tk.Label(pw, text="正在下载更新...", font=("Microsoft YaHei UI", 11),
                 fg=C["text"], bg=C["bg"]).pack(pady=(20, 8))
        progress = ttk.Progressbar(pw, length=300, mode="determinate")
        progress.pack(pady=(0, 20))

        def download():
            try:
                tmp_dir = tempfile.mkdtemp()
                fname = os.path.join(tmp_dir, "fly-reminder-update.exe")
                req = urllib.request.Request(url, headers={"User-Agent": "FlyReminder"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    done = 0
                    sha = hashlib.sha256()
                    with open(fname, "wb") as f:
                        while True:
                            chunk = resp.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                            sha.update(chunk)
                            done += len(chunk)
                            if total and total > 0:
                                pw.after(0, lambda d=done, t=total: progress.configure(value=d * 100 / t))

                # 校验下载完整性（比对文件大小）
                if total and done != total:
                    raise Exception(f"下载不完整: {done}/{total} bytes")

                pw.after(0, lambda: pw.destroy())
                # 运行安装包，之后清理临时文件
                if IS_WINDOWS:
                    os.startfile(fname)
                else:
                    subprocess.Popen([fname])
                # 延迟清理临时目录（给安装程序足够启动时间）
                self.root.after(30000, lambda: shutil.rmtree(tmp_dir, ignore_errors=True))
                # 退出当前程序
                self.root.after(500, self.root.destroy)
            except Exception as e:
                pw.after(0, lambda: [pw.destroy(), messagebox.showerror("更新失败", str(e))])

        threading.Thread(target=download, daemon=True).start()

    @staticmethod
    def _center(win, w, h):
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


# ==============================================================
#  主应用
# ==============================================================
class FlyReminder:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("飞机提醒")
        self.root.geometry("440x580")
        self.root.resizable(False, False)
        self.root.configure(bg=C["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.reminders: list[dict] = []
        self._rid = 0
        self._closing = False
        self._list_refresh_id = None

        self.updater = Updater(self.root)

        self._build_ui()
        self._center(self.root, 440, 580)

        # 启动后静默检查更新
        self.root.after(3000, lambda: self.updater.check(silent=True))

    # -------------------- 窗口居中 --------------------
    @staticmethod
    def _center(win, w, h):
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ================================================================
    #  UI 构建
    # ================================================================
    def _build_ui(self):
        # ---- 标题栏 ----
        hdr = tk.Frame(self.root, bg=C["bg"])
        hdr.pack(fill="x", padx=24, pady=(20, 4))
        tk.Label(hdr, text="飞机提醒", font=("Microsoft YaHei UI", 20, "bold"),
                 fg=C["accent"], bg=C["bg"]).pack(side="left")

        # 版本 + 更新按钮
        ver_frame = tk.Frame(hdr, bg=C["bg"])
        ver_frame.pack(side="left", padx=6, pady=(10, 0))
        self._ver_label = tk.Label(ver_frame, text=f"v{APP_VERSION}", font=("Consolas", 9),
                                   fg=C["dim"], bg=C["bg"])
        self._ver_label.pack(side="left")
        self._update_btn = tk.Label(ver_frame, text="  检查更新", font=("Microsoft YaHei UI", 8),
                                    fg=C["accent"], bg=C["bg"], cursor="hand2")
        self._update_btn.pack(side="left")
        self._update_btn.bind("<Button-1>", lambda e: self._on_check_update())
        self._update_btn.bind("<Enter>", lambda e: self._update_btn.config(fg=C["btn_hi"]))
        self._update_btn.bind("<Leave>", lambda e: self._update_btn.config(fg=C["accent"]))

        tk.Label(self.root, text="设定时间点，小飞机准时飞过屏幕提醒你",
                 font=("Microsoft YaHei UI", 9), fg=C["dim"], bg=C["bg"]).pack(anchor="w", padx=24)

        # ---- 输入区 ----
        inp = tk.Frame(self.root, bg=C["panel"])
        inp.pack(fill="x", padx=24, pady=(12, 6), ipady=6)

        tk.Label(inp, text="提醒内容", font=("Microsoft YaHei UI", 10, "bold"),
                 fg=C["text"], bg=C["panel"]).pack(anchor="w", padx=14, pady=(10, 2))
        self.msg_var = tk.StringVar(value="该休息一下啦！")
        self.msg_entry = tk.Entry(inp, textvariable=self.msg_var, font=("Microsoft YaHei UI", 11),
                                  bg=C["input"], fg=C["text"], insertbackground=C["text"],
                                  relief="flat", bd=5)
        self.msg_entry.pack(fill="x", padx=14, pady=(0, 8))

        # 提醒时间点
        row = tk.Frame(inp, bg=C["panel"])
        row.pack(fill="x", padx=14)

        now = datetime.datetime.now()
        self.h_var = tk.StringVar(value=f"{now.hour:02d}")
        self.m_var = tk.StringVar(value=f"{now.minute:02d}")
        self.s_var = tk.StringVar(value="00")

        tk.Label(row, text="提醒时间:", font=("Microsoft YaHei UI", 10, "bold"),
                 fg=C["text"], bg=C["panel"]).pack(side="left")

        for label_text, var, max_v in [("时", self.h_var, 23), ("分", self.m_var, 59), ("秒", self.s_var, 59)]:
            sp = tk.Spinbox(row, from_=0, to=max_v, textvariable=var, width=3, format="%02.0f",
                            font=("Consolas", 16), bg=C["input"], fg=C["text"],
                            insertbackground=C["text"], relief="flat", bd=3,
                            buttonbackground=C["card"])
            sp.pack(side="left", padx=2)
            tk.Label(row, text=label_text, font=("Microsoft YaHei UI", 10),
                     fg=C["dim"], bg=C["panel"]).pack(side="left")

        # 快捷按钮
        qf = tk.Frame(inp, bg=C["panel"])
        qf.pack(fill="x", padx=14, pady=(8, 10))
        for txt, delta_h, delta_m in [("半小时后", 0, 30), ("1小时后", 1, 0),
                                       ("2小时后", 2, 0), ("明早9点", 9, 0)]:
            b = tk.Button(qf, text=txt, font=("Microsoft YaHei UI", 8),
                          bg=C["card"], fg=C["text"], relief="flat", cursor="hand2",
                          command=lambda dh=delta_h, dm=delta_m, t=txt: self._quick_time(dh, dm, t))
            b.pack(side="left", padx=2, expand=True, fill="x")
            b.bind("<Enter>", lambda e, w=b: w.config(bg=C["accent"]))
            b.bind("<Leave>", lambda e, w=b: w.config(bg=C["card"]))

        # ---- 添加按钮 ----
        self.add_btn = tk.Button(
            self.root, text="✈  添加提醒", font=("Microsoft YaHei UI", 12, "bold"),
            bg=C["btn"], fg="#11111b", activebackground=C["btn_hi"],
            relief="flat", cursor="hand2", command=self._add_reminder)
        self.add_btn.pack(fill="x", padx=24, pady=(6, 8), ipady=7)
        self.add_btn.bind("<Enter>", lambda e: self.add_btn.config(bg=C["btn_hi"]))
        self.add_btn.bind("<Leave>", lambda e: self.add_btn.config(bg=C["btn"]))

        # ---- 提醒列表 ----
        tk.Label(self.root, text="提醒列表", font=("Microsoft YaHei UI", 11, "bold"),
                 fg=C["text"], bg=C["bg"]).pack(anchor="w", padx=24, pady=(4, 2))

        lf = tk.Frame(self.root, bg=C["panel"])
        lf.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self.list_canvas = tk.Canvas(lf, bg=C["panel"], highlightthickness=0)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.list_canvas.yview)
        self.scroll_frame = tk.Frame(self.list_canvas, bg=C["panel"])
        self.scroll_frame.bind("<Configure>",
                               lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.list_canvas.configure(yscrollcommand=sb.set)
        self.list_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._empty_label = tk.Label(self.list_canvas, text="暂无提醒，添加一个吧 ✈",
                                     font=("Microsoft YaHei UI", 10),
                                     fg=C["dim"], bg=C["panel"])
        self.list_canvas.create_window(196, 20, window=self._empty_label)

    # ================================================================
    #  版本检测
    # ================================================================
    def _on_check_update(self):
        self._update_btn.config(text="  检测中...", fg=C["yellow"])
        self.root.update_idletasks()
        self.updater.check(silent=False)
        self.root.after(3000, lambda: self._update_btn.config(text="  检查更新", fg=C["accent"]))

    # ================================================================
    #  提醒逻辑
    # ================================================================
    def _quick_time(self, delta_h, delta_m, label):
        now = datetime.datetime.now()
        if label == "明早9点":
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
        else:
            target = now + datetime.timedelta(hours=delta_h, minutes=delta_m)
        self.h_var.set(f"{target.hour:02d}")
        self.m_var.set(f"{target.minute:02d}")
        self.s_var.set(f"{target.second:02d}")

    def _add_reminder(self):
        try:
            h = int(self.h_var.get())
            m = int(self.m_var.get())
            s = int(self.s_var.get())
        except ValueError:
            return

        now = datetime.datetime.now()
        target = now.replace(hour=h, minute=m, second=s, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)

        msg = self.msg_var.get().strip() or "时间到！"
        self._rid += 1
        r = dict(id=self._rid, message=msg, target=target, active=True)
        self.reminders.append(r)
        self._refresh_list()

        threading.Thread(target=self._wait_until, args=(r,), daemon=True).start()

    def _wait_until(self, r):
        while r["active"] and not self._closing:
            now = datetime.datetime.now()
            diff = (r["target"] - now).total_seconds()
            if diff <= 0:
                break
            time.sleep(min(1, diff))
        if r["active"] and not self._closing:
            self.root.after(0, self._fire, r)

    def _fire(self, r):
        self._fly(r["message"])
        self.reminders = [x for x in self.reminders if x["id"] != r["id"]]
        self._refresh_list()
        if IS_WINDOWS:
            self._win_notify(r["message"])

    def _cancel(self, rid):
        for r in self.reminders:
            if r["id"] == rid:
                r["active"] = False
        self.reminders = [x for x in self.reminders if x["id"] != rid]
        self._refresh_list()

    def _refresh_list(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        if not self.reminders:
            self._empty_label = tk.Label(self.list_canvas, text="暂无提醒，添加一个吧 ✈",
                                         font=("Microsoft YaHei UI", 10),
                                         fg=C["dim"], bg=C["panel"])
            self.list_canvas.create_window(196, 20, window=self._empty_label)
            if self._list_refresh_id:
                self.root.after_cancel(self._list_refresh_id)
                self._list_refresh_id = None
            return

        for r in self.reminders:
            row = tk.Frame(self.scroll_frame, bg=C["card"])
            row.pack(fill="x", padx=4, pady=2, ipady=4)
            tgt = r["target"]
            tgt_str = tgt.strftime("%H:%M:%S")
            now = datetime.datetime.now()
            diff = max(0, int((tgt - now).total_seconds()))
            left_str = f"{diff//3600:02d}:{diff%3600//60:02d}:{diff%60:02d}"
            tk.Label(row, text=f"✈ {r['message']}   🕐 {tgt_str}   ⏳ {left_str}",
                     font=("Microsoft YaHei UI", 9), fg=C["text"], bg=C["card"]).pack(side="left", padx=8)
            tk.Button(row, text="✕", font=("Arial", 9, "bold"), bg=C["accent"], fg="white",
                      relief="flat", width=3, cursor="hand2",
                      command=lambda rid=r["id"]: self._cancel(rid)).pack(side="right", padx=4)

        if self._list_refresh_id:
            self.root.after_cancel(self._list_refresh_id)
        self._list_refresh_id = self.root.after(500, self._refresh_list)

    # ================================================================
    #  飞机动画 — 透明背景，只有飞机从左到右滑过屏幕
    # ================================================================
    def _fly(self, message):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        # 透明色 key — 背景用这个颜色，Windows 会让它完全透明
        TRANS_KEY = "#010101"

        # 窗口全屏但背景透明
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{sw}x{sh}+0+0")

        # Windows 透明色: 与该颜色相同的像素全部透明
        try:
            win.attributes("-transparentcolor", TRANS_KEY)
        except Exception:
            pass

        cv = tk.Canvas(win, width=sw, height=sh, highlightthickness=0, bg=TRANS_KEY)
        cv.pack()

        # 飞机参数
        sc = 3.0
        base_y = sh // 3
        start_x = -200
        end_x = sw + 200

        parts = self._draw_plane(cv, start_x, base_y, sc)
        trails = []

        # 消息气泡跟随飞机上方
        bubble_shadow = cv.create_rectangle(0, 0, 0, 0, fill="#00000033", outline="")
        bubble = cv.create_rectangle(0, 0, 0, 0, fill="white", outline=C["accent"], width=2, smooth=False)
        bubble_text = cv.create_text(0, 0, text=f"  {message}  ",
                                     font=("Microsoft YaHei UI", 13, "bold"), fill=C["accent"])

        fc = [0]
        speed = 9

        def step():
            x = start_x + fc[0] * speed
            if x > end_x or self._closing:
                win.destroy()
                return

            y = base_y + math.sin(fc[0] * 0.03) * 40

            # 尾迹 (白色小圆点, 不是 TRANS_KEY 所以可见)
            if fc[0] % 2 == 0 and len(trails) < 120:
                t1 = cv.create_oval(x, y + 6, x + 10, y + 15, fill="#d0d8e8", outline="")
                t2 = cv.create_oval(x, y - 15, x + 10, y - 6, fill="#d0d8e8", outline="")
                trails.extend([t1, t2])
                if len(trails) > 60:
                    cv.delete(trails.pop(0)); cv.delete(trails.pop(0))

            # 移动飞机
            self._move_plane(cv, parts, x, y, sc)

            # 移动气泡到飞机上方
            bw = max(len(message) * 15 + 30, 120)
            bh = 36
            bx_center = x + 55 * sc / 3.5
            by_center = y - 65
            if by_center < 10:
                by_center = y + 55
            cv.coords(bubble, bx_center - bw // 2, by_center - bh // 2,
                      bx_center + bw // 2, by_center + bh // 2)
            cv.coords(bubble_text, bx_center, by_center)
            for item in (bubble, bubble_text):
                cv.tag_raise(item)

            fc[0] += 1
            win.after(16, step)

        win.after(8000, lambda: win.destroy() if win.winfo_exists() else None)
        step()

    # ---- 绘制云朵 ----
    @staticmethod
    def _cloud(cv, cx, cy, s):
        for dx, dy, rx, ry in [(-0.5, -0.3, 0.5, 0.4), (0.2, -0.4, 0.4, 0.35), (0, 0.1, 0.7, 0.4)]:
            cv.create_oval(cx + dx * s - rx * s, cy + dy * s - ry * s,
                           cx + dx * s + rx * s, cy + dy * s + ry * s,
                           fill="#ffffff", outline="", stipple="gray75")

    # ---- 绘制 / 移动飞机 ----
    def _draw_plane(self, cv, x, y, sc):
        p = {}
        for name, poly in [("body", PLANE_BODY), ("twing", PLANE_TOP_WING),
                           ("bwing", PLANE_BOTTOM_WING), ("ttail", PLANE_TAIL_TOP),
                           ("btail", PLANE_TAIL_BOT)]:
            color = C["plane"] if name == "body" else (C["wing"] if "wing" in name else C["tail_c"])
            p[name] = cv.create_polygon(self._sp(poly, sc, x, y), fill=color, outline="#7f849c", width=1)
        for i, dx in enumerate([8, 14]):
            p[f"w{i}"] = cv.create_oval(x + dx * sc, y - 1.5 * sc, x + (dx + 4) * sc, y + 1.5 * sc,
                                        fill="#74c7ec", outline="#89b4fa")
        return p

    def _move_plane(self, cv, p, x, y, sc):
        for name, poly in [("body", PLANE_BODY), ("twing", PLANE_TOP_WING),
                           ("bwing", PLANE_BOTTOM_WING), ("ttail", PLANE_TAIL_TOP),
                           ("btail", PLANE_TAIL_BOT)]:
            cv.coords(p[name], *self._sp(poly, sc, x, y))
        for i, dx in enumerate([8, 14]):
            cv.coords(p[f"w{i}"], x + dx * sc, y - 1.5 * sc, x + (dx + 4) * sc, y + 1.5 * sc)
        for v in p.values():
            cv.tag_raise(v)

    @staticmethod
    def _sp(pts, sc, ox, oy):
        r = []
        for px, py in pts:
            r.extend([px * sc + ox, py * sc + oy])
        return r

    # ================================================================
    #  Windows 通知
    # ================================================================
    def _win_notify(self, msg):
        if not IS_WINDOWS:
            return
        try:
            from ctypes import windll
            hwnd = int(self.root.winfo_id())
            windll.user32.FlashWindow(hwnd, True)
        except Exception:
            pass

    # ================================================================
    #  生命周期
    # ================================================================
    def _on_close(self):
        self._closing = True
        for r in self.reminders:
            r["active"] = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = FlyReminder()
    app.run()
