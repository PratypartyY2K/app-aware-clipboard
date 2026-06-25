from PyQt6.QtWidgets import QMainWindow, QListWidget, QVBoxLayout, QWidget, QComboBox, QMenu, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QSpinBox, QHBoxLayout, QCheckBox, QPushButton, QDialog, QTextEdit, QDialogButtonBox, QFormLayout, QLineEdit
from PyQt6.QtGui import QShortcut, QKeySequence
from clipboard_manager.history import History
from clipboard_manager.watcher import ClipboardWatcher
from clipboard_manager.utils import trim_whitespace, copy_one_line, extract_urls_text, json_escape, to_camel_case, to_snake_case, fuzzy_score, highlight_match
from PyQt6.QtCore import QTimer
import os
from clipboard_manager import settings


class BlocklistEditor(QDialog):
    def __init__(self, parent=None, initial_blocklist=None):
        super(BlocklistEditor, self).__init__(parent)
        self.setWindowTitle('Edit Secret-safe Blocklist')
        self.setModal(True)
        layout = QVBoxLayout()
        form = QFormLayout()
        self.text = QTextEdit()
        if initial_blocklist:
            self.text.setPlainText('\n'.join(initial_blocklist))
        form.addRow('Blocklist entries (one per line):', self.text)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_entries(self):
        txt = self.text.toPlainText()
        return [line.strip() for line in txt.splitlines() if line.strip()]


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setWindowTitle('Settings')
        self.setModal(True)
        layout = QVBoxLayout()

        form = QFormLayout()
        self.pause_spin = QSpinBox()
        self.pause_spin.setRange(0, 5000)
        self.pause_spin.setSingleStep(50)
        self.pause_spin.setValue(int(settings.get('pause_after_set_ms', 500)))
        form.addRow('Pause after programmatic copy (ms):', self.pause_spin)

        self.secret_safe_chk = QCheckBox('Secret-safe mode')
        self.secret_safe_chk.setChecked(bool(settings.get('secret_safe_mode', True)))
        form.addRow('', self.secret_safe_chk)

        self.persistence_chk = QCheckBox('Enable persistence (store history)')
        self.persistence_chk.setChecked(bool(settings.get('persistence_enabled', False)))
        form.addRow('', self.persistence_chk)

        layout.addLayout(form)

        bl_layout = QHBoxLayout()
        self.edit_blocklist_btn = QPushButton('Edit blocklist')
        bl_layout.addWidget(self.edit_blocklist_btn)
        layout.addLayout(bl_layout)
        self.blocklist_btn = self.edit_blocklist_btn
        self._pending_blocklist = list(settings.get('blocklist_apps', []) or [])
        self.edit_blocklist_btn.clicked.connect(self._on_edit_blocklist)

        adv_group_layout = QVBoxLayout()
        adv_form = QFormLayout()
        self.dedupe_lru_spin = QSpinBox()
        self.dedupe_lru_spin.setRange(10, 5000)
        self.dedupe_lru_spin.setSingleStep(10)
        self.dedupe_lru_spin.setValue(int(settings.get('dedupe_lru_size', 200)))
        adv_form.addRow('Dedupe LRU size:', self.dedupe_lru_spin)

        self.dedupe_per_app_spin = QSpinBox()
        self.dedupe_per_app_spin.setRange(1, 3600)
        self.dedupe_per_app_spin.setSingleStep(1)
        self.dedupe_per_app_spin.setValue(int(settings.get('dedupe_per_app_window_s', 30)))
        adv_form.addRow('Per-app dedupe window (s):', self.dedupe_per_app_spin)

        self.per_app_text = QTextEdit()
        per_app_map = settings.get('per_app_capture_toggle', {}) or {}
        try:
            if isinstance(per_app_map, dict):
                lines = [f"{k}={1 if v else 0}" for k, v in per_app_map.items()]
            else:
                lines = []
        except Exception:
            lines = []
        self.per_app_text.setPlainText('\n'.join(lines))
        adv_form.addRow('Per-app capture (app=1/0 per line):', self.per_app_text)

        adv_group_layout.addLayout(adv_form)
        layout.addLayout(adv_group_layout)

        action_layout = QHBoxLayout()
        self.reset_btn = QPushButton('Reset to defaults')
        self.reset_btn.clicked.connect(self._on_reset)
        action_layout.addWidget(self.reset_btn)

        buttons = QDialogButtonBox()
        apply_btn = buttons.addButton(QDialogButtonBox.StandardButton.Apply)
        close_btn = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        apply_btn.clicked.connect(self._on_apply)
        close_btn.clicked.connect(self.accept)
        action_layout.addWidget(buttons)
        layout.addLayout(action_layout)

        self.setLayout(layout)

    def _on_edit_blocklist(self):
        initial_list = list(self._pending_blocklist or [])
        editor = BlocklistEditor(self, initial_blocklist=initial_list)
        if editor.exec() == QDialog.DialogCode.Accepted:
            entries = editor.get_entries()
            self._pending_blocklist = entries

    def _on_apply(self):
        settings.set_('pause_after_set_ms', int(self.pause_spin.value()))
        settings.set_('secret_safe_mode', bool(self.secret_safe_chk.isChecked()))
        settings.set_('persistence_enabled', bool(self.persistence_chk.isChecked()))
        settings.set_('blocklist_apps', list(self._pending_blocklist or []))
        settings.set_('dedupe_lru_size', int(self.dedupe_lru_spin.value()))
        settings.set_('dedupe_per_app_window_s', int(self.dedupe_per_app_spin.value()))
        pam = {}
        try:
            for line in (self.per_app_text.toPlainText() or '').splitlines():
                if '=' in line:
                    k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip()
                    pam[k] = bool(int(v))
        except Exception:
            pam = settings.get('per_app_capture_toggle', {}) or {}
        settings.set_('per_app_capture_toggle', pam)
        settings.save_settings()

    def _on_reset(self):
        d = settings.DEFAULTS if hasattr(settings, 'DEFAULTS') else {}
        try:
            self.pause_spin.setValue(int(d.get('pause_after_set_ms', 500)))
            self.secret_safe_chk.setChecked(bool(d.get('secret_safe_mode', True)))
            self.persistence_chk.setChecked(bool(d.get('persistence_enabled', False)))
            self.dedupe_lru_spin.setValue(int(d.get('dedupe_lru_size', 200)))
            self.dedupe_per_app_spin.setValue(int(d.get('dedupe_per_app_window_s', 30)))
            per_map = d.get('per_app_capture_toggle', {}) or {}
            lines = [f"{k}={1 if v else 0}" for k, v in per_map.items()]
            self.per_app_text.setPlainText('\n'.join(lines))
            self._pending_blocklist = list(d.get('blocklist_apps', []))
        except Exception:
            pass


