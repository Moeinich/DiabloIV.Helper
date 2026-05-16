from os import path
from pathlib import Path
from keyboard import add_hotkey
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QIcon, QPixmap, QIntValidator, QPainter, QPen, QBrush, QColor
from PyQt5.QtWidgets import (QApplication, QCheckBox, QDialog, QGridLayout, QLineEdit,
                              QGroupBox, QHBoxLayout, QLabel, QPushButton, QStyleFactory, QWidget)

from helper import image_helper, config_helper, logging_helper
from bot import bot_config
from pynput import mouse as pynput_mouse


class RegionSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.desktop().screenGeometry())
        self.corner1 = None
        self.corner2 = None
        self.is_first_click = True
        self.mouse_pos = QCursor.pos()
        self.mouse_tracking_timer = QTimer()
        self.mouse_tracking_timer.timeout.connect(self._update_mouse_pos)
        self.mouse_tracking_timer.start(16)
        self.listener = None

    def _update_mouse_pos(self):
        self.mouse_pos = QCursor.pos()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.corner1 and self.corner2:
            rect = QRect(self.corner1, self.corner2).normalized()
            painter.setPen(QPen(Qt.white, 2))
            painter.setBrush(QBrush(QColor(0, 255, 0, 80)))
            painter.drawRect(rect)
            label = f"{rect.width()}x{rect.height()}"
            painter.setPen(QPen(Qt.white, 1))
            painter.drawText(rect.center(), label)
        elif self.corner1:
            painter.setPen(QPen(Qt.yellow, 2))
            painter.setBrush(QBrush(QColor(255, 255, 0, 150)))
            painter.drawEllipse(self.corner1, 12, 12)
            painter.drawText(self.corner1 + QPoint(15, 5), "Click 2nd corner")
        else:
            painter.setPen(QPen(Qt.red, 2))
            painter.drawText(self.mouse_pos + QPoint(15, 5), "Click 1st corner")
            painter.drawEllipse(self.mouse_pos, 6, 6)

    def mousePressEvent(self, event):
        pass

    def run(self):
        self.listener = pynput_mouse.Listener(
            on_click=lambda x, y, button, pressed: self._on_click(x, y, button, pressed) if pressed else None)
        self.listener.start()
        self.show()
        self.setFocus()
        self.raise_()
        self.activateWindow()
        while self.isVisible():
            QApplication.processEvents()
        if self.listener.is_alive():
            self.listener.stop()
        self.listener.join(timeout=1)

    def _on_click(self, x, y, button, pressed):
        if pressed:
            pos = QPoint(x, y)
            if self.is_first_click:
                self.corner1 = pos
                self.is_first_click = False
                self.update()
            else:
                self.corner2 = pos
                if self.listener.is_alive():
                    self.listener.stop()
                self.close()


class MouseClickEvent:
    def __init__(self, pos):
        self._pos = pos

    def pos(self):
        return self._pos


class PointSelector:
    def run(self):
        self._result = None
        self._click_pos = None

        def on_click(x, y, button, pressed):
            if pressed:
                self._click_pos = QPoint(x, y)
                return False

        listener = pynput_mouse.Listener(on_click=on_click)
        listener.start()
        listener.join()

        if self._click_pos:
            self._result = self._click_pos
        return self._result


