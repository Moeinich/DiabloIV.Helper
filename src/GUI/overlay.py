from threading import Thread, Lock
from time import sleep
import ctypes
from keyboard import add_hotkey, remove_hotkey
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem, QPainter, QPen, QBrush, QColor, QFont
from PyQt5.QtWidgets import (QApplication, QComboBox, QMainWindow,
                             QGroupBox, QPushButton, QHBoxLayout, QVBoxLayout, QLabel, QStyleFactory, QWidget)

from pathlib import Path

from helper import config_helper, logging_helper, process_helper
from bot import rotation, bot_config
from GUI import toolbox
from GUI.styles import OVERLAY_STYLESHEET
from pynput import mouse as pynput_mouse

WINDOW_X = 660
WINDOW_Y = 0
WINDOW_WIDTH = 820
WINDOW_HEIGHT = 40
EXPANDED_HEIGHT = 760
ICON_PATH = str(Path(__file__).resolve().parents[1] / "assets" / "layout" / "mmorpg_helper.ico")

class Overlay(QMainWindow):
    def __init__(self, parent=None):
        super(Overlay, self).__init__(parent)
        self.running = False
        self._lock = Lock()
        self.pause_req = False
        self._log_handler = None
        self._hotkey_str = None
        self._mouse_listener = None
        self._live_viz = None
        self._toolbox_expanded = False
        self.name = config_helper.get_shared_config('apptitle', 'notepad')
        self.proc = process_helper.ProcessHelper()

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowIcon(QIcon(ICON_PATH))
        QApplication.setStyle(QStyleFactory.create('Fusion'))
        self.setWindowTitle(self.name)
        self.setGeometry(WINDOW_X, WINDOW_Y, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setFixedWidth(WINDOW_WIDTH)
        self.setFixedHeight(WINDOW_HEIGHT)
        self.setStyleSheet(OVERLAY_STYLESHEET)

        visible_window = QWidget(self)
        visible_window.setStyleSheet(OVERLAY_STYLESHEET)

        self.createDropdownBox()
        self.createStartBox()
        self.createToolBox()

        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(8, 4, 8, 4)
        bar_row.setSpacing(8)
        bar_row.addWidget(self.dropdownBox)
        bar_row.addWidget(self.startBox)
        bar_row.addStretch(1)
        bar_row.addWidget(self.toolBox)

        exitButton = QPushButton("EXIT")
        exitButton.clicked.connect(self._quit_app)
        bar_row.addWidget(exitButton)

        self._toolbox_panel = toolbox.Toolbox()
        self._toolbox_panel.setVisible(False)

        mainLayout = QVBoxLayout()
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)
        mainLayout.addLayout(bar_row)
        mainLayout.addWidget(self._toolbox_panel, 1)
        self.setCentralWidget(visible_window)
        visible_window.setLayout(mainLayout)

        self._register_hotkey()

        add_hotkey('end', lambda: self.on_press('exit'))
        add_hotkey('del', lambda: self.on_press('pause'))
        add_hotkey('capslock', lambda: self.on_press('pause'))

    def _register_hotkey(self):
        self._unregister_hotkey()
        self._hotkey_str = config_helper.get_shared_config('rotation_hotkey', 'f6')
        hk = self._hotkey_str
        mouse_keys = {'mouse1': pynput_mouse.Button.left, 'mouse2': pynput_mouse.Button.right,
                       'mouse3': pynput_mouse.Button.middle, 'x': pynput_mouse.Button.x1,
                       'x2': pynput_mouse.Button.x2, 'x1': pynput_mouse.Button.x1}
        if hk in mouse_keys:
            btn = mouse_keys[hk]
            self._mouse_listener = pynput_mouse.Listener(
                on_click=lambda x, y, button, pressed: self._on_mouse_hotkey(button, pressed, btn))
            self._mouse_listener.start()
        else:
            add_hotkey(hk, self.toggle_rotation)

    def _unregister_hotkey(self):
        if self._mouse_listener is not None:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None
        if self._hotkey_str:
            try:
                remove_hotkey(self._hotkey_str)
            except Exception:
                pass

    def _on_mouse_hotkey(self, button, pressed, target):
        if pressed and button == target:
            self.toggle_rotation()

    def update_class(self, item, value=None):
        logging_helper.log_info(f'Preset {item}: {value}')
        if item == 'class':
            config_helper.save_shared_config(item, value)
        else:
            config_helper.save_config(item, value)

    def passCurrentText(self):
        self.update_class('class', self.ComboBox.currentText())
        bot_config.init()

    def get_class(self):
        class_array = ['Druid', 'Spiritborn', 'Barbarian', 'Necromancer', 'Sorceress', 'Rogue', 'Warlock', 'Paladin']
        for class_var in class_array:
            item = QStandardItem(class_var)
            self.model.appendRow(item)
        saved_class = config_helper.get_shared_config('class', '')
        if saved_class:
            idx = class_array.index(saved_class) if saved_class in class_array else 0
            self.ComboBox.setCurrentIndex(idx)

    def createDropdownBox(self):
        self.dropdownBox = QGroupBox()
        self.dropdownBox.setStyleSheet("QGroupBox { border: none; background: transparent; }")
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.model = QStandardItemModel()
        self.ComboBox = QComboBox()
        self.ComboBox.setModel(self.model)

        self.get_class()
        self.ComboBox.activated.connect(self.passCurrentText)

        layout.addWidget(self.ComboBox)
        self.dropdownBox.setLayout(layout)

    def _quit_app(self):
        self.close()
        QApplication.quit()

    def closeEvent(self, event):
        self.stop_rotation()
        self._unregister_hotkey()
        root_logger = logging_helper.logger
        if self._log_handler:
            root_logger.removeHandler(self._log_handler)
            self._log_handler = None
        event.accept()

    def createStartBox(self):
        self.startBox = QGroupBox()
        self.startBox.setStyleSheet("QGroupBox { border: none; background: transparent; }")
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.toggleButton = QPushButton("START")
        self.toggleButton.clicked.connect(self.toggle_rotation)

        self.statusLabel = QLabel("OFF")
        self.statusLabel.setStyleSheet('color: #ff4444; font-weight: bold; font-size: 12px;')

        layout.addWidget(self.toggleButton)
        layout.addWidget(self.statusLabel)
        self.startBox.setLayout(layout)

    def createToolBox(self):
        self.toolBox = QGroupBox()
        self.toolBox.setStyleSheet("QGroupBox { border: none; background: transparent; }")
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        toggleToolButton = QPushButton("TOOLBOX")
        toggleToolButton.clicked.connect(self._toggle_toolbox)

        self.liveVizButton = QPushButton("LIVE")
        self.liveVizButton.setCheckable(True)
        self.liveVizButton.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 60, 230);
                color: #e0e0e0;
                border: 1px solid rgba(80, 80, 100, 150);
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: rgba(0, 180, 80, 220);
                color: white;
            }
        """)
        self.liveVizButton.clicked.connect(self.toggle_live_visualizer)

        layout.addWidget(toggleToolButton)
        layout.addWidget(self.liveVizButton)
        self.toolBox.setLayout(layout)

    def on_press(self, key):
        if key == 'exit':
            logging_helper.log_info('_EXIT')
            self.stop_rotation()
        elif key == 'pause':
            self.set_pause(not self.should_pause())
            if self.should_pause():
                logging_helper.log_info('_PAUSE')
            else:
                logging_helper.log_info('_RUN')

    def _is_d4_focused(self):
        try:
            fg = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(fg) + 1
            buf = ctypes.create_unicode_buffer(length)
            ctypes.windll.user32.GetWindowTextW(fg, buf, length)
            return 'diablo' in buf.value.lower()
        except Exception:
            return False

    def toggle_rotation(self):
        if self.running:
            self.stop_rotation()
            self.toggleButton.setText("START")
            self.statusLabel.setText("OFF")
            self.statusLabel.setStyleSheet('color: #ff4444; font-weight: bold; font-size: 13px;')
            logging_helper.log_info('Rotation stopped')
        else:
            if not self._is_d4_focused():
                logging_helper.log_info('Cannot start: Diablo IV is not focused')
                return
            self.start_rotation()
            self.toggleButton.setText("STOP")
            self.statusLabel.setText("ON")
            self.statusLabel.setStyleSheet('color: #44ff44; font-weight: bold; font-size: 13px;')
            logging_helper.log_info('Rotation started (hotkey: %s)' % self._hotkey_str)

    def start_rotation(self):
        if not hasattr(self, 'rotation_thread') or not self.rotation_thread.is_alive():
            bot_config.init()
            self.rotation_thread = Thread(target=self._rotation_loop, daemon=True)
            self.rotation_thread.start()

    def stop_rotation(self):
        self.running = False
        if hasattr(self, 'rotation_thread') and self.rotation_thread.is_alive():
            self.rotation_thread.join(timeout=2)
        rotation.release_held_key()

    def _rotation_loop(self):
        self.proc.set_foreground_window()
        self.running = True

        while self.running:
            while self.should_pause():
                sleep(0.25)
            rotation.rotation()
            sleep(0.1)

        logging_helper.log_info("Rotation thread ended")

    def should_pause(self):
        with self._lock:
            return self.pause_req

    def set_pause(self, pause):
        with self._lock:
            self.pause_req = pause

    def _toggle_toolbox(self):
        self._toolbox_expanded = not self._toolbox_expanded
        if self._toolbox_expanded:
            self._toolbox_panel.setVisible(True)
            self.setFixedHeight(EXPANDED_HEIGHT)
        else:
            self._toolbox_panel.setVisible(False)
            self.setFixedHeight(WINDOW_HEIGHT)

    def toggle_live_visualizer(self, checked):
        if checked:
            try:
                if self._live_viz is not None:
                    self._live_viz.show()
                    return
            except RuntimeError:
                self._live_viz = None
            self._live_viz = toolbox.LiveVisualizerWidget()
            self._live_viz.show()
        else:
            if self._live_viz is not None:
                try:
                    self._live_viz.close()
                except RuntimeError:
                    pass
                self._live_viz = None
