from __future__ import annotations

import os
import sys
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, List

import requests
from pythonping import ping
from PySide6.QtGui import (
    QPalette,
    QColor,
    QFont,
    QIcon,
    QAction,
    QPixmap,
    QPainter,
    QPen,
    QBrush,
    QFontMetrics,
)
from PySide6.QtCore import QThread, Qt, QTimer, Signal, QEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
    QFrame,
    QTextEdit,
    QScrollArea,
    QSystemTrayIcon,
    QMenu,
    QStyle,
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


def resource_path(relative_path: str) -> str:
    """Return absolute path to resource, works for dev and for PyInstaller bundles."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


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
        # Slightly higher DPI for crisper, more consistent line rendering
        self.figure.set_dpi(120)
        self.figure.patch.set_visible(False)
        super().__init__(self.figure)
        self.setParent(parent)
        self.logger = logger if logger else print

        # Create subplot with symmetric margins so the graph is centered
        left_right_margin = 0.12
        bottom_margin = 0.15
        top_margin = 0.12
        axes_width = 1.0 - 2 * left_right_margin
        axes_height = 1.0 - bottom_margin - top_margin
        self.ax = self.figure.add_axes(
            [left_right_margin, bottom_margin, axes_width, axes_height],
            facecolor="#1a1a2e",
        )
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
            fontsize=8,
            weight="600",
            fontfamily="Segoe UI",
        )
        self.ax.set_yticks([0, 25, 50, 75, 100])
        self.ax.set_yticklabels(
            ["0%", "25%", "50%", "75%", "100%"],
            color="#ecf0f1",
            fontsize=8,
            weight="600",
            fontfamily="Segoe UI",
        )

        # Enhanced axis labels
        self.ax.set_xlabel(
            "Time (minutes)",
            color="#3498db",
            fontsize=8,
            weight="600",
            fontfamily="Segoe UI",
        )
        self.ax.set_ylabel(
            "Success Rate (%)",
            color="#3498db",
            fontsize=8,
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
            linewidth=1.6,
            alpha=1.0,
            solid_joinstyle="miter",
            solid_capstyle="butt",
            antialiased=True,
        )

        # Overlay average text positioned just above the graph area
        axes_box = self.ax.get_position()  # in figure coordinates
        center_x = axes_box.x0 + (axes_box.width / 2.0)
        top_y = min(0.99, axes_box.y1 + 0.02)  # small margin above the axes
        self.avg_text = self.figure.text(
            center_x,
            top_y,
            "",
            transform=self.figure.transFigure,
            ha="center",
            va="bottom",
            color="#eafaf1",
            fontsize=10,
            weight="700",
            fontfamily="Segoe UI",
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

    def set_average_text(self, text: str):
        """Update the overlay average percentage text on the graph."""
        if hasattr(self, "avg_text"):
            self.avg_text.set_text(f"Average: {text}")
            self.draw_idle()


@dataclass
class TargetSeries:
    host: str
    history: Deque[int]
    worker: PingWorker


class MainWindow(QMainWindow):
    # Signal for thread-safe IP updates
    ip_updated = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ping Success Monitor")
        self.setFixedSize(700, 700)  # Increased height to accommodate console
        self.setWindowFlags(
            Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        )
        self._is_exiting = False
        self._last_percentage_text = "0%"
        self._public_ip = "Fetching..."
        
        # Connect the IP update signal
        self.ip_updated.connect(self._on_ip_updated)

        # Set window icon and properties
        try:
            app_icon = QIcon(resource_path("icon.png"))
            self.setWindowIcon(app_icon)
        except Exception:
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

        # Enhanced title area (subtitle only)
        title_frame = QFrame()
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5)

        subtitle = QLabel("Real-time Network Connectivity Monitor")
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

        # Public IP refresh timer (every 5 minutes)
        self.ip_timer = QTimer(self)
        self.ip_timer.timeout.connect(self._fetch_public_ip)
        self.ip_timer.start(300000)  # 300000 ms = 5 minutes

        # Fetch IP immediately on startup (in background)
        QTimer.singleShot(1000, self._fetch_public_ip)

        # Initial console message
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message(f"[{timestamp}] Ping Success Monitor started")
        self.log_message(f"[{timestamp}] Monitoring interval: {PING_INTERVAL}s")
        self.log_message(f"[{timestamp}] Console logs limited to 100 messages")

        # Set initial overlay percentage on the plot
        self._last_percentage_text = "0%"
        self.plot_widget.set_average_text(self._last_percentage_text)

        # System tray setup
        self._setup_tray()

    def _setup_tray(self):
        """Create system tray icon with context menu and actions."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.log_message("[Tray] System tray not available on this system")
            return

        # Create initial number icon based on current percentage
        icon = self._make_percentage_tray_icon(self._last_percentage_text)

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Ping Success Monitor")

        tray_menu = QMenu(self)
        # Readout action (disabled label to show average in menu)
        self.tray_avg_action = QAction("Avg: 0%", self)
        self.tray_avg_action.setEnabled(False)
        tray_menu.addAction(self.tray_avg_action)
        tray_menu.addSeparator()
        action_show = QAction("Show Window", self)
        action_show.triggered.connect(self.show_and_raise)
        action_hide = QAction("Hide Window", self)
        action_hide.triggered.connect(self.hide)
        action_quit = QAction("Quit", self)
        action_quit.triggered.connect(self.quit_app)

        tray_menu.addAction(action_show)
        tray_menu.addAction(action_hide)
        tray_menu.addSeparator()
        tray_menu.addAction(action_quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

        # Initialize tray text from current percentage
        self._refresh_tray_percentage_text(self._last_percentage_text)

    def _on_tray_activated(self, reason):
        """Toggle window on tray icon activation (double click)."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger or reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show_and_raise()

    def show_and_raise(self):
        """Show the window and bring it to the foreground."""
        self.show()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self):
        """Hide the window and notify via tray balloon message."""
        self.hide()
        if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            try:
                self.tray_icon.showMessage(
                    "Ping Success Monitor",
                    f"Average: {self._last_percentage_text}\nRunning in the system tray. Right-click for options.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )
            except Exception:
                pass

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

        # Update the overlay text on the plot and tray percentage
        formatted = self._format_percentage(percentage)
        if self._last_percentage_text != formatted:
            self.plot_widget.set_average_text(formatted)
            self._refresh_tray_percentage_text(formatted)
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

    def _fetch_public_ip(self):
        """Fetch public IP address from echoip.ir or fallback services."""
        def fetch_in_thread():
            services = [
                "https://echoip.ir",
                "https://api.ipify.org",
                "https://icanhazip.com",
                "https://ifconfig.me/ip"
            ]
            
            for service in services:
                try:
                    response = requests.get(service, timeout=3)
                    if response.status_code == 200:
                        ip = response.text.strip()
                        # Emit signal to update UI in main thread
                        self.ip_updated.emit(ip)
                        return
                except Exception:
                    continue
            
            # If all services fail
            self.ip_updated.emit("N/A")
        
        # Run in a separate thread to avoid blocking the UI
        thread = threading.Thread(target=fetch_in_thread, daemon=True)
        thread.start()

    def _on_ip_updated(self, ip: str):
        """Handle IP update in the main thread (slot for ip_updated signal)."""
        self._public_ip = ip
        self._update_tray_tooltip()
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message(f"[{timestamp}] Public IP updated: {ip}")

    def _update_tray_tooltip(self):
        """Update the tray tooltip with current data."""
        if hasattr(self, "tray_icon") and self.tray_icon is not None:
            try:
                tooltip = f"Ping Success Monitor\nAverage: {self._last_percentage_text}\nPublic IP: {self._public_ip}"
                self.tray_icon.setToolTip(tooltip)
            except Exception:
                pass

    def _refresh_tray_percentage_text(self, text: str):
        """Update tray tooltip and menu label with current average percent."""
        self._last_percentage_text = text
        if hasattr(self, "tray_icon") and self.tray_icon is not None:
            try:
                self._update_tray_tooltip()
                # Update tray icon graphic with numeric text
                self.tray_icon.setIcon(self._make_percentage_tray_icon(text))
            except Exception:
                pass
        if hasattr(self, "tray_avg_action") and self.tray_avg_action is not None:
            self.tray_avg_action.setText(f"Avg: {text}")

    def _make_percentage_tray_icon(self, text: str) -> QIcon:
        """Render a small icon showing the integer percentage as text."""
        # Extract integer value and choose background color
        display_text = text.replace("%", "").split(".")[0]
        try:
            value = int(display_text)
        except Exception:
            value = 0
        # Color thresholds: green >=95, yellow >=80, red otherwise
        if value >= 95:
            bg_color = QColor("#0f5132")  # dark green
            fg_color = QColor("#d1e7dd")  # light text
            border_color = QColor("#198754")
        elif value >= 80:
            bg_color = QColor("#664d03")  # dark yellow
            fg_color = QColor("#fff3cd")
            border_color = QColor("#ffc107")
        else:
            bg_color = QColor("#58151c")  # dark red
            fg_color = QColor("#f8d7da")
            border_color = QColor("#dc3545")

        size = 32
        padding = 2
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Background circle
        brush = QBrush(bg_color)
        pen = QPen(border_color)
        pen.setWidth(2)
        painter.setBrush(brush)
        painter.setPen(pen)
        painter.drawEllipse(padding, padding, size - 2 * padding, size - 2 * padding)

        # Text: try to fit width by reducing font size
        font = QFont(self.font())
        font.setBold(True)
        font_size = 14
        fm: QFontMetrics
        while font_size >= 8:
            font.setPointSize(font_size)
            fm = QFontMetrics(font)
            if fm.horizontalAdvance(display_text) <= size - 8:
                break
            font_size -= 1
        painter.setFont(font)
        painter.setPen(QPen(fg_color))
        painter.drawText(0, 0, size, size, Qt.AlignCenter, display_text)

        painter.end()
        return QIcon(pix)

    def closeEvent(self, event):
        # Close should fully exit
        for s in self.series:
            s.worker.stop()
        super().closeEvent(event)

    def quit_app(self):
        """Quit from tray action (ensures workers stopped)."""
        self._is_exiting = True
        if hasattr(self, "tray_icon"):
            try:
                self.tray_icon.hide()
            except Exception:
                pass
        self.close()

    def changeEvent(self, event):
        """Minimize should go to tray."""
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                # Defer hide to avoid animation glitches
                QTimer.singleShot(0, self.hide_to_tray)
        super().changeEvent(event)


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

    # Set application-wide font (Qt will fall back to available system fonts)
    font = QFont("SF Pro Text", 10)
    font.setWeight(QFont.Weight.Normal)
    app.setFont(font)

    # Application icon (taskbar/alt-tab)
    try:
        app.setWindowIcon(QIcon(resource_path("icon.png")))
    except Exception:
        pass

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
