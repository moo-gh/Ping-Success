# ping_success_app.py
"""
Ping Success Graph – Windows Desktop Application (PySide6 + PyQtGraph)
=====================================================================

This version creates a dark-themed line graph showing ping success over time,
similar to the Starlink interface style.

Dependencies:   `pip install pyside6 pyqtgraph pythonping`
Python >= 3.9.
"""
from __future__ import annotations

import ipaddress
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
    QHBoxLayout,
)
import pyqtgraph as pg

# Configure PyQtGraph for better Windows compatibility
pg.setConfigOptions(antialias=True)
pg.setConfigOptions(useOpenGL=False)  # Disable OpenGL for better compatibility
pg.setConfigOptions(enableExperimental=False)

PING_INTERVAL = 1.0  # seconds
PACKETS_PER_INTERVAL = 5
HISTORY_SECONDS = 900  # 15-minute rolling window


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
                    pass  # treat errors as loss

            # Send 1 if all pings successful, 0 otherwise
            success = 1 if success_count == PACKETS_PER_INTERVAL else 0

            print(
                f"Ping {self.host}: {'SUCCESS' if success else 'FAILURE'}"
            )  # Debug output
            self.sample_ready.emit(success)
            self._stop.wait(PING_INTERVAL)

    def stop(self):
        self._stop.set()
        self.wait()


@dataclass
class TargetSeries:
    host: str
    history: Deque[int]
    line_item: pg.PlotDataItem
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

        # Plot widget with WHITE theme for testing
        self.plot = pg.PlotWidget(background="white")
        self.plot.setYRange(0, 100)
        self.plot.setXRange(0, 100)  # Start with smaller range, will adjust dynamically
        self.plot.setLabel("left", "")
        self.plot.setLabel("bottom", "")
        self.plot.showGrid(x=True, y=True, alpha=0.5)  # More visible grid

        # Test if plot widget is working at all
        print(f"Plot widget created: {self.plot}")
        print(f"Plot size: {self.plot.size()}")

        # Hide axes but keep the lines
        self.plot.getAxis("left").setStyle(showValues=False)
        self.plot.getAxis("bottom").setStyle(showValues=False)

        # Ensure the plot is properly configured for line display
        self.plot.setMouseEnabled(x=False, y=False)  # Disable mouse interaction
        self.plot.setMenuEnabled(False)  # Disable context menu

        # MINIMAL TEST: Just hardcoded numbers to eliminate any data issues
        print("Creating minimal test with hardcoded data...")

        # Test 1: Most basic line possible
        x_data = [0, 1, 2, 3, 4, 5]
        y_data = [10, 30, 50, 70, 90, 50]

        print(f"X data type: {type(x_data[0])}, values: {x_data}")
        print(f"Y data type: {type(y_data[0])}, values: {y_data}")

        basic_line = self.plot.getPlotItem().plot(
            x_data, y_data, pen=pg.mkPen(color="red", width=10)
        )
        print("Created basic line with hardcoded integers")

        # Test 2: Try with explicit float conversion
        x_float = [float(x) for x in x_data]
        y_float = [float(y) for y in y_data]

        float_line = self.plot.getPlotItem().plot(
            x_float, y_float, pen=pg.mkPen(color="green", width=10)
        )
        print("Created float line")

        # Test 3: Check PyQtGraph version
        print(
            f"PyQtGraph version: {pg.__version__ if hasattr(pg, '__version__') else 'unknown'}"
        )

        # Test 4: Force a repaint
        self.plot.repaint()
        self.plot.update()
        print("Forced plot repaint and update")

        layout.addWidget(self.plot)

        # Success percentage display
        self.percentage_label = QLabel("0.0%")
        self.percentage_label.setStyleSheet(
            "color: white; font-size: 24px; font-weight: bold;"
        )
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
            "8.8.8.8",  # Google DNS
        ]

    # ---------- internal helpers ----------
    def _add_series(self, host: str):
        # basic validation (allow hostnames too)
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass

        # TEMPORARILY DISABLE ping worker to focus on static line display
        print("Skipping ping worker creation for testing...")

        # Create a dummy TargetSeries without worker for now
        history: Deque[int] = deque([], maxlen=HISTORY_SECONDS)
        dummy_plot = self.plot.getPlotItem().plot(
            [0, 10, 20], [50, 60, 70], pen=pg.mkPen(color="white", width=5)
        )
        print(f"Added static ping line for {host}")

        # worker = PingWorker(host)
        # worker.sample_ready.connect(lambda success, h=history: self._on_sample(h, success))
        # worker.start()

        # Store the plot reference
        self.series.append(TargetSeries(host, history, dummy_plot, None))

    def _on_sample(self, history: Deque[int], success: int):
        history.append(success)

        # Calculate percentage: successful pings / total expected pings in 15 minutes
        successful_pings = sum(history)
        percentage = (successful_pings / HISTORY_SECONDS) * 100.0

        self.percentage_label.setText(f"{percentage:.1f}%")

    def _replot(self):
        for s in self.series:
            # Only plot if we have data
            if len(s.history) == 0:
                print("No history data yet")
                return

            print(
                f"History length: {len(s.history)}, data: {list(s.history)[-10:]}"
            )  # Show last 10 values

            # Create simple line data for testing
            y_data = []
            for i in range(len(s.history)):
                # Use the actual percentage but add some variation for visibility
                window_size = min(10, i + 1)
                start_idx = max(0, i - window_size + 1)
                window_data = list(s.history)[start_idx : i + 1]
                successful_in_window = sum(window_data)
                percentage = (successful_in_window / window_size) * 100.0

                # Add some variation to make line visible (remove this later)
                import random

                percentage += random.uniform(-5, 5)
                percentage = max(0, min(100, percentage))  # Keep in range

                y_data.append(percentage)

            # Scale x-axis to show progression from left to right
            x_data = list(range(len(y_data)))

            print(
                f"Plotting {len(x_data)} points, Y range: {min(y_data) if y_data else 0:.1f} to {max(y_data) if y_data else 0:.1f}"
            )

            # Update the plot data using setData method
            s.line_item.setData(x_data, y_data)

            print(f"Line updated with {len(x_data)} points using setData")

    def closeEvent(self, event):
        for s in self.series:
            if s.worker is not None:  # Check if worker exists
                s.worker.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    # Fix High DPI display issues on Windows
    import os

    if sys.platform == "win32":
        # Set environment variables for High DPI support
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "RoundPreferFloor"

    app = QApplication(sys.argv)

    # Additional High DPI configuration
    if hasattr(app, "setAttribute"):
        try:
            from PySide6.QtCore import Qt

            app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
            print("High DPI scaling enabled")
        except:
            print("Could not enable High DPI scaling")

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
