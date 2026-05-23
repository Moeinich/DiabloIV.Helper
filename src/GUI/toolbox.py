from pathlib import Path
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer
from PyQt5.QtGui import QIcon, QPainter, QPen, QBrush, QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QStyleFactory, QTabWidget,
    QVBoxLayout, QWidget,
)

from helper import image_helper, config_helper, logging_helper
from bot import bot_config
from GUI.styles import TOOLBOX_STYLESHEET
from GUI.selectors import RectDragSelector, CircleDragSelector


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
        self.setGeometry(QApplication.primaryScreen().geometry())
        self._skill_states = {}
        self._cached_cls_cfg = {}
        self._cached_shared = {}
        self._cast_tracker = None
        self._last_config_read = 0.0
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._update_states)
        self._refresh_timer.start(200)

    def _get_cast_tracker(self):
        if self._cast_tracker is None:
            from bot.rotation import _cast_tracker
            self._cast_tracker = _cast_tracker
        return self._cast_tracker

    def _update_states(self):
        try:
            from bot.rotation import get_skill_states
            rotation_states = get_skill_states()

            from bot import bot_config
            c = bot_config.get()
            if c is None:
                bot_config.init()
                c = bot_config.get()

            import time as _time
            now = _time.time()
            if now - self._last_config_read >= 2.0:
                self._last_config_read = now
                shared = {}
                for k in ('hp_orb_center', 'hp_orb_radius', 'hp_orb_full_color', 'hp_orb_dark_color', 'hp_orb_tolerance',
                          'resource_orb_center', 'resource_orb_radius', 'resource_orb_full_color', 'resource_orb_dark_color', 'resource_orb_tolerance'):
                    shared[k] = config_helper.get_shared_config(k)
                self._cached_shared = shared
                current_class = config_helper.get_current_class()
                self._cached_cls_cfg = config_helper.get_class_config(current_class)

            if c is not None:
                from helper import image_helper
                debug_parts = []
                for key in config_helper.SKILL_SLOTS:
                    if not c.is_skill_enabled(key):
                        self._skill_states[key] = {'state': 'disabled', 'mode': ''}
                        debug_parts.append(f"{key}: disabled")
                        continue
                    if key in rotation_states and rotation_states[key].get('state') == 'casting':
                        self._skill_states[key] = rotation_states[key]
                        debug_parts.append(f"{key}: casting")
                        continue
                    cal = c.skill_calibration(key)
                    state = image_helper.classify_skill_state(cal)
                    self._skill_states[key] = {'state': state, 'mode': rotation_states.get(key, {}).get('mode', '')}
                    if cal and 'pixel1_x' in cal:
                        b1 = image_helper.read_pixel_brightness(cal['pixel1_x'], cal['pixel1_y'])
                        b2 = image_helper.read_pixel_brightness(cal['pixel2_x'], cal['pixel2_y'])
                        debug_parts.append(f"{key}: {state} (b1={b1:.0f} b2={b2:.0f})")
                    else:
                        debug_parts.append(f"{key}: {state} (no cal)")
                if debug_parts:
                    print("[SKILL] " + " | ".join(debug_parts))
            else:
                self._skill_states = rotation_states
        except Exception as ex:
            logging_helper.log_debug(f"LiveVisualizer._update_states error: {ex}")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        shared = self._cached_shared
        hp_center = shared.get('hp_orb_center')
        hp_radius = shared.get('hp_orb_radius') or 0
        hp_full_color = shared.get('hp_orb_full_color')
        hp_dark_color = shared.get('hp_orb_dark_color')
        hp_tolerance = shared.get('hp_orb_tolerance') or 45
        if hp_center and hp_radius > 0 and hp_full_color:
            cx, cy = hp_center if isinstance(hp_center, (list, tuple)) else (hp_center[0], hp_center[1])
            fc = hp_full_color if isinstance(hp_full_color, (list, tuple)) else (hp_full_color[0], hp_full_color[1], hp_full_color[2])
            dc = hp_dark_color if hp_dark_color and isinstance(hp_dark_color, (list, tuple)) else fc
            fill = image_helper.read_orb_fill_percentage(cx, cy, hp_radius, fc[0], fc[1], fc[2], dc[0], dc[1], dc[2], hp_tolerance)
            hp_color = QColor(int(255 * (1 - fill)), int(255 * fill), 0)
            self._draw_orb_indicator(painter, cx, cy, hp_radius, hp_color, f"HP {int(fill * 100)}%")

        res_center = shared.get('resource_orb_center')
        res_radius = shared.get('resource_orb_radius') or 0
        res_full_color = shared.get('resource_orb_full_color')
        res_dark_color = shared.get('resource_orb_dark_color')
        res_tolerance = shared.get('resource_orb_tolerance') or 45
        if res_center and res_radius > 0 and res_full_color:
            cx, cy = res_center if isinstance(res_center, (list, tuple)) else (res_center[0], res_center[1])
            fc = res_full_color if isinstance(res_full_color, (list, tuple)) else (res_full_color[0], res_full_color[1], res_full_color[2])
            dc = res_dark_color if res_dark_color and isinstance(res_dark_color, (list, tuple)) else fc
            fill = image_helper.read_orb_fill_percentage(cx, cy, res_radius, fc[0], fc[1], fc[2], dc[0], dc[1], dc[2], res_tolerance)
            res_color = QColor(0, int(200 * fill), int(255 * fill))
            self._draw_orb_indicator(painter, cx, cy, res_radius, res_color, f"RES {int(fill * 100)}%")

        label_map = {
            'skill1': 'S1', 'skill2': 'S2', 'skill3': 'S3',
            'skill4': 'S4', 'skill5': 'S5', 'skill6': 'S6', 'pot': 'POT', 'evade': 'EVADE'
        }

        for key in config_helper.SKILL_SLOTS:
            pos = self._cached_cls_cfg.get(f'{key}_pos')
            if not pos or len(pos) < 4:
                continue
            x, y, w, h = pos[0], pos[1], pos[2], pos[3]
            state_info = self._skill_states.get(key, {})
            state = state_info.get('state', 'cd') if isinstance(state_info, dict) else 'cd'
            mode = state_info.get('mode', '') if isinstance(state_info, dict) else ''
            cast_tracker = self._get_cast_tracker()
            if cast_tracker and cast_tracker.is_flashing(key):
                state = 'casting'
            fill_color = self.STATE_COLORS.get(state, self.STATE_COLORS['cd'])
            border_color = self.STATE_COLORS.get(f'{state}_border', self.STATE_COLORS['cd_border'])
            painter.setPen(QPen(border_color, 3))
            painter.setBrush(QBrush(fill_color))
            painter.drawRect(x, y, w, h)
            label_text = f"{label_map.get(key, key.upper())}:{state.upper()}"
            if mode:
                label_text += f":{mode}"
            self._draw_label(painter, label_text, x, y - 15, border_color)

        self._draw_legend(painter)

    def _draw_orb_indicator(self, painter, cx, cy, radius, color, label):
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))
        painter.drawEllipse(QPoint(cx, cy), radius, radius)
        painter.drawLine(cx - radius, cy, cx + radius, cy)
        painter.drawLine(cx, cy - radius, cx, cy + radius)
        self._draw_label(painter, label, cx + radius + 5, cy - 5, color)

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

    def _draw_label(self, painter, text, x, y, color):
        painter.setPen(QPen(Qt.white, 1))
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        bg_rect = QRect(x - 2, y - 14, painter.fontMetrics().horizontalAdvance(text) + 6, 16)
        painter.drawRect(bg_rect)
        painter.drawText(x + 2, y, text)

    def mousePressEvent(self, event):
        self.close()


