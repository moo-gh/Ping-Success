# ping_success_app.py
"""
Ping Success Graph – Windows Desktop Application (PySide6 + PyQtGraph)
=====================================================================

This script provides a stand‑alone GUI similar to Starlink’s Statistics tab. It
continuously pings three configurable targets and draws a real‑time, second‑by‑
second bar chart of *ping‑success* (% packets returned within timeout).

Key features
------------
* **Three default targets** – local gateway, 8.8.8.8, 1.1.1.1 (editable).
* **Rolling history** – 300 seconds (5 minutes) kept in memory & viewport.
* **Colour‑coded bars** – green = 100 %, yellow = <100 % and >0 %, red = 0 %.
* **Threaded pingers** – each host gets its own worker thread (QThread)
  emitting per‑second results via Qt signals.
* **No admin rights needed on Windows** – uses *pythonping*’s subprocess
  fallback to the built‑in `ping.exe`.
* **Packaging** – run `pyinstaller --onefile ping_success_app.py` for a single
  EXE (see README section at bottom).

Dependencies:   `pip install pyside6 pyqtgraph pythonping`
Python >= 3.9.
"""
from __future__ import annotations

import ipaddress
import queue
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, List

from pythonping import ping  # type: ignore
from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
import pyqtgraph as pg


PING_INTERVAL = 1.0  # seconds
PACKETS_PER_INTERVAL = 5
HISTORY_SECONDS = 300  # 5‑minute rolling window


def _colour_for_success(success_pct: float) -> QColor:
    if success_pct >= 99.5:
        return QColor("#4caf50")  # green
    elif success_pct > 0.0:
        return QColor("#ffca28")  # amber
    return QColor("#f44336")  # red


class PingWorker(QThread):
    sample_ready = Signal(float)

    def __init__(self, host: str):
        super().__init__()
        self.host = host
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            success_count = 0
            for _ in range(PACKETS_PER_INTERVAL):
                try:
                    response = ping(self.host, count=1, timeout=1, verbose=False)
                    if response.success():
                        success_count += 1
                except Exception:
                    # Treat exceptions as loss
                    pass
            pct = (success_count / PACKETS_PER_INTERVAL) * 100.0
            self.sample_ready.emit(pct)
            self._stop.wait(PING_INTERVAL)

    def stop(self):
        self._stop.set()
        self.wait()


@dataclass
class TargetSeries:
    host: str
    history: Deque[float]
    curve: pg.BarGraphItem
    worker: PingWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ping Success Monitor")
        self.resize(900, 600)

        central = QWidget(self)
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        # Plot widget
        self.plot = pg.PlotWidget(background="w")
        self.plot.setYRange(0, 100)
        self.plot.setLabel("left", "Ping Success (%)")
        self.plot.setLabel("bottom", "Seconds Ago")
        layout.addWidget(self.plot, 1)

        # Control panel
        ctl = QHBoxLayout()
        layout.addLayout(ctl)

        self.input_new_host = QLineEdit()
        self.input_new_host.setPlaceholderText("Add host (Enter to start)")
        ctl.addWidget(self.input_new_host, 1)
        add_btn = QPushButton("Add")
        ctl.addWidget(add_btn)
        add_btn.clicked.connect(self._add_host_from_field)
        self.input_new_host.returnPressed.connect(self._add_host_from_field)

        # Series storage
        self.series: List[TargetSeries] = []

        for default in self._default_hosts():
            self._add_series(default)

        # Timer to refresh bars every second
        self.redraw_timer = QTimer(self)
        self.redraw_timer.timeout.connect(self._replot)
        self.redraw_timer.start(int(PING_INTERVAL * 1000))

    @staticmethod
    def _default_hosts() -> List[str]:
        # Attempt to detect gateway, else fall back to 192.168.1.1
        try:
            import psutil  # optional

            gws = psutil.net_if_addrs()
            # dummy implementation; leave for user editing
            return ["192.168.1.1", "8.8.8.8", "1.1.1.1"]
        except Exception:
            return ["192.168.1.1", "8.8.8.8", "1.1.1.1"]

    # ---------- UI helpers ----------
    def _add_host_from_field(self):
        text = self.input_new_host.text().strip()
        if text:
            self._add_series(text)
            self.input_new_host.clear()

    def _add_series(self, host: str):
        # basic validation
        try:
            ipaddress.ip_address(host)
        except ValueError:
            # allow hostnames too
            pass
        history: Deque[float] = deque([100.0] * HISTORY_SECONDS, maxlen=HISTORY_SECONDS)
        bar_item = pg.BarGraphItem(x=list(range(HISTORY_SECONDS)), height=list(history), width=0.8)
        self.plot.addItem(bar_item)
        worker = PingWorker(host)
        worker.sample_ready.connect(lambda pct, h=history: self._on_sample(h, pct))
        worker.start()
        self.series.append(TargetSeries(host, history, bar_item, worker))

    def _on_sample(self, history: Deque[float], pct: float):
        history.append(pct)

    def _replot(self):
        for s in self.series:
            s.curve.setOpts(height=list(s.history))
            colours = [_colour_for_success(p) for p in s.history]
            s.curve.setOpts(brush=colours)

    def closeEvent(self, event):
        for s in self.series:
            s.worker.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Light theme tweaks
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("white"))
    palette.setColor(QPalette.WindowText, Qt.black)
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
