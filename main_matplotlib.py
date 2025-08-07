from __future__ import annotations

import sys
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, List

from pythonping import ping
from PySide6.QtGui import QPalette, QColor, QFont, QFontDatabase
from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
    QFrame,
    QTextEdit,
    QScrollArea,
    QGraphicsDropShadowEffect,
)

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Use non-interactive backend
plt.ioff()

# Configure better fonts for matplotlib
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = [
    "SF Pro Text",
    "SF Pro Display",
    "San Francisco",
    "Segoe UI",
    "Arial",
    "DejaVu Sans",
    "Liberation Sans",
    "sans-serif",
]
plt.rcParams["font.size"] = 10
plt.rcParams["axes.titlesize"] = 12
plt.rcParams["axes.labelsize"] = 11
plt.rcParams["xtick.labelsize"] = 9
plt.rcParams["ytick.labelsize"] = 9
plt.rcParams["legend.fontsize"] = 10
plt.rcParams["figure.titlesize"] = 14

PING_INTERVAL = 1.0  # seconds
PACKETS_PER_INTERVAL = 5
HISTORY_SECONDS = 450  # 15-minute rolling window (450 seconds = 7.5 minutes, but we'll scale to 15 minutes)


class PingWorker(QThread):
    sample_ready = Signal(int)
    log_message = Signal(str)

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
            message = f"[{timestamp}] Ping {self.host}: {status}"
            if not success:
                self.log_message.emit(message)
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
        self.setStyleSheet(
            """
            QFrame#gradientFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
                border-radius: 15px;
                border: 2px solid #4a90e2;
            }
        """
        )