class LiveVisualizerWidget(QWidget):
    STATE_COLORS = {
        'ready': QColor(0, 255, 0, 80),
        'ready_border': QColor(0, 255, 0),
        'cd': QColor(255, 0, 0, 80),
        'cd_border': QColor(255, 0, 0),
        'disabled': QColor(128, 128, 128, 80),
        'disabled_border': QColor(128, 128, 128),
        'casting': QColor(0, 122, 255, 120),
        'casting_border': QColor(0, 122, 255),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setGeometry(QApplication.desktop().screenGeometry())
        self._skill_states = {}
        self._cached_cls_cfg = {}
        self._cached_hp_vals = None
        self._cast_tracker = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._update_states)
        self._refresh_timer.start(100)

    def _get_cast_tracker(self):
        if self._cast_tracker is None:
            from bot.rotation import _cast_tracker
            self._cast_tracker = _cast_tracker
        return self._cast_tracker

    def _update_states(self):
        try:
            from bot.rotation import get_skill_states
            self._skill_states = get_skill_states()
            self._cached_hp_vals = config_helper.get_shared_config('hp_pixel', (608, 980, [95, 10, 15]))
            current_class = config_helper.get_shared_config('class', 'Paladin')
            self._cached_cls_cfg = config_helper.get_class_config(current_class)
        except Exception as ex:
            logging_helper.log_debug(f"LiveVisualizer._update_states error: {ex}")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        hp_vals = self._cached_hp_vals
        if hp_vals and len(hp_vals) >= 2:
            hx, hy = hp_vals[0], hp_vals[1]
            hp_colors = hp_vals[2] if len(hp_vals) > 2 and isinstance(hp_vals[2], list) else [[95, 10, 15]]
            if hp_colors and isinstance(hp_colors[0], (int, float)):
                hp_colors = [hp_colors]
            hp_ratio = 0.5
            for c in hp_colors:
                if len(c) >= 3 and image_helper.pixel_matches_color(hx, hy, c[0], c[1], c[2], 45):
                    hp_ratio = 1.0
                    break
            hp_color = QColor(int(255 * (1 - hp_ratio)), int(255 * hp_ratio), 0)
            self._draw_crosshair(painter, hx, hy, hp_color, f"HP {int(hp_ratio*100)}%")

        label_map = {
            'skill1': 'S1', 'skill2': 'S2', 'skill3': 'S3',
            'skill4': 'S4', 'skill5': 'S5', 'skill6': 'S6', 'pot': 'POT', 'evade': 'EVADE'
        }

        for key in ['skill1', 'skill2', 'skill3', 'skill4', 'skill5', 'skill6', 'pot', 'evade']:
            pos = self._cached_cls_cfg.get(f'{key}_pos')
            if not pos or len(pos) < 4:
                continue

            x, y, w, h = pos[0], pos[1], pos[2], pos[3]
            state = self._skill_states.get(key, 'cd')

            cast_tracker = self._get_cast_tracker()
            if cast_tracker and cast_tracker.is_flashing(key):
                state = 'casting'

            fill_color = self.STATE_COLORS.get(state, self.STATE_COLORS['cd'])
            border_color = getattr(self.STATE_COLORS, f'{state}_border', QColor(255, 0, 0))

            painter.setPen(QPen(border_color, 3))
            painter.setBrush(QBrush(fill_color))
            painter.drawRect(x, y, w, h)
            self._draw_label(painter, f"{label_map.get(key, key.upper())}:{state.upper()}", x, y - 15, border_color)

        self._draw_legend(painter)

    def _draw_legend(self, painter):
        legend_x = 20
        legend_y = 20
        line_h = 18
        items = [
            ('READY', self.STATE_COLORS['ready_border']),
            ('CD', self.STATE_COLORS['cd_border']),
            ('DISABLED', self.STATE_COLORS['disabled_border']),
            ('CASTING', self.STATE_COLORS['casting_border']),
        ]
        painter.setPen(QPen(Qt.white, 1))
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        for i, (label, color) in enumerate(items):
            y = legend_y + i * line_h
            painter.setPen(QPen(color, 2))
            painter.drawRect(legend_x, y, 14, 14)
            painter.setPen(QPen(Qt.white, 1))
            painter.drawText(legend_x + 20, y + 12, label)

    def _draw_crosshair(self, painter, x, y, color, label):
        painter.setPen(QPen(color, 2))
        painter.drawLine(x - 8, y, x + 8, y)
        painter.drawLine(x, y - 8, x, y + 8)
        painter.drawEllipse(x - 4, y - 4, 8, 8)
        self._draw_label(painter, label, x + 8, y - 15, color)

    def _draw_label(self, painter, text, x, y, color):
        painter.setPen(QPen(Qt.white, 1))
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        bg_rect = QRect(x - 2, y - 14, painter.fontMetrics().width(text) + 6, 16)
        painter.drawRect(bg_rect)
        painter.drawText(x + 2, y, text)

    def mousePressEvent(self, event):
        self.close()


