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
from datetime import datetime
from typing import Deque, List

from pythonping import ping  # type: ignore
from PySide6.QtCore import QThread, Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPalette, QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
    QFrame,
)

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

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
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            status = "SUCCESS" if success else "FAILURE"
            if success:
                print(f"[{timestamp}] Ping {self.host}: {status}")
            else:
                # Red background for FAILURE messages
                print(f"\033[41m[{timestamp}] Ping {self.host}: {status}\033[0m")
            self.sample_ready.emit(success)
            self._stop.wait(PING_INTERVAL)

    def stop(self):
        self._stop.set()
        self.wait()


class GradientFrame(QFrame):
    """Custom frame with gradient background"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gradientFrame")
        self.setStyleSheet("""
            QFrame#gradientFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
                border-radius: 15px;
                border: 2px solid #4a90e2;
            }
        """)


class StatusCard(QFrame):
    """Beautiful status card with gradient and shadow effect"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusCard")
        self.setStyleSheet("""
            QFrame#statusCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2c3e50, stop:0.5 #34495e, stop:1 #2c3e50);
                border-radius: 12px;
                border: 1px solid #3498db;
                padding: 15px;
            }
        """)
        self.setMinimumHeight(80)


class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None):
        # Create figure with modern dark background
        self.figure = Figure(figsize=(9, 5), facecolor='#1a1a2e')
        self.figure.patch.set_visible(False)
        super().__init__(self.figure)
        self.setParent(parent)
        
        # Create subplot with proper margins for labels and no frame
        self.ax = self.figure.add_axes([0.22, 0.15, 0.72, 0.75], facecolor='#1a1a2e')
        self.ax.patch.set_visible(False)
        self.ax.set_ylim(0, 100)
        self.ax.set_xlim(0, 15)
        
        # Enhanced styling with modern colors
        self.ax.grid(True, alpha=0.2, color='#3498db', linestyle='--', linewidth=0.5)
        self.ax.tick_params(colors='#ecf0f1', labelsize=10, 
                           top=False, right=False, left=True, bottom=True,
                           length=0, width=0, pad=8)
        
        # Remove borders and spines
        self.ax.set_frame_on(False)
        for key in ['top', 'right', 'bottom', 'left']:
            if key in self.ax.spines:
                self.ax.spines[key].set_visible(False)
        
        # Enhanced axis labels with better typography
        self.ax.set_xticks([0, 5, 10, 15])
        self.ax.set_xticklabels(['0m', '5m', '10m', '15m'], color='#ecf0f1', fontsize=9, weight='bold')
        self.ax.set_yticks([0, 25, 50, 75, 100])
        self.ax.set_yticklabels(['0%', '25%', '50%', '75%', '100%'], color='#ecf0f1', fontsize=9, weight='bold')
        
        # Enhanced axis labels
        self.ax.set_xlabel('Time (minutes)', color='#3498db', fontsize=11, weight='bold')
        self.ax.set_ylabel('Success Rate (%)', color='#3498db', fontsize=11, weight='bold')
        
        # Modern styling for the canvas
        self.setStyleSheet("""
            border: none; 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
            border-radius: 10px;
        """)
        
        # Initialize line with gradient effect
        self.line, = self.ax.plot([], [], color='#00ff88', linewidth=3, alpha=0.8)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Matplotlib widget created with modern styling")

    def update_line(self, x_data, y_data):
        """Update the line with new data"""
        # Convert data points to time scale (15 minutes = 900 seconds)
        if len(x_data) > 0:
            # Scale x_data to represent time in minutes (0 to 15 minutes)
            time_scale = [i * PING_INTERVAL / 60.0 for i in x_data]  # Convert to minutes
            self.line.set_data(time_scale, y_data)
            
            # Set x-axis to show 0-15 minutes
            self.ax.set_xlim(0, 15)
        else:
            self.line.set_data([], [])
        
        self.draw()
        timestamp = datetime.now().strftime("%H:%M:%S")
        # print(f"[{timestamp}] Matplotlib line updated with {len(x_data)} points")