class StatusCard(QFrame):
    """Beautiful status card with gradient and shadow effect"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusCard")
        self.setStyleSheet(
            """
            QFrame#statusCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2c3e50, stop:0.5 #34495e, stop:1 #2c3e50);
                border-radius: 12px;
                border: 1px solid #3498db;
                padding: 15px;
            }
        """
        )
        self.setMinimumHeight(140)


class ConsoleLogWidget(QFrame):
    """Console log widget with scrolling and message limiting"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("consoleFrame")
        self.setStyleSheet(
            """
            QFrame#consoleFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
                border-radius: 12px;
                border: 2px solid #3498db;
                padding: 10px;
            }
        """
        )
        self.setMinimumHeight(150)
        self.setMaximumHeight(150)

        # Layout for the console frame
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Console title
        title = QLabel("Console Logs")
        title.setStyleSheet(
            """
            color: #3498db; 
            font-size: 14px; 
            font-weight: 600; 
            font-family: 'Segoe UI', 'Arial', sans-serif;
            margin-bottom: 5px;
        """
        )
        layout.addWidget(title)

        # Text edit for console output
        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.4;
            }
            QScrollBar:vertical {
                background: #21262d;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #484f58;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6e7681;
            }
        """
        )
        layout.addWidget(self.console_text)

        # Message storage with 100 message limit
        self.messages = deque(maxlen=100)

    def add_message(self, message: str):
        """Add a message to the console log"""
        # Format failure messages with red background
        if "FAILURE" in message:
            formatted_message = f'<span style="background-color: #dc3545; color: white; padding: 2px 4px; border-radius: 3px;">{message}</span>'
        else:
            formatted_message = message

        self.messages.append(formatted_message)

        # Update the display with HTML formatting
        self.console_text.clear()
        self.console_text.setHtml("<br>".join(self.messages))

        # Auto-scroll to bottom
        scrollbar = self.console_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None, logger=None):
        # Create figure with modern dark background
        self.figure = Figure(figsize=(9, 5), facecolor="#1a1a2e")
        self.figure.patch.set_visible(False)
        super().__init__(self.figure)
        self.setParent(parent)
        self.logger = logger if logger else print

        # Create subplot with proper margins for labels and no frame
        self.ax = self.figure.add_axes([0.22, 0.15, 0.72, 0.75], facecolor="#1a1a2e")
        self.ax.patch.set_visible(False)
        self.ax.set_ylim(0, 100)
        self.ax.set_xlim(0, 15)

        # Enhanced styling with modern colors
        self.ax.grid(True, alpha=0.2, color="#3498db", linestyle="--", linewidth=0.5)
        self.ax.tick_params(
            colors="#ecf0f1",
            labelsize=10,
            top=False,
            right=False,
            left=True,
            bottom=True,
            length=0,
            width=0,
            pad=8,
        )

        # Remove borders and spines
        self.ax.set_frame_on(False)
        for key in ["top", "right", "bottom", "left"]:
            if key in self.ax.spines:
                self.ax.spines[key].set_visible(False)

        # Enhanced axis labels with better typography
        self.ax.set_xticks([0, 5, 10, 15])
        self.ax.set_xticklabels(
            ["0m", "5m", "10m", "15m"],
            color="#ecf0f1",
            fontsize=10,
            weight="600",
            fontfamily="Segoe UI",
        )
        self.ax.set_yticks([0, 25, 50, 75, 100])
        self.ax.set_yticklabels(
            ["0%", "25%", "50%", "75%", "100%"],
            color="#ecf0f1",
            fontsize=10,
            weight="600",
            fontfamily="Segoe UI",
        )

        # Enhanced axis labels
        self.ax.set_xlabel(
            "Time (minutes)",
            color="#3498db",
            fontsize=12,
            weight="600",
            fontfamily="Segoe UI",
        )
        self.ax.set_ylabel(
            "Success Rate (%)",
            color="#3498db",
            fontsize=12,
            weight="600",
            fontfamily="Segoe UI",
        )

        # Modern styling for the canvas
        self.setStyleSheet(
            """
            border: none; 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
            border-radius: 10px;
        """
        )

        # Initialize line with gradient effect
        (self.line,) = self.ax.plot(
            [],
            [],
            color="#00ff88",
            linewidth=1.5,
            alpha=0.8,
            solid_joinstyle="round",
            solid_capstyle="round",
            antialiased=True,
        )

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logger(f"[{timestamp}] Matplotlib widget created with modern styling")

    def update_line(self, x_data, y_data):
        """Update the line with new data"""
        # Convert data points to time scale (450 points = 15 minutes)
        if len(x_data) > 0:
            # Scale x_data to represent time in minutes (0 to 15 minutes)
            # Each data point represents 2 seconds (450 points * 2 seconds = 900 seconds = 15 minutes)
            time_scale = [i * 2.0 / 60.0 for i in x_data]  # Convert to minutes
            self.line.set_data(time_scale, y_data)

            # Set x-axis to show 0-15 minutes
            self.ax.set_xlim(0, 15)
        else:
            self.line.set_data([], [])

        self.draw()
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Commented out to reduce log noise - uncomment if needed for debugging
        # self.logger(f"[{timestamp}] Matplotlib line updated with {len(x_data)} points")


@dataclass
class TargetSeries:
    host: str
    history: Deque[int]
    worker: PingWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ping Success Monitor")
        self.setFixedSize(700, 700)  # Increased height to accommodate console
        self.setWindowFlags(
            Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        )

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
        title.setStyleSheet(
            """
            color: #ecf0f1; 
            font-size: 26px; 
            font-weight: 600; 
            font-family: 'SF Pro Display', 'SF Pro Text', 'San Francisco', 'Inter', 'Poppins', 'Montserrat', 'Segoe UI Variable', 'Segoe UI', 'Arial', sans-serif;
            text-align: center;
            letter-spacing: 0.5px;
        """
        )
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Real-time Network Connectivity")
        subtitle.setStyleSheet(
            """
            color: #3498db; 
            font-size: 15px; 
            font-weight: 400; 
            font-family: 'SF Pro Text', 'SF Pro Display', 'San Francisco', 'Inter', 'Poppins', 'Montserrat', 'Segoe UI Variable', 'Segoe UI', 'Arial', sans-serif;
            text-align: center;
            letter-spacing: 0.3px;
        """
        )
        subtitle.setAlignment(Qt.AlignCenter)

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        main_layout.addWidget(title_frame)

        # Matplotlib widget in a styled container
        plot_container = QFrame()
        plot_container.setObjectName("plotContainer")
        plot_container.setStyleSheet(
            """
            QFrame#plotContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
                border-radius: 15px;
                border: 2px solid #3498db;
                padding: 10px;
            }
        """
        )
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(10, 10, 10, 10)

        self.plot_widget = MatplotlibWidget(logger=self.log_message)
        plot_layout.addWidget(self.plot_widget)
        main_layout.addWidget(plot_container)

        # Enhanced status display with modern card design
        status_card = StatusCard()
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(25, 12, 25, 18)
        status_layout.setSpacing(10)

        # Time frame label with clearer contrast (placed above to avoid overlap)
        time_label = QLabel("Average in the last 15 minutes")
        time_label.setStyleSheet(
            """
            color: #ecf0f1; 
            font-size: 16px; 
            font-weight: 600; 
            font-family: 'SF Pro Text', 'SF Pro Display', 'San Francisco', 'Inter', 'Poppins', 'Montserrat', 'Segoe UI Variable', 'Segoe UI', 'Arial', sans-serif;
            text-align: center;
            letter-spacing: 0.3px;
        """
        )
        time_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(time_label, 0, Qt.AlignCenter)

        # Success percentage label (no green rectangle)
        self.percentage_label = QLabel("100%")
        self.percentage_label.setObjectName("percentageLabel")
        self.percentage_label.setStyleSheet(
            """
            QLabel#percentageLabel {
                color: #eafaf1; 
                font-size: 40px; 
                font-weight: 700; 
                font-family: 'SF Pro Display', 'SF Pro Text', 'San Francisco', 'Inter', 'Poppins', 'Montserrat', 'Segoe UI Variable', 'Segoe UI', 'Arial', sans-serif;
                text-align: center;
                letter-spacing: 0.5px;
                background-color: transparent;
            }
        """
        )
        self.percentage_label.setAlignment(Qt.AlignCenter)
        self.percentage_label.setMinimumHeight(56)
        self.percentage_label.setMinimumWidth(220)
        # Soft glow for readability
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(22)
        glow.setColor(QColor("#0b3d2e"))
        glow.setOffset(0, 2)
        self.percentage_label.setGraphicsEffect(glow)
        status_layout.addWidget(self.percentage_label, 0, Qt.AlignCenter)

        main_layout.addWidget(status_card)

        # Console log widget
        self.console_widget = ConsoleLogWidget()
        main_layout.addWidget(self.console_widget)

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

        # Initial console message
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message(f"[{timestamp}] Ping Success Monitor started")
        self.log_message(f"[{timestamp}] Monitoring interval: {PING_INTERVAL}s")
        self.log_message(f"[{timestamp}] Console logs limited to 100 messages")

        # Set initial percentage
        self.percentage_label.setText("0.0%")
        self.log_message(f"[{timestamp}] Initial percentage set to 0.0%")

    def log_message(self, message: str):
        """Log a message to both console output and the console widget"""
        print(message)
        if hasattr(self, "console_widget"):
            self.console_widget.add_message(message)

    @staticmethod
    def _default_hosts() -> List[str]:
        """Return the fixed list of hosts we monitor."""
        return [
            "8.8.8.8",  # Google DNS
        ]

    def _add_series(self, host: str):
        # Track successful pings (1 = success, 0 = failure) for last 15 minutes
        history: Deque[int] = deque([], maxlen=HISTORY_SECONDS)

        worker = PingWorker(host)
        # Use a more reliable signal connection
        worker.sample_ready.connect(lambda success: self._on_sample(history, success))
        worker.log_message.connect(
            self.log_message
        )  # Connect the signal to the main window's log_message method
        worker.start()

        self.series.append(TargetSeries(host, history, worker))
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message(f"[{timestamp}] Added ping series for {host}")

    def _on_sample(self, history: Deque[int], success: int):
        history.append(success)

        # Calculate percentage: successful pings / total samples collected
        if len(history) > 0:
            successful_pings = sum(history)
            percentage = (successful_pings / len(history)) * 100.0
        else:
            percentage = 0.0

        # Debug logging
        # timestamp = datetime.now().strftime("%H:%M:%S")
        # self.log_message(f"[{timestamp}] Sample received: success={success}, history_size={len(history)}, percentage={percentage:.1f}%")

        # Update the percentage label (formatted and without forced repaint to avoid flicker)
        formatted = self._format_percentage(percentage)
        if self.percentage_label.text() != formatted:
            self.percentage_label.setText(formatted)
        # self.log_message(f"[{timestamp}] Updated percentage label to {percentage:.1f}%")

    def _format_percentage(self, value: float) -> str:
        """Format percentage nicely: one decimal, but strip trailing .0."""
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text}%"

    def _replot(self):
        for s in self.series:
            if len(s.history) == 0:
                return

            # Create line data based on rolling window success rate
            y_data = []
            for i in range(len(s.history)):
                window_size = min(
                    HISTORY_SECONDS, i + 1
                )  # Use 15-minute rolling window
                start_idx = max(0, i - window_size + 1)
                window_data = list(s.history)[start_idx : i + 1]
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

    # Set application-wide font preferring San Francisco if available
    QFontDatabase.addApplicationFontFromData(b"")  # no-op, placeholder if packaged
    font = QFont("SF Pro Text", 10)
    font.setWeight(QFont.Weight.Normal)
    app.setFont(font)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