class ConfigVisualizer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        shared_cfg = config_helper.read_config()

        hp_center = config_helper.get_shared_config('hp_orb_center')
        hp_radius = config_helper.get_shared_config('hp_orb_radius') or 0
        if hp_center and hp_radius > 0:
            cx, cy = hp_center if isinstance(hp_center, (list, tuple)) else (hp_center[0], hp_center[1])
            painter.setPen(QPen(QColor(255, 50, 50), 2))
            painter.setBrush(QBrush(QColor(255, 50, 50, 30)))
            painter.drawEllipse(QPoint(cx, cy), hp_radius, hp_radius)
            painter.drawLine(cx - hp_radius, cy, cx + hp_radius, cy)
            painter.drawLine(cx, cy - hp_radius, cx, cy + hp_radius)
            self._draw_label(painter, "HP Orb", cx + hp_radius + 5, cy - 5, QColor(255, 100, 100))

        res_center = config_helper.get_shared_config('resource_orb_center')
        res_radius = config_helper.get_shared_config('resource_orb_radius') or 0
        if res_center and res_radius > 0:
            cx, cy = res_center if isinstance(res_center, (list, tuple)) else (res_center[0], res_center[1])
            painter.setPen(QPen(QColor(50, 150, 255), 2))
            painter.setBrush(QBrush(QColor(50, 150, 255, 30)))
            painter.drawEllipse(QPoint(cx, cy), res_radius, res_radius)
            painter.drawLine(cx - res_radius, cy, cx + res_radius, cy)
            painter.drawLine(cx, cy - res_radius, cx, cy + res_radius)
            self._draw_label(painter, "Resource Orb", cx + res_radius + 5, cy - 5, QColor(100, 180, 255))

        skill_labels = {
            'skill1': 'Skill 1', 'skill2': 'Skill 2', 'skill3': 'Skill 3',
            'skill4': 'Skill 4', 'skill5': 'Skill 5', 'skill6': 'Skill 6',
            'pot': 'Potion', 'evade': 'Evade'
        }
        current_class = config_helper.get_current_class()
        cls_cfg = config_helper.get_class_config(current_class)
        for key, label in skill_labels.items():
            vals = cls_cfg.get(f'{key}_pos')
            if vals and len(vals) >= 4:
                x, y, w, h = vals[0], vals[1], vals[2], vals[3]
                painter.setPen(QPen(QColor(255, 0, 255), 2))
                painter.setBrush(QBrush(QColor(255, 0, 255, 30)))
                painter.drawRect(x, y, w, h)
                self._draw_label(painter, label, x + 5, y + h // 2, QColor(255, 0, 255))

    def _draw_label(self, painter, text, x, y, color):
        painter.setPen(QPen(Qt.white, 1))
        painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        bg_rect = QRect(x - 2, y - 14, painter.fontMetrics().horizontalAdvance(text) + 6, 16)
        painter.drawRect(bg_rect)
        painter.drawText(x + 2, y, text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

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


class _OrbFillBar(QWidget):
    def __init__(self, color_hue='green', parent=None):
        super().__init__(parent)
        self._fill = 0.0
        self._color_hue = color_hue
        self.setFixedSize(200, 16)

    def set_fill(self, value):
        self._fill = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(80, 80, 100, 150), 1))
        painter.setBrush(QBrush(QColor(30, 30, 40, 200)))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        if self._fill > 0:
            bar_w = int((self.width() - 2) * self._fill)
            if self._color_hue == 'green':
                color = QColor(0, 200, 80, 220)
            else:
                color = QColor(50, 150, 255, 220)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(1, 1, bar_w, self.height() - 2)


