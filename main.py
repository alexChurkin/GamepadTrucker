"""Truck Remote Server V2 - drive ETS2/ATS with a DualShock 4 / DualSense.

The whole controller is republished as a virtual Xbox 360 pad (ViGEmBus), so
the game uses its built-in gamepad bindings with no manual setup. The gyroscope
replaces the left stick as the steering wheel; triggers are throttle/brake, the
right stick is camera look, and buttons keep their usual DualSense->Xbox layout.
"""

import os
import sys
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk

__version__ = "0.1.3"

from settings import Settings
from vjoy_output import VJoyController
from gyro_steering import GyroSteering
from pc_controller import PCController
from hid_gamepad import GamepadManager

BUTTON_REF = ("ETS2/ATS: bind vJoy axes - Steering=X, Throttle=Z, Brake=RZ, Look=RX/RY.\n"
              "D-pad: signals (<,>), hazard (^), ignition (v).  L1/R1 gears down/up.\n"
              "R3 = view zoom (mouse wheel).  Other buttons = default keys.")


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


class App:
    def __init__(self, root):
        self.root = root
        self.settings = Settings()
        self.vjoy = VJoyController()
        self.steering = GyroSteering(self.settings)
        self.controller = PCController(self.settings, self.vjoy)

        self._status_text = "Starting..."
        self._connected = False
        self._last_state = None
        self._rec = None            # open log file while recording
        self._rec_t0 = 0.0
        self._rec_last = 0.0

        self.manager = GamepadManager(on_state=self._on_state, on_status=self._on_status)

        self._build_ui()
        self.manager.start()
        self.root.after(33, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_state(self, state):
        self._last_state = state
        if self.settings.enabled:
            norm = self.steering.update(state)
            self.controller.update(state, norm)
        self._record(state)

    def _record(self, state):
        f = self._rec
        if f is None:
            return
        now = time.perf_counter()
        if now - self._rec_last < 0.01:      # ~100 Hz cap
            return
        self._rec_last = now
        gx, gy, gz = state.gyro
        ax, ay, az = state.accel
        ux, uy, uz = self.steering._axis
        try:
            f.write("%.3f,%d,%d,%d,%d,%d,%d,%.4f,%.3f,%.3f,%.3f\n" % (
                now - self._rec_t0, gx, gy, gz, ax, ay, az,
                self.steering.value, ux, uy, uz))
        except Exception:
            pass

    def _on_status(self, text, connected, has_motion):
        self._status_text = text
        self._connected = connected

    # -- UI -----------------------------------------------------------------
    def _build_ui(self):
        p = self.root
        p.title("Truck Remote Server V2  v" + __version__)
        p.resizable(False, False)
        try:
            p.iconbitmap(resource_path("app_icon.ico"))
        except Exception:
            pass
        pad = dict(padx=10, pady=4)

        self.lbl_status = tk.Label(p, text="", font=("Segoe UI", 11, "bold"),
                                   anchor="w", width=48)
        self.lbl_status.grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        xb = "vJoy device #1: OK (wheel)" if self.vjoy.available else \
             "vJoy NOT available - install/enable vJoy device #1"
        tk.Label(p, text=xb, anchor="w",
                 fg=("#1a7f1a" if self.vjoy.available else "#c00000")
                 ).grid(row=1, column=0, columnspan=2, sticky="w", **pad)

        tk.Label(p, text="Steering:").grid(row=2, column=0, sticky="w", **pad)
        self.canvas = tk.Canvas(p, width=300, height=24, bg="#f0f0f0",
                                highlightthickness=1, highlightbackground="#aaa")
        self.canvas.grid(row=2, column=1, sticky="w", **pad)
        self.canvas.create_line(150, 0, 150, 24, fill="#888")
        self._bar = self.canvas.create_rectangle(148, 3, 152, 21, fill="#1a7f1a", outline="")

        tk.Label(p, text="Gas (R2):").grid(row=3, column=0, sticky="w", **pad)
        self.pb_gas = ttk.Progressbar(p, length=300, maximum=100)
        self.pb_gas.grid(row=3, column=1, sticky="w", **pad)
        tk.Label(p, text="Brake (L2):").grid(row=4, column=0, sticky="w", **pad)
        self.pb_brake = ttk.Progressbar(p, length=300, maximum=100)
        self.pb_brake.grid(row=4, column=1, sticky="w", **pad)

        self.var_enabled = tk.BooleanVar(value=self.settings.enabled)
        ttk.Checkbutton(p, text="Enabled (sending to game)", variable=self.var_enabled,
                        command=self._on_enabled).grid(row=5, column=0, columnspan=2,
                                                       sticky="w", **pad)

        self._scales = {}
        self._add_scale(p, "Sensitivity", "sensitivity", 1, 100, 6)
        self._add_scale(p, "Smoothing (%)", "smoothing", 0, 95, 7)
        self._add_scale(p, "Dead zone (%)", "deadzone", 0, 30, 8)
        self._add_scale(p, "Expo (%)", "expo", 0, 90, 9,
                        to_setting=lambda v: v / 100.0, from_setting=lambda s: s * 100.0)
        self._add_scale(p, "Camera look deadzone (%)", "look_deadzone", 0, 40, 10)

        self.var_invert = tk.BooleanVar(value=self.settings.invert)
        ttk.Checkbutton(p, text="Invert steering", variable=self.var_invert,
                        command=self._on_invert).grid(row=11, column=0, sticky="w", **pad)
        self.var_look = tk.BooleanVar(value=self.settings.look_enabled)
        ttk.Checkbutton(p, text="Right stick = camera look", variable=self.var_look,
                        command=self._on_look).grid(row=11, column=1, sticky="w", **pad)

        ttk.Button(p, text="Recenter wheel  (hold in neutral, then click)",
                   command=self.steering.request_recenter).grid(
            row=12, column=0, columnspan=2, sticky="we", padx=10, pady=(10, 2))
        ttk.Button(p, text="Calibrate steering  (turn wheel left<->right)",
                   command=self._on_calibrate).grid(
            row=13, column=0, columnspan=2, sticky="we", padx=10, pady=(0, 2))
        self.lbl_calib = tk.Label(p, text="", fg="#777", font=("Segoe UI", 8), anchor="w")
        self.lbl_calib.grid(row=14, column=0, columnspan=2, sticky="w", padx=10)
        ttk.Button(p, text="Reset to defaults",
                   command=self._on_reset_defaults).grid(
            row=15, column=0, columnspan=2, sticky="we", padx=10, pady=(2, 6))

        tk.Label(p, text=BUTTON_REF, fg="#555", justify="left",
                 font=("Segoe UI", 8)).grid(row=16, column=0, columnspan=2,
                                            sticky="w", padx=10, pady=(0, 4))

        self.var_record = tk.BooleanVar(value=False)
        ttk.Checkbutton(p, text="Record data (log to CSV)", variable=self.var_record,
                        command=self._on_record).grid(row=17, column=0, columnspan=2,
                                                       sticky="w", **pad)
        self.lbl_rec = tk.Label(p, text="", fg="#777", font=("Segoe UI", 8), anchor="w")
        self.lbl_rec.grid(row=18, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))

    def _add_scale(self, p, label, attr, lo, hi, row, to_setting=None, from_setting=None):
        tk.Label(p, text=label).grid(row=row, column=0, sticky="w", padx=10)
        init = getattr(self.settings, attr)
        if from_setting:
            init = from_setting(init)
        var = tk.DoubleVar(value=init)

        def on_change(_=None):
            v = var.get()
            setattr(self.settings, attr, to_setting(v) if to_setting else int(round(v)))

        scale = ttk.Scale(p, from_=lo, to=hi, variable=var, command=on_change)
        scale.grid(row=row, column=1, sticky="we", padx=10, pady=2)
        scale.bind("<ButtonRelease-1>", lambda e: self.settings.save())
        self._scales[attr] = (var, from_setting)

    def _on_enabled(self):
        self.settings.enabled = self.var_enabled.get()
        if not self.settings.enabled:
            self.controller.release_all()
        self.settings.save()

    def _on_invert(self):
        self.settings.invert = self.var_invert.get()
        self.settings.save()

    def _on_look(self):
        self.settings.look_enabled = self.var_look.get()
        self.settings.save()

    def _on_calibrate(self):
        self.steering.start_calibration()

    def _on_reset_defaults(self):
        self.settings.reset_defaults()
        for attr, (var, from_setting) in self._scales.items():
            val = getattr(self.settings, attr)
            var.set(from_setting(val) if from_setting else val)
        self.var_invert.set(self.settings.invert)
        self.var_look.set(self.settings.look_enabled)
        self.steering.request_recenter()

    def _on_record(self):
        if self.var_record.get():
            base = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                    else os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(base, "data_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv")
            try:
                f = open(path, "w", encoding="utf-8")
                f.write("t,gx,gy,gz,ax,ay,az,steer,axisx,axisy,axisz\n")
                self._rec_t0 = time.perf_counter()
                self._rec_last = 0.0
                self._rec = f
                self.lbl_rec.config(text="Recording -> " + os.path.basename(path))
            except Exception as e:
                self.lbl_rec.config(text="Record failed: %s" % e)
                self.var_record.set(False)
        else:
            f, self._rec = self._rec, None
            if f:
                try:
                    f.close()
                except Exception:
                    pass
            self.lbl_rec.config(text="Saved.")

    def _tick(self):
        if self._connected:
            self.lbl_status.config(text=self._status_text, fg="#1a7f1a")
        else:
            self.lbl_status.config(text=self._status_text, fg="#c08000")
        if self.steering.calibrating:
            self.lbl_calib.config(text="Calibrating - turn the wheel LEFT <-> RIGHT...",
                                  fg="#c08000")
        elif self.settings.steer_axis:
            self.lbl_calib.config(text="Steering axis calibrated.", fg="#1a7f1a")
        else:
            self.lbl_calib.config(text="Not calibrated (turning auto-learns the axis).",
                                  fg="#777")
        v = max(-1.0, min(1.0, self.steering.value))
        x = 150 + v * 148
        self.canvas.coords(self._bar, min(150, x), 3, max(150, x), 21)
        st = self._last_state
        if st is not None:
            self.pb_gas["value"] = st.r2 * 100.0 / 255.0
            self.pb_brake["value"] = st.l2 * 100.0 / 255.0
        self.root.after(33, self._tick)

    def _on_close(self):
        self.manager.stop()
        f, self._rec = self._rec, None
        if f:
            try:
                f.close()
            except Exception:
                pass
        try:
            self.controller.release_all()
        except Exception:
            pass
        self.settings.save()
        self.root.destroy()


def _set_app_id():
    # Give the process its own taskbar identity so Windows uses our window icon
    # instead of grouping under pythonw.exe (which shows the Python icon).
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "AlexChurkin.TruckRemoteServerV2")
    except Exception:
        pass


def main():
    _set_app_id()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