class ConfigVisualizer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.desktop().screenGeometry())
        self.cfg = config_helper.read_config()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.update)
        self._refresh_timer.start(100)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        hp_vals = config_helper.get_shared_config('hp_pixel', (608, 980, [95, 10, 15]))
        if hp_vals and len(hp_vals) >= 2:
            hx, hy = hp_vals[0], hp_vals[1]
            painter.setPen(QPen(QColor(255, 255, 0), 2))
            painter.drawLine(hx - 8, hy, hx + 8, hy)
            painter.drawLine(hx, hy - 8, hx, hy + 8)
            self._draw_label(painter, "HP PIXEL", hx + 10, hy - 10, QColor(255, 255, 0))

        skill_labels = {
            'skill1': 'Skill 1', 'skill2': 'Skill 2', 'skill3': 'Skill 3',
            'skill4': 'Skill 4', 'skill5': 'Skill 5', 'skill6': 'Skill 6',
            'pot': 'Potion', 'evade': 'Evade'
        }
        current_class = config_helper.get_shared_config('class', 'Paladin')
        cls_cfg = config_helper.get_class_config(current_class)
        for key, label in skill_labels.items():
            vals = cls_cfg.get(f'{key}_pos')
            if vals and len(vals) >= 4:
                x, y, w, h = vals[0], vals[1], vals[2], vals[3]
                painter.setPen(QPen(QColor(255, 0, 255), 2))
                painter.drawRect(x, y, w, h)
                self._draw_label(painter, label, x + 5, y + h // 2, QColor(255, 0, 255))

    def _draw_label(self, painter, text, x, y, color):
        painter.setPen(QPen(Qt.white, 1))
        painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        bg_rect = QRect(x - 2, y - 14, painter.fontMetrics().width(text) + 6, 16)
        painter.drawRect(bg_rect)
        painter.drawText(x + 2, y, text)

    def mousePressEvent(self, event):
        self.close()

    def run(self):
        self.show()
        self.grabMouse()
        self.setFocus()
        self.raise_()
        self.activateWindow()
        while self.isVisible():
            QApplication.processEvents()
        self.releaseMouse()


class Toolbox(QDialog):
    def __init__(self, parent=None):
        super(Toolbox, self).__init__(parent)
        self.running = False
        self.cfg = config_helper.read_config()
        self.name = self.cfg.get('apptitle', 'notepad')
        self._live_viz = None

        try:
            self.setWindowIcon(QIcon('.\\assets\\layout\\mmorpg_helper.ico'))
            self.pixmap = QPixmap('.\\assets\\layout\\mmorpg_helper_background.png')
        except Exception as e:
            logging_helper.log_error(f"Error loading resources: {e}")
            self.pixmap = QPixmap()

        QApplication.setStyle(QStyleFactory.create('Fusion'))
        self.setWindowTitle(self.name)
        self.setGeometry(700, 300, 600, 520)
        self.setMinimumSize(600, 520)

        self.label = QLabel(self)
        self.label.setPixmap(self.pixmap)
        self.label.resize(self.pixmap.width(), self.pixmap.height())

        add_hotkey('end', lambda: self.on_press('exit'))

        self.createConfigBox()
        self.load_config_to_fields()

        mainLayout = QGridLayout()
        mainLayout.addWidget(self.configBox, 0, 0)
        self.setLayout(mainLayout)

    def on_press(self, key):
        if key == 'exit':
            self.exit_app()
        else:
            logging_helper.log_error(f"Unknown key: {key}")

    def exit_app(self):
        logging_helper.log_info("Exiting application")
        QApplication.quit()

    def createConfigBox(self):
        self.configBox = QGroupBox('Game Config')
        self.configBox.setStyleSheet('QGroupBox:title {color: rgb(0,255,0);}')
        layout = QGridLayout()

        common_style = 'background:rgb(204,153,51);'
        label_style = 'color: rgb(0,255,0);'

        self.cfg = config_helper.read_config()

        layout.addWidget(QLabel('HP Detection:'), 0, 0)
        layout.addWidget(self._make_hp_row(common_style, label_style), 1, 0, 1, 4)

        layout.addWidget(QLabel('Skills & Utility:'), 2, 0)
        layout.addWidget(self._make_skill_row('skill1', 'q', (801, 45), 'Skill 1', common_style, label_style), 3, 0, 1, 4)
        layout.addWidget(self._make_skill_row('skill2', 'w', (710, 45), 'Skill 2', common_style, label_style), 4, 0, 1, 4)
        layout.addWidget(self._make_skill_row('skill3', 'e', (619, 45), 'Skill 3', common_style, label_style), 5, 0, 1, 4)
        layout.addWidget(self._make_skill_row('skill4', 'r', (528, 45), 'Skill 4', common_style, label_style), 6, 0, 1, 4)
        layout.addWidget(self._make_skill_row('skill5', 'leftclick', (890, 45), 'Skill 5 (LMouse)', common_style, label_style), 7, 0, 1, 4)
        layout.addWidget(self._make_skill_row('skill6', 'rightclick', (980, 45), 'Skill 6 (RMouse)', common_style, label_style), 8, 0, 1, 4)
        layout.addWidget(self._make_skill_row('pot', '2', (437, 45), 'Potion', common_style, label_style), 9, 0, 1, 4)
        layout.addWidget(self._make_skill_row('evade', 'space', (346, 45), 'Evade', common_style, label_style), 10, 0, 1, 4)

        layout.addWidget(QLabel('Rotation Hotkey:'), 13, 0)
        self._hotkey_btn = QPushButton(str(self.cfg.get('rotation_hotkey', 'f6')))
        self._hotkey_btn.setStyleSheet('background:rgb(204,153,51); color: #e0e0e0; padding: 2px 8px;')
        self._hotkey_btn.setFixedSize(120, 24)
        self._hotkey_btn.setObjectName('rotation_hotkey_btn')
        self._hotkey_btn.setToolTip('Click to capture a key or mouse button')
        self._hotkey_btn.clicked.connect(self._capture_hotkey)
        layout.addWidget(self._hotkey_btn, 13, 1)

        loadBtn = QPushButton('LOAD FROM CONFIG')
        loadBtn.clicked.connect(self.load_config_to_fields)
        saveBtn = QPushButton('SAVE TO CONFIG')
        saveBtn.clicked.connect(self.save_fields_to_config)
        vizBtn = QPushButton('VISUALIZE')
        vizBtn.clicked.connect(self.visualize_config)

        self.liveVizCheck = QCheckBox('Live Visualize')
        self.liveVizCheck.setStyleSheet('color: rgb(0,255,0);')
        self.liveVizCheck.stateChanged.connect(self.on_live_viz_toggled)

        layout.addWidget(loadBtn, 14, 0)
        layout.addWidget(saveBtn, 14, 1)
        layout.addWidget(vizBtn, 14, 2)
        layout.addWidget(self.liveVizCheck, 14, 3)

        self.configBox.setLayout(layout)

    def on_live_viz_toggled(self, state):
        if state == Qt.Checked:
            if not hasattr(self, '_live_viz') or not self._live_viz:
                self._live_viz = LiveVisualizerWidget()
            self._live_viz.show()
        else:
            if hasattr(self, '_live_viz') and self._live_viz:
                self._live_viz.close()

    def _make_coord_row(self, args, idx):
        key, default, label_text, style, lbl_style = args
        container = QWidget()
        layout = QHBoxLayout()

        lbl = QLabel(label_text)
        lbl.setStyleSheet(lbl_style)

        vals = self.cfg.get(key, default)
        x, y, w, h = vals if len(vals) == 4 else default

        x_ed = QLineEdit(str(x))
        x_ed.setStyleSheet(style)
        x_ed.setFixedSize(50, 20)
        x_ed.setValidator(QIntValidator())
        x_ed.setObjectName(f'coord_{idx}_x')

        y_ed = QLineEdit(str(y))
        y_ed.setStyleSheet(style)
        y_ed.setFixedSize(50, 20)
        y_ed.setValidator(QIntValidator())
        y_ed.setObjectName(f'coord_{idx}_y')

        w_ed = QLineEdit(str(w))
        w_ed.setStyleSheet(style)
        w_ed.setFixedSize(50, 20)
        w_ed.setValidator(QIntValidator())
        w_ed.setObjectName(f'coord_{idx}_w')

        h_ed = QLineEdit(str(h))
        h_ed.setStyleSheet(style)
        h_ed.setFixedSize(50, 20)
        h_ed.setValidator(QIntValidator())
        h_ed.setObjectName(f'coord_{idx}_h')

        setBtn = QPushButton('SET')
        setBtn.setStyleSheet('background:rgb(0,180,0); color:white;')
        setBtn.setFixedSize(40, 20)
        setBtn.key = key
        setBtn.idx = idx
        setBtn.clicked.connect(self.select_region)

        layout.addWidget(lbl)
        layout.addWidget(x_ed)
        layout.addWidget(y_ed)
        layout.addWidget(w_ed)
        layout.addWidget(h_ed)
        layout.addWidget(setBtn)
        layout.addStretch(1)
        container.setLayout(layout)
        return container

    def _make_hp_row(self, style, lbl_style):
        container = QWidget()
        layout = QHBoxLayout()

        lbl = QLabel('HP Pixel:')
        lbl.setStyleSheet(lbl_style)

        hp_vals = self.cfg.get('hp_pixel', (608, 980, [95, 10, 15]))
        x, y = hp_vals[0], hp_vals[1]
        colors = hp_vals[2] if len(hp_vals) > 2 and isinstance(hp_vals[2], list) else [95, 10, 15]
        if isinstance(colors[0], (int, float)):
            colors = [colors]

        x_ed = QLineEdit(str(x))
        x_ed.setStyleSheet(style)
        x_ed.setFixedSize(50, 20)
        x_ed.setValidator(QIntValidator())
        x_ed.setObjectName('hp_x')

        y_ed = QLineEdit(str(y))
        y_ed.setStyleSheet(style)
        y_ed.setFixedSize(50, 20)
        y_ed.setValidator(QIntValidator())
        y_ed.setObjectName('hp_y')

        r_ed = QLineEdit(str(colors[0][0]))
        r_ed.setStyleSheet(style)
        r_ed.setFixedSize(30, 20)
        r_ed.setValidator(QIntValidator())
        r_ed.setObjectName('hp_r')

        g_ed = QLineEdit(str(colors[0][1]))
        g_ed.setStyleSheet(style)
        g_ed.setFixedSize(30, 20)
        g_ed.setValidator(QIntValidator())
        g_ed.setObjectName('hp_g')

        b_ed = QLineEdit(str(colors[0][2]))
        b_ed.setStyleSheet(style)
        b_ed.setFixedSize(30, 20)
        b_ed.setValidator(QIntValidator())
        b_ed.setObjectName('hp_b')

        setBtn = QPushButton('SET HP')
        setBtn.setStyleSheet('background:rgb(180,0,0); color:white;')
        setBtn.setFixedSize(60, 20)
        setBtn.clicked.connect(self.select_hp_pixel)

        layout.addWidget(lbl)
        layout.addWidget(x_ed)
        layout.addWidget(y_ed)
        layout.addWidget(r_ed)
        layout.addWidget(g_ed)
        layout.addWidget(b_ed)
        layout.addWidget(setBtn)
        layout.addStretch(1)
        container.setLayout(layout)
        return container

    def _capture_hotkey(self):
        self._hotkey_btn.setText('Press a key or mouse button...')
        self._hotkey_btn.setStyleSheet('background:rgb(0,120,200); color: white; padding: 2px 8px;')
        self._hotkey_captured = None

        from pynput import keyboard as pk, mouse as pm

        def on_key_press(key):
            try:
                if hasattr(key, 'char') and key.char:
                    name = key.char
                elif hasattr(key, 'name'):
                    name = key.name
                else:
                    name = str(key).replace('Key.', '')
            except Exception:
                name = str(key)
            self._hotkey_captured = name
            return False

        def on_mouse_click(x, y, button, pressed):
            if pressed:
                btn_map = {'left': 'mouse1', 'right': 'mouse2', 'middle': 'mouse3', 'x1': 'x', 'x2': 'x2'}
                self._hotkey_captured = btn_map.get(button.name, button.name)
                return False

        kb_listener = pk.Listener(on_press=on_key_press, on_release=lambda k: False if self._hotkey_captured else True)
        ms_listener = pm.Listener(on_click=on_mouse_click)

        kb_listener.start()
        ms_listener.start()

        while self._hotkey_captured is None:
            QApplication.processEvents()

        kb_listener.stop()
        ms_listener.stop()
        kb_listener.join(timeout=1)
        ms_listener.join(timeout=1)

        captured = self._hotkey_captured
        self._hotkey_btn.setText(captured)
        self._hotkey_btn.setStyleSheet('background:rgb(204,153,51); color: #e0e0e0; padding: 2px 8px;')
        logging_helper.log_info(f'Captured hotkey: {captured}')

    def select_hp_pixel(self):
        selector = PointSelector()
        result = selector.run()
        if result:
            cx, cy = result.x(), result.y()
            self._find_and_set('hp_x', str(cx))
            self._find_and_set('hp_y', str(cy))
            logging_helper.log_info(f"Selected HP pixel at {cx},{cy}")

    def _make_skill_row(self, key, default_key, pos_default, label_text, style, lbl_style):
        container = QWidget()
        layout = QHBoxLayout()

        cb = QCheckBox()
        cb.setStyleSheet('QCheckBox {color: rgb(0,255,0);}')
        cb.setObjectName(f'skill_{key}_enabled')
        cb.setChecked(self.cfg.get(f'{key}_enabled', True))

        lbl = QLabel(label_text)
        lbl.setStyleSheet(lbl_style)
        lbl.setFixedSize(80, 20)

        key_ed = QLineEdit(str(self.cfg.get(key, default_key)))
        key_ed.setStyleSheet(style)
        key_ed.setFixedSize(60, 20)
        key_ed.setObjectName(f'skill_{key}_key')

        vals = self.cfg.get(f'{key}_pos', pos_default)
        x, y, w, h = vals if len(vals) >= 4 else (*pos_default, 60, 60)

        x_ed = QLineEdit(str(x))
        x_ed.setStyleSheet(style)
        x_ed.setFixedSize(40, 20)
        x_ed.setValidator(QIntValidator())
        x_ed.setObjectName(f'skill_{key}_x')

        y_ed = QLineEdit(str(y))
        y_ed.setStyleSheet(style)
        y_ed.setFixedSize(40, 20)
        y_ed.setValidator(QIntValidator())
        y_ed.setObjectName(f'skill_{key}_y')

        w_ed = QLineEdit(str(w))
        w_ed.setStyleSheet(style)
        w_ed.setFixedSize(30, 20)
        w_ed.setValidator(QIntValidator())
        w_ed.setObjectName(f'skill_{key}_w')

        h_ed = QLineEdit(str(h))
        h_ed.setStyleSheet(style)
        h_ed.setFixedSize(30, 20)
        h_ed.setValidator(QIntValidator())
        h_ed.setObjectName(f'skill_{key}_h')

        setBtn = QPushButton('SET')
        setBtn.setStyleSheet('background:rgb(0,180,0); color:white;')
        setBtn.setFixedSize(40, 20)
        setBtn.key = key
        setBtn.clicked.connect(self.select_skill_pos)

        layout.addWidget(cb)
        layout.addWidget(lbl)
        layout.addWidget(QLabel('K:'))
        layout.addWidget(key_ed)
        layout.addWidget(QLabel('X:'))
        layout.addWidget(x_ed)
        layout.addWidget(QLabel('Y:'))
        layout.addWidget(y_ed)
        layout.addWidget(QLabel('W:'))
        layout.addWidget(w_ed)
        layout.addWidget(QLabel('H:'))
        layout.addWidget(h_ed)
        layout.addWidget(setBtn)
        layout.addStretch(1)
        container.setLayout(layout)
        return container

    def select_hp_pixel(self):
        selector = PointSelector()
        result = selector.run()
        if result:
            cx, cy = result.x(), result.y()
            self._find_and_set('hp_x', str(cx))
            self._find_and_set('hp_y', str(cy))
            logging_helper.log_info(f"Selected HP pixel at {cx},{cy}")

    def select_skill_pos(self):
        sender = self.sender()
        key = sender.key
        selector = RegionSelector()
        selector.run()
        if selector.corner1 and selector.corner2:
            rect = QRect(selector.corner1, selector.corner2).normalized()
            self._find_and_set(f'skill_{key}_x', str(rect.left()))
            self._find_and_set(f'skill_{key}_y', str(rect.top()))
            self._find_and_set(f'skill_{key}_w', str(rect.width()))
            self._find_and_set(f'skill_{key}_h', str(rect.height()))
            logging_helper.log_info(f"Selected skill {key} region at {rect.left()},{rect.top()} {rect.width()}x{rect.height()}")

    def visualize_config(self):
        self.cfg = config_helper.read_config()
        viz = ConfigVisualizer()
        viz.run()

    def load_config_to_fields(self):
        current_class = config_helper.get_current_class()

        hp_vals = config_helper.get_shared_config('hp_pixel', (608, 980, [95, 10, 15]))
        x, y = hp_vals[0], hp_vals[1]
        colors = hp_vals[2] if len(hp_vals) > 2 and isinstance(hp_vals[2], list) else [95, 10, 15]
        if isinstance(colors[0], (int, float)):
            colors = [colors]
        self._find_and_set('hp_x', str(x))
        self._find_and_set('hp_y', str(y))
        self._find_and_set('hp_r', str(colors[0][0]))
        self._find_and_set('hp_g', str(colors[0][1]))
        self._find_and_set('hp_b', str(colors[0][2]))

        cls_cfg = config_helper.get_class_config(current_class)
        for key, default in [
            ('skill1', 'q'),
            ('skill2', 'w'),
            ('skill3', 'e'),
            ('skill4', 'r'),
            ('skill5', 'leftclick'),
            ('skill6', 'rightclick'),
            ('pot', '2'),
            ('evade', 'space'),
        ]:
            val = cls_cfg.get(key, default)
            self._find_and_set(f'skill_{key}_key', str(val))
            cb = self.configBox.findChild(QCheckBox, f'skill_{key}_enabled')
            if cb:
                cb.setChecked(cls_cfg.get(f'{key}_enabled', True))

        for key, default in [
            ('skill1', (801, 45, 60, 60)),
            ('skill2', (710, 45, 60, 60)),
            ('skill3', (619, 45, 60, 60)),
            ('skill4', (528, 45, 60, 60)),
            ('skill5', (890, 45, 60, 60)),
            ('skill6', (980, 45, 60, 60)),
            ('pot', (437, 45, 60, 60)),
            ('evade', (346, 45, 60, 60)),
        ]:
            vals = cls_cfg.get(f'{key}_pos', default)
            self._find_and_set(f'skill_{key}_x', str(vals[0]))
            self._find_and_set(f'skill_{key}_y', str(vals[1]))
            self._find_and_set(f'skill_{key}_w', str(vals[2] if len(vals) >= 3 else 60))
            self._find_and_set(f'skill_{key}_h', str(vals[3] if len(vals) >= 4 else 60))

        hotkey_val = config_helper.get_shared_config('rotation_hotkey', 'f6')
        if hasattr(self, '_hotkey_btn'):
            self._hotkey_btn.setText(str(hotkey_val))

        logging_helper.log_info(f'Loaded config values into fields for class: {current_class}')

    def save_fields_to_config(self):
        current_class = config_helper.get_current_class()

        def get_val(obj_name):
            le = self.configBox.findChild(QLineEdit, obj_name)
            return int(le.text()) if le and le.text() else None

        hp_r = get_val('hp_r') or 95
        hp_g = get_val('hp_g') or 10
        hp_b = get_val('hp_b') or 15
        config_helper.save_shared_config('hp_pixel', [get_val('hp_x') or 608, get_val('hp_y') or 980, [hp_r, hp_g, hp_b]])

        def get_key_val(obj_name):
            le = self.configBox.findChild(QLineEdit, obj_name)
            return le.text() if le and le.text() else None

        for key in ['skill1', 'skill2', 'skill3', 'skill4', 'skill5', 'skill6', 'pot', 'evade']:
            config_helper.save_class_config(current_class, key, get_key_val(f'skill_{key}_key'))
            config_helper.save_class_config(current_class, f'{key}_pos', [
                get_val(f'skill_{key}_x') or 0,
                get_val(f'skill_{key}_y') or 0,
                get_val(f'skill_{key}_w') or 60,
                get_val(f'skill_{key}_h') or 60
            ])
            cb = self.configBox.findChild(QCheckBox, f'skill_{key}_enabled')
            config_helper.save_class_config(current_class, f'{key}_enabled', cb.isChecked() if cb else True)

        if hasattr(self, '_hotkey_btn') and self._hotkey_btn.text():
            config_helper.save_shared_config('rotation_hotkey', self._hotkey_btn.text())

        logging_helper.log_info(f'Saved config values from fields for class: {current_class}')
        bot_config.init()

    def _find_and_set(self, object_name, value):
        le = self.configBox.findChild(QLineEdit, object_name)
        if le:
            le.setText(value)