class Toolbox(QWidget):
    def __init__(self, parent=None):
        super(Toolbox, self).__init__(parent)

        self.setStyleSheet(TOOLBOX_STYLESHEET)

        self._live_viz = None
        self._build_ui()
        self.load_config_to_fields()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_skills_tab(), "Skills & Input")
        self._tabs.addTab(self._build_macro_tab(), "Macro Rules")
        self._tabs.addTab(self._build_bar_setup_tab(), "Bar Setup")
        root.addWidget(self._tabs, 1)
        root.addWidget(self._build_bottom_bar())

    def _build_skills_tab(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(4)
        for key in config_helper.SKILL_SLOTS:
            layout.addWidget(self._build_skill_row(key))
        layout.addStretch()
        return container

    def _build_skill_row(self, key):
        group = QGroupBox(self._slot_label(key))
        row = QHBoxLayout(group)
        row.setContentsMargins(8, 6, 8, 6)

        cb = QCheckBox("Enabled")
        cb.setObjectName(f'skill_{key}_enabled')
        cb.setChecked(True)
        cb.toggled.connect(lambda checked, k=key: self._sync_enabled_state(k, checked, 'skill'))
        row.addWidget(cb)

        row.addWidget(QLabel("Key:"))
        key_ed = QLineEdit()
        key_ed.setFixedSize(70, 24)
        key_ed.setObjectName(f'skill_{key}_key')
        row.addWidget(key_ed)

        row.addWidget(QLabel("X:"))
        x_sp = QSpinBox()
        x_sp.setRange(0, 9999)
        x_sp.setFixedSize(65, 24)
        x_sp.setObjectName(f'skill_{key}_x')
        row.addWidget(x_sp)

        row.addWidget(QLabel("Y:"))
        y_sp = QSpinBox()
        y_sp.setRange(0, 9999)
        y_sp.setFixedSize(65, 24)
        y_sp.setObjectName(f'skill_{key}_y')
        row.addWidget(y_sp)

        row.addWidget(QLabel("W:"))
        w_sp = QSpinBox()
        w_sp.setRange(0, 9999)
        w_sp.setFixedSize(55, 24)
        w_sp.setObjectName(f'skill_{key}_w')
        row.addWidget(w_sp)

        row.addWidget(QLabel("H:"))
        h_sp = QSpinBox()
        h_sp.setRange(0, 9999)
        h_sp.setFixedSize(55, 24)
        h_sp.setObjectName(f'skill_{key}_h')
        row.addWidget(h_sp)

        set_btn = QPushButton("SET")
        set_btn.setFixedSize(45, 24)
        set_btn.clicked.connect(lambda checked, k=key: self.select_skill_pos(k))
        row.addWidget(set_btn)

        cal_btn = QPushButton("CALIBRATE")
        cal_btn.setFixedSize(85, 24)
        cal_btn.setToolTip("Calibrate skill state detection (HSV)")
        cal_btn.setObjectName(f'skill_{key}_cal_btn')
        cal_btn.clicked.connect(lambda checked, k=key: self._calibrate_skill(k))
        row.addWidget(cal_btn)

        cal_status = QLabel("⚠")
        cal_status.setObjectName(f'skill_{key}_cal_status')
        cal_status.setToolTip("⚠ = using fallback thresholds | ✓ = calibrated")
        cal_status.setFixedSize(20, 20)
        row.addWidget(cal_status)

        row.addStretch()
        return group

    def _build_macro_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(4)

        for key in config_helper.SKILL_SLOTS:
            layout.addWidget(self._build_macro_section(key))
        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_macro_section(self, key):
        group = QGroupBox(self._slot_label(key))
        group.setCheckable(True)
        group.setChecked(True)
        group.setObjectName(f'macro_group_{key}')
        group.toggled.connect(lambda checked, k=key: self._sync_enabled_state(k, checked, 'macro'))
        vbox = QVBoxLayout(group)
        vbox.setContentsMargins(8, 18, 8, 8)
        vbox.setSpacing(4)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Mode:"))
        mode_cb = QComboBox()
        mode_cb.addItems(['ready', 'delay', 'filler', 'hp_guard', 'resource_guard', 'hold'])
        mode_cb.setObjectName(f'macro_{key}_mode')
        mode_cb.currentTextChanged.connect(lambda text, k=key: self._update_macro_title(k))
        row1.addWidget(mode_cb)

        row1.addWidget(QLabel("Priority:"))
        pri_sp = QSpinBox()
        pri_sp.setRange(1, 8)
        pri_sp.setObjectName(f'macro_{key}_priority')
        pri_sp.valueChanged.connect(lambda val, k=key: self._update_macro_title(k))
        row1.addWidget(pri_sp)

        row1.addWidget(QLabel("Chain:"))
        chain_items = ['none'] + [s for s in config_helper.SKILL_SLOTS if s not in ('pot', 'evade')]
        chain_cb = QComboBox()
        chain_cb.addItems(chain_items)
        chain_cb.setObjectName(f'macro_{key}_chain_next')
        row1.addWidget(chain_cb)

        row1.addWidget(QLabel("Delay:"))
        chain_delay = QDoubleSpinBox()
        chain_delay.setRange(0.0, 5.0)
        chain_delay.setSingleStep(0.05)
        chain_delay.setDecimals(2)
        chain_delay.setObjectName(f'macro_{key}_chain_delay')
        chain_delay.setSuffix(" s")
        row1.addWidget(chain_delay)
        row1.addStretch()
        vbox.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Cast Delay"))
        row2.addWidget(QLabel("Min:"))
        delay_min = QDoubleSpinBox()
        delay_min.setRange(0.0, 60.0)
        delay_min.setSingleStep(0.1)
        delay_min.setDecimals(1)
        delay_min.setObjectName(f'macro_{key}_delay_min')
        delay_min.setSuffix(" s")
        row2.addWidget(delay_min)
        row2.addWidget(QLabel("Max:"))
        delay_max = QDoubleSpinBox()
        delay_max.setRange(0.0, 60.0)
        delay_max.setSingleStep(0.1)
        delay_max.setDecimals(1)
        delay_max.setObjectName(f'macro_{key}_delay_max')
        delay_max.setSuffix(" s")
        row2.addWidget(delay_max)
        row2.addStretch()
        vbox.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("HP Threshold"))
        row3.addWidget(QLabel("Min:"))
        hp_min = QSpinBox()
        hp_min.setRange(0, 100)
        hp_min.setSingleStep(5)
        hp_min.setObjectName(f'macro_{key}_hp_min')
        hp_min.setSuffix(" %")
        row3.addWidget(hp_min)
        row3.addWidget(QLabel("Max:"))
        hp_max = QSpinBox()
        hp_max.setRange(0, 100)
        hp_max.setSingleStep(5)
        hp_max.setObjectName(f'macro_{key}_hp_max')
        hp_max.setSuffix(" %")
        row3.addWidget(hp_max)
        row3.addStretch()
        vbox.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Resource"))
        row4.addWidget(QLabel("Min:"))
        res_min = QSpinBox()
        res_min.setRange(0, 100)
        res_min.setSingleStep(5)
        res_min.setObjectName(f'macro_{key}_resource_min')
        res_min.setSuffix(" %")
        row4.addWidget(res_min)
        row4.addWidget(QLabel("Max:"))
        res_max = QSpinBox()
        res_max.setRange(0, 100)
        res_max.setSingleStep(5)
        res_max.setObjectName(f'macro_{key}_resource_max')
        res_max.setSuffix(" %")
        row4.addWidget(res_max)
        row4.addStretch()
        vbox.addLayout(row4)

        row5 = QHBoxLayout()
        always_cb = QCheckBox("Always Available (ignore cooldown)")
        always_cb.setObjectName(f'macro_{key}_always_available')
        row5.addWidget(always_cb)
        hold_cb = QCheckBox("Always Hold")
        hold_cb.setObjectName(f'macro_{key}_always_hold')
        hold_cb.setChecked(True)
        hold_cb.setVisible(False)
        row5.addWidget(hold_cb)
        row5.addStretch()
        vbox.addLayout(row5)

        mode_cb.currentTextChanged.connect(lambda text, k=key: self._update_hold_visibility(k))

        return group

    def _sync_enabled_state(self, key, checked, source):
        if source == 'skill':
            macro_group = self.findChild(QGroupBox, f'macro_group_{key}')
            if macro_group and macro_group.isChecked() != checked:
                macro_group.blockSignals(True)
                macro_group.setChecked(checked)
                macro_group.blockSignals(False)
        elif source == 'macro':
            cb = self.findChild(QCheckBox, f'skill_{key}_enabled')
            if cb and cb.isChecked() != checked:
                cb.blockSignals(True)
                cb.setChecked(checked)
                cb.blockSignals(False)

    def _update_cal_status(self, key):
        status_lbl = self.findChild(QLabel, f'skill_{key}_cal_status')
        if not status_lbl:
            return
        cls_cfg = config_helper.get_class_config(config_helper.read_config().get('class', 'Paladin'))
        cal = cls_cfg.get(f'{key}_cal')
        if cal and isinstance(cal, dict) and 'pixel1_x' in cal:
            status_lbl.setText("✓")
            status_lbl.setStyleSheet("color: #00cc66; font-weight: bold;")
        else:
            status_lbl.setText("⚠")
            status_lbl.setStyleSheet("color: #cc8800; font-weight: bold;")

    def _calibrate_skill(self, key):
        from PyQt5.QtWidgets import QMessageBox
        from GUI.selectors import ColorPickerOverlay

        ret = QMessageBox.information(
            self, f"Calibrate {self._slot_label(key)}",
            "Make sure the skill is READY (off cooldown).\n\n"
            "Click OK, then click 2 pixels on the skill icon where the cooldown sweep passes.\n\n"
            "Tip: pick spots that go DARK when the skill is on cooldown.",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if ret != QMessageBox.Ok:
            return

        picker = ColorPickerOverlay()
        picker._prompt = "Click PIXEL 1 on the skill icon (cooldown sweep area)"
        result = picker.run()
        if result is None or len(picker._clicks) < 2:
            return

        p1 = picker._clicks[0]['pos']
        p2 = picker._clicks[1]['pos']
        b1 = image_helper.read_pixel_brightness(p1.x(), p1.y())
        b2 = image_helper.read_pixel_brightness(p2.x(), p2.y())

        calibration = {
            'pixel1_x': p1.x(), 'pixel1_y': p1.y(), 'pixel1_brightness': round(b1, 1),
            'pixel2_x': p2.x(), 'pixel2_y': p2.y(), 'pixel2_brightness': round(b2, 1),
        }

        current_class = config_helper.read_config().get('class', 'Paladin')
        config_helper.batch_save({}, {current_class: {f'{key}_cal': calibration}})
        logging_helper.log_info(f"Calibrated {key}: {calibration}")
        self._update_cal_status(key)
        QMessageBox.information(self, "Calibration",
            f"{self._slot_label(key)} calibrated!\n"
            f"Pixel 1: ({p1.x()}, {p1.y()}) brightness={b1:.1f}\n"
            f"Pixel 2: ({p2.x()}, {p2.y()}) brightness={b2:.1f}")

    def _update_macro_title(self, key):
        group = self.findChild(QGroupBox, f'macro_group_{key}')
        mode_cb = self.findChild(QComboBox, f'macro_{key}_mode')
        pri_sp = self.findChild(QSpinBox, f'macro_{key}_priority')
        if group and mode_cb and pri_sp:
            mode = mode_cb.currentText()
            pri = pri_sp.value()
            group.setTitle(f"{self._slot_label(key)}  —  {mode}, pri:{pri}")

    def _update_hold_visibility(self, key):
        mode_cb = self.findChild(QComboBox, f'macro_{key}_mode')
        hold_cb = self.findChild(QCheckBox, f'macro_{key}_always_hold')
        if mode_cb and hold_cb:
            hold_cb.setVisible(mode_cb.currentText() == 'hold')

    def _build_bar_setup_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        layout.addWidget(self._build_orb_group('hp'))
        layout.addWidget(self._build_orb_group('resource'))
        layout.addWidget(self._build_orb_info_box())
        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_orb_group(self, orb_type):
        prefix = orb_type
        title = "HP Orb" if orb_type == 'hp' else "Resource Orb"
        fill_color = 'green' if orb_type == 'hp' else 'blue'
        group = QGroupBox(title)
        vbox = QVBoxLayout(group)
        vbox.setContentsMargins(8, 18, 8, 8)
        vbox.setSpacing(4)

        row_center = QHBoxLayout()
        row_center.addWidget(QLabel("Center X:"))
        cx = QSpinBox()
        cx.setRange(0, 9999)
        cx.setObjectName(f'{prefix}_orb_center_x')
        row_center.addWidget(cx)
        row_center.addWidget(QLabel("Y:"))
        cy = QSpinBox()
        cy.setRange(0, 9999)
        cy.setObjectName(f'{prefix}_orb_center_y')
        row_center.addWidget(cy)
        row_center.addWidget(QLabel("Radius:"))
        rad = QSpinBox()
        rad.setRange(0, 999)
        rad.setObjectName(f'{prefix}_orb_radius')
        row_center.addWidget(rad)
        set_orb_btn = QPushButton("SET ORB")
        set_orb_btn.orb_type = orb_type
        set_orb_btn.clicked.connect(lambda checked, t=orb_type: self.select_orb(t))
        row_center.addWidget(set_orb_btn)
        row_center.addStretch()
        vbox.addLayout(row_center)

        row_color = QHBoxLayout()
        row_color.addWidget(QLabel("Full Color R:"))
        fr = QSpinBox()
        fr.setRange(0, 255)
        fr.setObjectName(f'{prefix}_full_r')
        row_color.addWidget(fr)
        row_color.addWidget(QLabel("G:"))
        fg = QSpinBox()
        fg.setRange(0, 255)
        fg.setObjectName(f'{prefix}_full_g')
        row_color.addWidget(fg)
        row_color.addWidget(QLabel("B:"))
        fb = QSpinBox()
        fb.setRange(0, 255)
        fb.setObjectName(f'{prefix}_full_b')
        row_color.addWidget(fb)
        row_color.addWidget(QLabel("  Dark R:"))
        dr = QSpinBox()
        dr.setRange(0, 255)
        dr.setObjectName(f'{prefix}_dark_r')
        row_color.addWidget(dr)
        row_color.addWidget(QLabel("G:"))
        dg = QSpinBox()
        dg.setRange(0, 255)
        dg.setObjectName(f'{prefix}_dark_g')
        row_color.addWidget(dg)
        row_color.addWidget(QLabel("B:"))
        db = QSpinBox()
        db.setRange(0, 255)
        db.setObjectName(f'{prefix}_dark_b')
        row_color.addWidget(db)
        row_color.addWidget(QLabel("Tol:"))
        tol = QSpinBox()
        tol.setRange(0, 100)
        tol.setObjectName(f'{prefix}_tolerance')
        row_color.addWidget(tol)
        pick_btn = QPushButton("PICK COLORS")
        pick_btn.clicked.connect(lambda checked, t=orb_type: self.pick_orb_colors(t))
        row_color.addWidget(pick_btn)
        row_color.addStretch()
        vbox.addLayout(row_color)

        row_reading = QHBoxLayout()
        row_reading.addWidget(QLabel("Current Reading:"))
        fill_bar = _OrbFillBar(color_hue=fill_color)
        fill_bar.setObjectName(f'{prefix}_fill_bar')
        row_reading.addWidget(fill_bar)
        fill_label = QLabel("-- %")
        fill_label.setObjectName(f'{prefix}_fill_label')
        fill_label.setMinimumWidth(50)
        row_reading.addWidget(fill_label)
        test_btn = QPushButton("TEST")
        test_btn.orb_type = orb_type
        test_btn.clicked.connect(lambda checked, t=orb_type: self.test_orb(t))
        row_reading.addWidget(test_btn)
        row_reading.addStretch()
        vbox.addLayout(row_reading)

        return group

    def _build_orb_info_box(self):
        group = QGroupBox("Orb Detection Info")
        vbox = QVBoxLayout(group)
        vbox.setContentsMargins(8, 18, 8, 8)
        info = QLabel(
            "The orb detection system samples circular regions on screen.\n"
            "Use SET ORB to drag-select a circle over the HP or Resource orb.\n"
            "SAMPLE EMPTY COLOR reads the bottom of the orb to determine the 'empty' color.\n"
            "TEST reads the current fill percentage using the configured empty color and tolerance.\n"
            "Tolerance controls how closely a pixel must match the empty color (higher = more lenient)."
        )
        info.setWordWrap(True)
        vbox.addWidget(info)
        return group

    def _build_bottom_bar(self):
        bar = QWidget()
        bar.setFixedHeight(50)
        row = QHBoxLayout(bar)
        row.setContentsMargins(4, 4, 4, 4)

        load_btn = QPushButton("LOAD FROM CONFIG")
        load_btn.clicked.connect(self.load_config_to_fields)
        row.addWidget(load_btn)

        save_btn = QPushButton("SAVE TO CONFIG")
        save_btn.clicked.connect(self.save_fields_to_config)
        row.addWidget(save_btn)

        row.addSpacing(20)

        viz_btn = QPushButton("VISUALIZE")
        viz_btn.clicked.connect(self.visualize_config)
        row.addWidget(viz_btn)

        self.liveVizCheck = QCheckBox("Live Viz")
        self.liveVizCheck.stateChanged.connect(self.on_live_viz_toggled)
        row.addWidget(self.liveVizCheck)

        row.addSpacing(20)

        row.addWidget(QLabel("Rotation Hotkey:"))
        self._hotkey_btn = QPushButton("f6")
        self._hotkey_btn.setFixedSize(100, 28)
        self._hotkey_btn.setObjectName('rotation_hotkey_btn')
        self._hotkey_btn.clicked.connect(self._capture_hotkey)
        row.addWidget(self._hotkey_btn)

        capture_btn = QPushButton("CAPTURE")
        capture_btn.clicked.connect(self._capture_hotkey)
        row.addWidget(capture_btn)

        row.addStretch()
        return bar

    @staticmethod
    def _slot_label(key):
        labels = {
            'skill1': 'Skill 1', 'skill2': 'Skill 2', 'skill3': 'Skill 3',
            'skill4': 'Skill 4', 'skill5': 'Skill 5', 'skill6': 'Skill 6',
            'pot': 'Potion', 'evade': 'Evade',
        }
        return labels.get(key, key)

    def select_skill_pos(self, key):
        selector = RectDragSelector()
        result = selector.run()
        if result:
            self._find_spin_set(f'skill_{key}_x', result.left())
            self._find_spin_set(f'skill_{key}_y', result.top())
            self._find_spin_set(f'skill_{key}_w', result.width())
            self._find_spin_set(f'skill_{key}_h', result.height())
            logging_helper.log_info(f"Selected skill {key} region at {result.left()},{result.top()} {result.width()}x{result.height()}")

    def select_orb(self, orb_type):
        selector = CircleDragSelector()
        result = selector.run()
        if result:
            center, radius = result
            prefix = orb_type
            self._find_spin_set(f'{prefix}_orb_center_x', center.x())
            self._find_spin_set(f'{prefix}_orb_center_y', center.y())
            self._find_spin_set(f'{prefix}_orb_radius', radius)
            logging_helper.log_info(f"Selected {orb_type} orb at {center.x()},{center.y()} r={radius}")

    def pick_orb_colors(self, orb_type):
        from GUI.selectors import ColorPickerOverlay
        picker = ColorPickerOverlay()
        result = picker.run()
        if result is None:
            return
        bright, dark = result
        prefix = orb_type
        self._find_spin_set(f'{prefix}_full_r', bright[0])
        self._find_spin_set(f'{prefix}_full_g', bright[1])
        self._find_spin_set(f'{prefix}_full_b', bright[2])
        self._find_spin_set(f'{prefix}_dark_r', dark[0])
        self._find_spin_set(f'{prefix}_dark_g', dark[1])
        self._find_spin_set(f'{prefix}_dark_b', dark[2])
        logging_helper.log_info(f"Picked {orb_type} orb colors: bright=({bright[0]},{bright[1]},{bright[2]}) dark=({dark[0]},{dark[1]},{dark[2]})")

    def test_orb(self, orb_type):
        prefix = orb_type
        cx_sp = self.findChild(QSpinBox, f'{prefix}_orb_center_x')
        cy_sp = self.findChild(QSpinBox, f'{prefix}_orb_center_y')
        rad_sp = self.findChild(QSpinBox, f'{prefix}_orb_radius')
        fr_sp = self.findChild(QSpinBox, f'{prefix}_full_r')
        fg_sp = self.findChild(QSpinBox, f'{prefix}_full_g')
        fb_sp = self.findChild(QSpinBox, f'{prefix}_full_b')
        dr_sp = self.findChild(QSpinBox, f'{prefix}_dark_r')
        dg_sp = self.findChild(QSpinBox, f'{prefix}_dark_g')
        db_sp = self.findChild(QSpinBox, f'{prefix}_dark_b')
        tol_sp = self.findChild(QSpinBox, f'{prefix}_tolerance')
        if not all([cx_sp, cy_sp, rad_sp, fr_sp, fg_sp, fb_sp]):
            return
        fr, fg, fb = fr_sp.value(), fg_sp.value(), fb_sp.value()
        dr_val = dr_sp.value() if dr_sp else fr
        dg_val = dg_sp.value() if dg_sp else fg
        db_val = db_sp.value() if db_sp else fb
        fill = image_helper.read_orb_fill_percentage(
            cx_sp.value(), cy_sp.value(), rad_sp.value(),
            fr, fg, fb, dr_val, dg_val, db_val,
            tol_sp.value() if tol_sp else 45
        )
        fill_bar = self.findChild(_OrbFillBar, f'{prefix}_fill_bar')
        fill_label = self.findChild(QLabel, f'{prefix}_fill_label')
        if fill_bar:
            fill_bar.set_fill(fill)
        if fill_label:
            fill_label.setText(f"{int(fill * 100)} %")

    def visualize_config(self):
        viz = ConfigVisualizer()
        viz.run()

    def on_live_viz_toggled(self, state):
        if state == Qt.Checked:
            if not self._live_viz:
                self._live_viz = LiveVisualizerWidget()
            self._live_viz.show()
        else:
            if self._live_viz:
                self._live_viz.close()
                self._live_viz = None

    def _capture_hotkey(self):
        self._hotkey_btn.setText('Press a key...')
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
        logging_helper.log_info(f'Captured hotkey: {captured}')

    def load_config_to_fields(self):
        current_class = config_helper.get_current_class()
        cls_cfg = config_helper.get_class_config(current_class)

        default_keys = {
            'skill1': 'q', 'skill2': 'w', 'skill3': 'e', 'skill4': 'r',
            'skill5': 'leftclick', 'skill6': 'rightclick', 'pot': '2', 'evade': 'space',
        }
        default_positions = {
            'skill1': (801, 45, 60, 60), 'skill2': (710, 45, 60, 60),
            'skill3': (619, 45, 60, 60), 'skill4': (528, 45, 60, 60),
            'skill5': (890, 45, 60, 60), 'skill6': (980, 45, 60, 60),
            'pot': (437, 45, 60, 60), 'evade': (346, 45, 60, 60),
        }

        for key in config_helper.SKILL_SLOTS:
            key_val = cls_cfg.get(key, default_keys.get(key, ''))
            self._find_and_set(f'skill_{key}_key', str(key_val))

            cb = self.findChild(QCheckBox, f'skill_{key}_enabled')
            if cb:
                cb.setChecked(cls_cfg.get(f'{key}_enabled', True))

            pos_default = default_positions.get(key, (0, 0, 60, 60))
            vals = cls_cfg.get(f'{key}_pos', pos_default)
            self._find_spin_set(f'skill_{key}_x', vals[0])
            self._find_spin_set(f'skill_{key}_y', vals[1])
            self._find_spin_set(f'skill_{key}_w', vals[2] if len(vals) >= 3 else 60)
            self._find_spin_set(f'skill_{key}_h', vals[3] if len(vals) >= 4 else 60)

        for key in config_helper.SKILL_SLOTS:
            mode_cb = self.findChild(QComboBox, f'macro_{key}_mode')
            if mode_cb:
                mode_val = cls_cfg.get(f'{key}_mode', 'ready')
                idx = mode_cb.findText(mode_val)
                if idx >= 0:
                    mode_cb.setCurrentIndex(idx)

            pri_sp = self.findChild(QSpinBox, f'macro_{key}_priority')
            if pri_sp:
                pri_sp.setValue(cls_cfg.get(f'{key}_priority', 5))

            chain_cb = self.findChild(QComboBox, f'macro_{key}_chain_next')
            if chain_cb:
                chain_val = cls_cfg.get(f'{key}_chain_next', 'none')
                if not chain_val:
                    chain_val = 'none'
                idx = chain_cb.findText(chain_val)
                if idx >= 0:
                    chain_cb.setCurrentIndex(idx)

            self._find_spin_set_d(f'macro_{key}_chain_delay', cls_cfg.get(f'{key}_chain_delay', 0.1))
            self._find_spin_set_d(f'macro_{key}_delay_min', cls_cfg.get(f'{key}_delay_min', 0.0))
            self._find_spin_set_d(f'macro_{key}_delay_max', cls_cfg.get(f'{key}_delay_max', 0.0))
            self._find_spin_set(f'macro_{key}_hp_min', cls_cfg.get(f'{key}_hp_min', 0))
            self._find_spin_set(f'macro_{key}_hp_max', cls_cfg.get(f'{key}_hp_max', 100))
            self._find_spin_set(f'macro_{key}_resource_min', cls_cfg.get(f'{key}_resource_min', 0))
            self._find_spin_set(f'macro_{key}_resource_max', cls_cfg.get(f'{key}_resource_max', 100))

            always_cb = self.findChild(QCheckBox, f'macro_{key}_always_available')
            if always_cb:
                always_cb.setChecked(cls_cfg.get(f'{key}_always_available', False))

            hold_cb = self.findChild(QCheckBox, f'macro_{key}_always_hold')
            if hold_cb:
                hold_cb.setChecked(cls_cfg.get(f'{key}_always_hold', True))

            macro_group = self.findChild(QGroupBox, f'macro_group_{key}')
            if macro_group:
                macro_group.blockSignals(True)
                macro_group.setChecked(cls_cfg.get(f'{key}_enabled', True))
                macro_group.blockSignals(False)

            self._update_macro_title(key)
            self._update_hold_visibility(key)
            self._update_cal_status(key)

        hp_center = config_helper.get_shared_config('hp_orb_center')
        if hp_center:
            cx, cy = hp_center if isinstance(hp_center, (list, tuple)) else (hp_center[0], hp_center[1])
            self._find_spin_set('hp_orb_center_x', cx)
            self._find_spin_set('hp_orb_center_y', cy)
        hp_radius = config_helper.get_shared_config('hp_orb_radius')
        if hp_radius is not None:
            self._find_spin_set('hp_orb_radius', hp_radius)
        hp_full_color = config_helper.get_shared_config('hp_orb_full_color')
        if hp_full_color:
            r, g, b = hp_full_color if isinstance(hp_full_color, (list, tuple)) else (hp_full_color[0], hp_full_color[1], hp_full_color[2])
            self._find_spin_set('hp_full_r', r)
            self._find_spin_set('hp_full_g', g)
            self._find_spin_set('hp_full_b', b)
        hp_dark_color = config_helper.get_shared_config('hp_orb_dark_color')
        if hp_dark_color:
            r, g, b = hp_dark_color if isinstance(hp_dark_color, (list, tuple)) else (hp_dark_color[0], hp_dark_color[1], hp_dark_color[2])
            self._find_spin_set('hp_dark_r', r)
            self._find_spin_set('hp_dark_g', g)
            self._find_spin_set('hp_dark_b', b)
        hp_tolerance = config_helper.get_shared_config('hp_orb_tolerance')
        if hp_tolerance is not None:
            self._find_spin_set('hp_tolerance', hp_tolerance)

        res_center = config_helper.get_shared_config('resource_orb_center')
        if res_center:
            cx, cy = res_center if isinstance(res_center, (list, tuple)) else (res_center[0], res_center[1])
            self._find_spin_set('resource_orb_center_x', cx)
            self._find_spin_set('resource_orb_center_y', cy)
        res_radius = config_helper.get_shared_config('resource_orb_radius')
        if res_radius is not None:
            self._find_spin_set('resource_orb_radius', res_radius)
        res_full_color = config_helper.get_shared_config('resource_orb_full_color')
        if res_full_color:
            r, g, b = res_full_color if isinstance(res_full_color, (list, tuple)) else (res_full_color[0], res_full_color[1], res_full_color[2])
            self._find_spin_set('resource_full_r', r)
            self._find_spin_set('resource_full_g', g)
            self._find_spin_set('resource_full_b', b)
        res_dark_color = config_helper.get_shared_config('resource_orb_dark_color')
        if res_dark_color:
            r, g, b = res_dark_color if isinstance(res_dark_color, (list, tuple)) else (res_dark_color[0], res_dark_color[1], res_dark_color[2])
            self._find_spin_set('resource_dark_r', r)
            self._find_spin_set('resource_dark_g', g)
            self._find_spin_set('resource_dark_b', b)
        res_tolerance = config_helper.get_shared_config('resource_orb_tolerance')
        if res_tolerance is not None:
            self._find_spin_set('resource_tolerance', res_tolerance)

        hotkey_val = config_helper.get_shared_config('rotation_hotkey', 'f6')
        if hasattr(self, '_hotkey_btn'):
            self._hotkey_btn.setText(str(hotkey_val))

        logging_helper.log_info(f'Loaded config into fields for class: {current_class}')

    def save_fields_to_config(self):
        current_class = config_helper.get_current_class()

        def _sv(name, default=0):
            sp = self.findChild(QSpinBox, name)
            return sp.value() if sp else default

        def _dsv(name, default=0.0):
            sp = self.findChild(QDoubleSpinBox, name)
            return sp.value() if sp else default

        def _cv(name, default=''):
            cb = self.findChild(QComboBox, name)
            return cb.currentText() if cb else default

        def _kv(name, default=''):
            le = self.findChild(QLineEdit, name)
            return le.text() if le else default

        hp_center = [_sv('hp_orb_center_x'), _sv('hp_orb_center_y')]
        hp_radius = _sv('hp_orb_radius')
        hp_full_color = [_sv('hp_full_r'), _sv('hp_full_g'), _sv('hp_full_b')]
        hp_dark_color = [_sv('hp_dark_r'), _sv('hp_dark_g'), _sv('hp_dark_b')]
        hp_tolerance = _sv('hp_tolerance', 45)

        res_center = [_sv('resource_orb_center_x'), _sv('resource_orb_center_y')]
        res_radius = _sv('resource_orb_radius')
        res_full_color = [_sv('resource_full_r'), _sv('resource_full_g'), _sv('resource_full_b')]
        res_dark_color = [_sv('resource_dark_r'), _sv('resource_dark_g'), _sv('resource_dark_b')]
        res_tolerance = _sv('resource_tolerance', 45)

        shared_updates = {
            'hp_orb_center': hp_center,
            'hp_orb_radius': hp_radius,
            'hp_orb_full_color': hp_full_color,
            'hp_orb_dark_color': hp_dark_color,
            'hp_orb_tolerance': hp_tolerance,
            'resource_orb_center': res_center,
            'resource_orb_radius': res_radius,
            'resource_orb_full_color': res_full_color,
            'resource_orb_dark_color': res_dark_color,
            'resource_orb_tolerance': res_tolerance,
        }
        if hasattr(self, '_hotkey_btn') and self._hotkey_btn.text():
            shared_updates['rotation_hotkey'] = self._hotkey_btn.text()

        class_updates = {}
        for key in config_helper.SKILL_SLOTS:
            class_updates[key] = _kv(f'skill_{key}_key')
            class_updates[f'{key}_pos'] = [
                _sv(f'skill_{key}_x'),
                _sv(f'skill_{key}_y'),
                _sv(f'skill_{key}_w', 60),
                _sv(f'skill_{key}_h', 60),
            ]
            cb = self.findChild(QCheckBox, f'skill_{key}_enabled')
            macro_group = self.findChild(QGroupBox, f'macro_group_{key}')
            enabled = (cb.isChecked() if cb else True) and (macro_group.isChecked() if macro_group else True)
            class_updates[f'{key}_enabled'] = enabled

            class_updates[f'{key}_mode'] = _cv(f'macro_{key}_mode', 'ready')
            class_updates[f'{key}_priority'] = _sv(f'macro_{key}_priority', 5)
            class_updates[f'{key}_chain_next'] = _cv(f'macro_{key}_chain_next', 'none')
            class_updates[f'{key}_chain_delay'] = _dsv(f'macro_{key}_chain_delay', 0.1)
            class_updates[f'{key}_delay_min'] = _dsv(f'macro_{key}_delay_min', 0.0)
            class_updates[f'{key}_delay_max'] = _dsv(f'macro_{key}_delay_max', 0.0)
            class_updates[f'{key}_hp_min'] = _sv(f'macro_{key}_hp_min', 0)
            class_updates[f'{key}_hp_max'] = _sv(f'macro_{key}_hp_max', 100)
            class_updates[f'{key}_resource_min'] = _sv(f'macro_{key}_resource_min', 0)
            class_updates[f'{key}_resource_max'] = _sv(f'macro_{key}_resource_max', 100)
            always_cb = self.findChild(QCheckBox, f'macro_{key}_always_available')
            class_updates[f'{key}_always_available'] = always_cb.isChecked() if always_cb else False
            hold_cb = self.findChild(QCheckBox, f'macro_{key}_always_hold')
            class_updates[f'{key}_always_hold'] = hold_cb.isChecked() if hold_cb else True

        config_helper.batch_save(shared_updates, {current_class: class_updates})
        logging_helper.log_info(f'Saved config for class: {current_class}')
        bot_config.init()

    def _find_and_set(self, object_name, value):
        le = self.findChild(QLineEdit, object_name)
        if le:
            le.setText(value)

    def _find_spin_set(self, object_name, value):
        sp = self.findChild(QSpinBox, object_name)
        if sp:
            sp.setValue(int(value))
        else:
            logging_helper.log_debug(f"SpinBox not found: {object_name}")

    def _find_spin_set_d(self, object_name, value):
        sp = self.findChild(QDoubleSpinBox, object_name)
        if sp:
            sp.setValue(float(value))
        else:
            logging_helper.log_debug(f"DoubleSpinBox not found: {object_name}")

    def _find_child(self, widget_type, object_name):
        return self.findChild(widget_type, object_name)