class MainWindow(QMainWindow):
    def __init__(self, history=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle('App-Aware Clipboard Manager')
        self.setGeometry(100, 100, 700, 480)

        self.history = history or History()
        self._pause_ms = int(settings.get('pause_after_set_ms', 300))

        self._history_listener = lambda: QTimer.singleShot(0, self._on_history_changed)
        self.history.add_change_listener(self._history_listener)

        ss_layout = QHBoxLayout()
        self.secret_safe_checkbox = QCheckBox('Secret-safe mode')
        self.secret_safe_checkbox.setChecked(self.history.get_secret_safe_enabled())
        self.secret_safe_checkbox.stateChanged.connect(self._on_secret_safe_toggled)
        ss_layout.addWidget(self.secret_safe_checkbox)
        self.edit_blocklist_btn = QPushButton('Edit Blocklist')
        self.edit_blocklist_btn.clicked.connect(self._on_edit_blocklist)
        ss_layout.addWidget(self.edit_blocklist_btn)

        self.settings_btn = QPushButton('Settings')
        self.settings_btn.clicked.connect(self._open_settings_dialog)
        ss_layout.addWidget(self.settings_btn)

        self.app_dropdown = QComboBox()
        self.app_dropdown.currentIndexChanged.connect(self.update_list)
        self.app_capture_checkbox = QCheckBox('Capture for this app')
        self.app_capture_checkbox.stateChanged.connect(self._on_app_capture_toggled)

        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText('Search current app/board...')
        self.search_box.textChanged.connect(self.update_list)

        layout = QVBoxLayout()
        pause_layout = QHBoxLayout()
        pause_label = QLabel('Pause (ms):')
        self.pause_spin = QSpinBox()
        self.pause_spin.setRange(0, 5000)
        self.pause_spin.setSingleStep(50)
        self.pause_spin.setValue(self._pause_ms)
        self.pause_spin.valueChanged.connect(self._on_pause_spin_changed)
        pause_layout.addWidget(pause_label)
        pause_layout.addWidget(self.pause_spin)
        self.pause_status_label = QLabel('')
        self.pause_status_label.setStyleSheet('color: red; font-weight: bold;')
        self.pause_status_label.setVisible(False)
        pause_layout.addWidget(self.pause_status_label)
        layout.addLayout(pause_layout)
        layout.addLayout(ss_layout)
        layout.addWidget(self.app_dropdown)
        layout.addWidget(self.app_capture_checkbox)
        layout.addWidget(self.search_box)
        layout.addWidget(self.list_widget)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        shortcut = QShortcut(QKeySequence('Ctrl+`'), self)
        shortcut.activated.connect(self._on_hotkey_open)

        self.watcher = ClipboardWatcher()
        self.watcher.clipboard_changed.connect(self._on_clipboard_event)

    def _on_clipboard_event(self, content: str, source_app: str, timestamp: float):
        if os.environ.get('CLIP_DEBUG') == '2':
            try:
                preview = (content or '')[:200].replace('\n','\\n')
            except Exception:
                preview = ''
            print('[clip-debug] gui._on_clipboard_event received preview="%s" source_app=%s ts=%s' % (preview, source_app, timestamp))
        item = self.history.add_item(content, source_app=source_app, timestamp=timestamp)
        if item is not None:
            if os.environ.get('CLIP_DEBUG') == '2':
                print('[clip-debug] gui: history.add_item returned id=%s' % (item.id,))
            self.update_apps_dropdown()
            try:
                self.app_dropdown.setCurrentText(item.source_app)
            except Exception:
                pass
            self.update_list()
            try:
                for i in range(self.list_widget.count()):
                    lw = self.list_widget.item(i)
                    try:
                        if lw and lw.data(int(Qt.ItemDataRole.UserRole)) == item.id:
                            self.list_widget.scrollToItem(lw)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

    def _on_pause_spin_changed(self, value: int):
        self._pause_ms = int(value)
        settings.set_('pause_after_set_ms', self._pause_ms)
        try:
            settings.save_debounced()
        except Exception:
            pass

    def update_apps_dropdown(self):
        apps = self.history.get_apps()
        current_app = self.app_dropdown.currentText()
        self.app_dropdown.blockSignals(True)
        self.app_dropdown.clear()
        self.app_dropdown.addItems(apps)
        if current_app in apps:
            self.app_dropdown.setCurrentText(current_app)
        self.app_dropdown.blockSignals(False)
        sel = self.app_dropdown.currentText()
        enabled = self.history.is_app_capture_enabled(sel)
        self.app_capture_checkbox.blockSignals(True)
        self.app_capture_checkbox.setChecked(enabled)
        self.app_capture_checkbox.blockSignals(False)

    def _on_history_changed(self):
        self.update_apps_dropdown()
        self.update_list()

    def closeEvent(self, event):
        try:
            self.history.remove_change_listener(self._history_listener)
        except Exception:
            pass
        return super(MainWindow, self).closeEvent(event)

    def update_list(self):
        self.list_widget.clear()
        selected_app = self.app_dropdown.currentText()
        if not selected_app:
            return
        filter_text = self.search_box.text().strip()
        from PyQt6.QtWidgets import QListWidgetItem
        items = self.history.get_items_by_app(selected_app)
        scored = []
        for item in items:
            if not filter_text:
                score = 100
            else:
                score = fuzzy_score(item.content, filter_text)
            if score <= 0:
                continue
            scored.append((score, item))
        scored.sort(key=lambda x: (-x[0], not getattr(x[1], 'pinned', False), x[1].timestamp),)
        for score, item in scored:
            label_html = highlight_match(item.content, filter_text)
            timestamp = item.timestamp.strftime('%H:%M:%S')
            board = getattr(item.board, 'value', 'other')
            html = '<span style="color: gray; font-size: 10px">%s</span> - <span style="font-weight: bold;">[%s]</span> %s' % (timestamp, board, label_html)
            list_item = QListWidgetItem()
            list_item.setData(int(Qt.ItemDataRole.UserRole), item.id)
            if getattr(item, 'pinned', False):
                html = '<span style="color: green; font-weight: bold;">[PIN]</span> ' + html
            self.list_widget.addItem(list_item)
            label_widget = QLabel()
            label_widget.setTextFormat(Qt.TextFormat.RichText)
            label_widget.setText(html)
            label_widget.setWordWrap(True)
            self.list_widget.setItemWidget(list_item, label_widget)

    def show_context_menu(self, position):
        item = self.list_widget.itemAt(position)
        if item:
            self.list_widget.setCurrentItem(item)
        else:
            return

        menu = QMenu()
        copy_action = menu.addAction("Copy to Clipboard")
        trim_action = menu.addAction("Trim whitespace")
        oneline_action = menu.addAction("Copy as one-line")
        extract_urls_action = menu.addAction("Extract URLs")
        json_action = menu.addAction("JSON-escape")
        camel_action = menu.addAction("Convert to camelCase")
        snake_action = menu.addAction("Convert to snake_case")
        pin_action = menu.addAction("Pin item")
        unpin_action = menu.addAction("Unpin item")

        action = menu.exec(self.list_widget.viewport().mapToGlobal(position))
        if action in (copy_action, trim_action, oneline_action, extract_urls_action, json_action, camel_action, snake_action, pin_action, unpin_action):
            lw_item = self.list_widget.currentItem()
            if lw_item is None:
                return
            try:
                item_id = lw_item.data(int(Qt.ItemDataRole.UserRole))
            except Exception:
                try:
                    item_id = lw_item.data(Qt.ItemDataRole.UserRole)
                except Exception:
                    item_id = None
            item_obj = self.history.get_item_by_id(item_id)
            if item_obj is None:
                return
            original = item_obj.content

            if action == copy_action:
                out = original
            elif action == trim_action:
                out = trim_whitespace(original)
            elif action == oneline_action:
                out = copy_one_line(original)
            elif action == extract_urls_action:
                out = extract_urls_text(original)
            elif action == json_action:
                out = json_escape(original)
            elif action == camel_action:
                out = to_camel_case(original)
            elif action == snake_action:
                out = to_snake_case(original)
            else:
                out = original

            if action == pin_action:
                self.history.pin_item(item_id)
                self.update_list()
                return
            if action == unpin_action:
                self.history.unpin_item(item_id)
                self.update_list()
                return

            self.pause_status_label.setText('Paused (%d ms)' % (self._pause_ms,))
            self.pause_status_label.setVisible(True)
            self.watcher.set_text(out, pause_ms=self._pause_ms)
            try:
                QTimer.singleShot(self._pause_ms, lambda: self.pause_status_label.setVisible(False))
            except Exception:
                self.pause_status_label.setVisible(False)

    def _on_secret_safe_toggled(self, state: int):
        enabled = (state == Qt.CheckState.Checked)
        self.history.set_secret_safe_enabled(enabled)

    def _on_edit_blocklist(self):
        initial_blocklist = self.history.get_blocklist()
        editor = BlocklistEditor(self, initial_blocklist=initial_blocklist)
        if editor.exec() == QDialog.DialogCode.Accepted:
            entries = editor.get_entries()
            self.history.set_blocklist(entries)
            settings.set_('blocklist_apps', entries)
            settings.save_debounced()

    def _open_settings_dialog(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._pause_ms = int(settings.get('pause_after_set_ms', self._pause_ms))
                self.pause_spin.setValue(self._pause_ms)
            except Exception:
                pass
            try:
                self.secret_safe_checkbox.setChecked(bool(settings.get('secret_safe_mode', self.secret_safe_checkbox.isChecked())))
            except Exception:
                pass

    def _on_hotkey_open(self):
        try:
            QApplication.processEvents()
        except Exception:
            pass
        try:
            self.show()
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

        try:
            def _set_focus():
                try:
                    self.search_box.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
                except Exception:
                    try:
                        self.search_box.setFocus()
                    except Exception:
                        pass
            QTimer.singleShot(0, _set_focus)
            QTimer.singleShot(50, lambda: QApplication.processEvents())
            try:
                for _ in range(3):
                    try:
                        self.search_box.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
                    except Exception:
                        try:
                            self.search_box.setFocus()
                        except Exception:
                            pass
                    try:
                        QApplication.processEvents()
                    except Exception:
                        pass
                    if self.search_box.hasFocus():
                        break
            except Exception:
                pass
        except Exception:
            try:
                self.search_box.setFocus()
            except Exception:
                pass

    def _on_app_capture_toggled(self, state: int):
        enabled = (state == Qt.CheckState.Checked)
        current_app = self.app_dropdown.currentText()
        if current_app:
            self.history.set_app_capture_enabled(current_app, enabled)