@dataclass
class TargetSeries:
    host: str
    history: Deque[int]
    worker: PingWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ping Success Monitor")
        self.setFixedSize(700, 500)
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)

        # Set window icon and properties
        # Skip icon for now to avoid compatibility issues
        pass

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        # Main gradient frame
        main_frame = GradientFrame()
        main_layout = QVBoxLayout(main_frame)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)

        # Enhanced title with modern typography
        title_frame = QFrame()
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5)

        title = QLabel("Ping Success Monitor")
        title.setStyleSheet("""
            color: #ecf0f1; 
            font-size: 24px; 
            font-weight: bold; 
            font-family: 'Segoe UI', Arial, sans-serif;
            text-align: center;
        """)
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Real-time Network Connectivity")
        subtitle.setStyleSheet("""
            color: #3498db; 
            font-size: 14px; 
            font-weight: normal; 
            font-family: 'Segoe UI', Arial, sans-serif;
            text-align: center;
        """)
        subtitle.setAlignment(Qt.AlignCenter)

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        main_layout.addWidget(title_frame)

        # Matplotlib widget in a styled container
        plot_container = QFrame()
        plot_container.setObjectName("plotContainer")
        plot_container.setStyleSheet("""
            QFrame#plotContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
                border-radius: 15px;
                border: 2px solid #3498db;
                padding: 10px;
            }
        """)
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(10, 10, 10, 10)

        self.plot_widget = MatplotlibWidget()
        plot_layout.addWidget(self.plot_widget)
        main_layout.addWidget(plot_container)

        # Enhanced status display with modern card design
        status_card = StatusCard()
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(20, 20, 20, 20)
        status_layout.setSpacing(10)

        # Success percentage with enhanced styling
        percentage_container = QFrame()
        percentage_container.setObjectName("percentageContainer")
        percentage_container.setStyleSheet("""
            QFrame#percentageContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #27ae60, stop:0.5 #2ecc71, stop:1 #27ae60);
                border-radius: 10px;
                border: 2px solid #00ff88;
            }
        """)
        percentage_layout = QVBoxLayout(percentage_container)
        percentage_layout.setContentsMargins(15, 10, 15, 10)

        self.percentage_label = QLabel("0.0%")
        self.percentage_label.setStyleSheet("""
            color: white; 
            font-size: 32px; 
            font-weight: bold; 
            font-family: 'Segoe UI', Arial, sans-serif;
            text-align: center;
        """)
        self.percentage_label.setAlignment(Qt.AlignCenter)
        percentage_layout.addWidget(self.percentage_label)
        status_layout.addWidget(percentage_container)
        
        # Time frame label with enhanced styling
        time_label = QLabel("Last 15 Minutes")
        time_label.setStyleSheet("""
            color: #bdc3c7; 
            font-size: 14px; 
            font-weight: normal; 
            font-family: 'Segoe UI', Arial, sans-serif;
            text-align: center;
        """)
        time_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(time_label)

        main_layout.addWidget(status_card)
        layout.addWidget(main_frame)

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
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Added ping series for {host}")

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
                window_size = min(HISTORY_SECONDS, i + 1)  # Use 15-minute rolling window
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

    # Enhanced dark theme with modern colors
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#1a1a2e"))
    palette.setColor(QPalette.WindowText, QColor("#ecf0f1"))
    palette.setColor(QPalette.Base, QColor("#16213e"))
    palette.setColor(QPalette.AlternateBase, QColor("#0f3460"))
    palette.setColor(QPalette.ToolTipBase, QColor("#2c3e50"))
    palette.setColor(QPalette.ToolTipText, QColor("#ecf0f1"))
    palette.setColor(QPalette.Text, QColor("#ecf0f1"))
    palette.setColor(QPalette.Button, QColor("#34495e"))
    palette.setColor(QPalette.ButtonText, QColor("#ecf0f1"))
    palette.setColor(QPalette.BrightText, QColor("#00ff88"))
    palette.setColor(QPalette.Link, QColor("#3498db"))
    palette.setColor(QPalette.Highlight, QColor("#3498db"))
    app.setPalette(palette)

    # Set application-wide font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    win = MainWindow()
    win.show()
    sys.exit(app.exec()) 