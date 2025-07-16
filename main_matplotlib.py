"""
Ping Success Graph – Windows Desktop Application (PySide6 + Matplotlib)
=====================================================================

This version uses matplotlib instead of PyQtGraph for better compatibility
and line rendering on Windows systems.

Dependencies:   `pip install pyside6 matplotlib pythonping`
Python >= 3.9.
"""
from __future__ import annotations

import sys
import threading
from collections import deque
from dataclasses import dataclass
from typing import Deque, List

from pythonping import ping  # type: ignore
from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
)

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.style as mplstyle
import numpy as np
from scipy.interpolate import make_interp_spline

# Use non-interactive backend
plt.ioff()

PING_INTERVAL = 1.0  # seconds
PACKETS_PER_INTERVAL = 5
HISTORY_SECONDS = 900  # 15-minute rolling window


class PingWorker(QThread):
    sample_ready = Signal(int)

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
                    pass  # treat errors as loss
            
            # Send 1 if all pings successful, 0 otherwise
            success = 1 if success_count == PACKETS_PER_INTERVAL else 0
            
            print(f"Ping {self.host}: {'SUCCESS' if success else 'FAILURE'}")
            self.sample_ready.emit(success)
            self._stop.wait(PING_INTERVAL)

    def stop(self):
        self._stop.set()
        self.wait()


class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None):
        # Create figure with dark background
        self.figure = Figure(figsize=(8, 4), facecolor='#2a2a2a')
        super().__init__(self.figure)
        self.setParent(parent)
        
        # Create subplot
        self.ax = self.figure.add_subplot(111, facecolor='#2a2a2a')
        self.ax.set_ylim(0, 100)
        self.ax.set_xlim(0, 100)
        
        # Style the plot
        self.ax.grid(True, alpha=0.3, color='white')
        self.ax.tick_params(colors='white')
        
        # Remove frame/box borders for cleaner look
        for spine in self.ax.spines.values():
            spine.set_visible(False)
        
        # Hide axis labels
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        
        # Initialize line
        self.line, = self.ax.plot([], [], color='white', linewidth=2)
        
        # Tight layout
        self.figure.tight_layout()
        
        print("Matplotlib widget created with white line")

    def update_line(self, x_data, y_data):
        """Update the line with new data"""
        if len(x_data) < 3:
            # Not enough points for smoothing
            self.line.set_data(x_data, y_data)
        else:
            try:
                # Create smooth curve using spline interpolation
                x_smooth = np.linspace(min(x_data), max(x_data), len(x_data) * 3)
                spl = make_interp_spline(x_data, y_data, k=min(3, len(x_data)-1))
                y_smooth = spl(x_smooth)
                self.line.set_data(x_smooth, y_smooth)
            except:
                # Fallback to original data if smoothing fails
                self.line.set_data(x_data, y_data)
        
        # Adjust axis ranges
        if len(x_data) > 0:
            self.ax.set_xlim(0, max(100, len(x_data) + 10))
        
        self.draw()
        print(f"Matplotlib line updated with {len(x_data)} points")


@dataclass
class TargetSeries:
    host: str
    history: Deque[int]
    worker: PingWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ping Success Monitor")
        self.resize(400, 300)

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Ping success")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Matplotlib widget
        self.plot_widget = MatplotlibWidget()
        layout.addWidget(self.plot_widget)

        # Success percentage display
        self.percentage_label = QLabel("0.0%")
        self.percentage_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        layout.addWidget(self.percentage_label)
        
        # Time frame label
        time_label = QLabel("last 15 minutes")
        time_label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(time_label)

        # Internal storage
        self.series: List[TargetSeries] = []

        # Create default host series
        for host in self._default_hosts():
            self._add_series(host)

        # Refresh timer
        self.redraw_timer = QTimer(self)
        self.redraw_timer.timeout.connect(self._replot)
        self.redraw_timer.start(int(PING_INTERVAL * 1000))

    @staticmethod
    def _default_hosts() -> List[str]:
        """Return the fixed list of hosts we monitor."""
        return [
            "8.8.8.8",        # Google DNS
        ]

    def _add_series(self, host: str):
        # Track successful pings (1 = success, 0 = failure) for last 15 minutes
        history: Deque[int] = deque([], maxlen=HISTORY_SECONDS)

        worker = PingWorker(host)
        worker.sample_ready.connect(lambda success, h=history: self._on_sample(h, success))
        worker.start()

        self.series.append(TargetSeries(host, history, worker))
        print(f"Added ping series for {host}")

    def _on_sample(self, history: Deque[int], success: int):
        history.append(success)
        
        # Calculate percentage: successful pings / total expected pings in 15 minutes
        successful_pings = sum(history)
        percentage = (successful_pings / HISTORY_SECONDS) * 100.0
            
        self.percentage_label.setText(f"{percentage:.1f}%")

    def _replot(self):
        for s in self.series:
            if len(s.history) == 0:
                return
                
            # Create line data based on rolling window success rate
            y_data = []
            for i in range(len(s.history)):
                window_size = min(60, i + 1)  # Use 60-second rolling window
                start_idx = max(0, i - window_size + 1)
                window_data = list(s.history)[start_idx:i+1]
                successful_in_window = sum(window_data)
                percentage = (successful_in_window / window_size) * 100.0
                
                y_data.append(percentage)
            
            x_data = list(range(len(y_data)))
            
            # Update matplotlib line
            self.plot_widget.update_line(x_data, y_data)

    def closeEvent(self, event):
        for s in self.series:
            s.worker.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Dark theme
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#2a2a2a"))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor("#2a2a2a"))
    palette.setColor(QPalette.AlternateBase, QColor("#2a2a2a"))
    palette.setColor(QPalette.ToolTipBase, QColor("#2a2a2a"))
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor("#2a2a2a"))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.white)
    palette.setColor(QPalette.Link, QColor("#42a5f5"))
    palette.setColor(QPalette.Highlight, QColor("#42a5f5"))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec()) 