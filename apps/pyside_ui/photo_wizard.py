from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from pyside_ui.pipeline_runner import PhotoState, PipelineRunner


class BeforeAfterView(QWidget):
    def __init__(self):
        super().__init__()
        self.before = QPixmap()
        self.after = QPixmap()
        self.position = 50
        self.zoom = 1.0
        self.setMinimumHeight(320)
        self.setStyleSheet("background: #0f172a; border: 1px solid #64748b;")
        self.setMouseTracking(True)

    def set_images(self, before_path: Path | None, after_path: Path | None):
        self.before = QPixmap(str(before_path)) if before_path else QPixmap()
        self.after = QPixmap(str(after_path)) if after_path else QPixmap()
        self.update()

    def set_position(self, value: int):
        self.position = max(1, min(99, value))
        self.update()

    def set_zoom(self, factor: float):
        self.zoom = max(0.1, min(5.0, factor))
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120.0
        self.set_zoom(self.zoom * (1.0 + delta * 0.15))
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._update_position(event.pos().x())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._update_position(event.pos().x())
        super().mouseMoveEvent(event)

    def _update_position(self, mouse_x):
        w = self.rect().width() - 24
        if w <= 0:
            return
        pct = (mouse_x - 12) / w * 100
        self.set_position(int(max(1, min(99, pct))))

    def paintEvent(self, event):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QPainter, QPen

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0f172a"))
        source = None
        if not self.before.isNull():
            source = self.before
        elif not self.after.isNull():
            source = self.after
        if source is None:
            painter.setPen(QColor("#cbd5e1"))
            painter.drawText(self.rect(), Qt.AlignCenter, "\u4fee\u590d\u7ed3\u679c\u5bf9\u6bd4\u9884\u89c8")
            return
        target = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        scaled_w = int(source.width() * self.zoom)
        scaled_h = int(source.height() * self.zoom)
        scaled = source.scaled(scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = target.x() + (target.width() - scaled.width()) / 2
        y = target.y() + (target.height() - scaled.height()) / 2
        image_rect = QRectF(x, y, scaled.width(), scaled.height())
        if not self.after.isNull():
            painter.drawPixmap(image_rect.toRect(), self.after.scaled(scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if not self.before.isNull():
            clip_width = image_rect.width() * self.position / 100
            painter.save()
            painter.setClipRect(QRectF(image_rect.x(), image_rect.y(), clip_width, image_rect.height()))
            scaled_before = self.before.scaled(scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(image_rect.toRect(), scaled_before)
            painter.restore()
        divider_x = image_rect.x() + image_rect.width() * self.position / 100
        painter.setPen(QPen(QColor("#f8fafc"), 2))
        painter.drawLine(int(divider_x), int(image_rect.y()), int(divider_x), int(image_rect.bottom()))
        painter.setBrush(QColor("#2563eb"))
        painter.setPen(QPen(QColor("#f8fafc"), 3))
        painter.drawEllipse(int(divider_x) - 8, int(image_rect.center().y()) - 8, 16, 16)
        painter.setPen(QColor("#e2e8f0"))
        painter.drawText(image_rect.adjusted(10, 10, -10, -10), Qt.AlignTop | Qt.AlignLeft, "\u4fee\u590d\u524d")
        painter.drawText(image_rect.adjusted(10, 10, -10, -10), Qt.AlignTop | Qt.AlignRight, "\u4fee\u590d\u540e")


class PhotoWizard(QWidget):
    def __init__(self):
        super().__init__()
        self._states: dict[str, PhotoState] = {}
        self._current_id: str | None = None
        self._runner = PipelineRunner()
        self._runner.finished.connect(self._on_finished)
        self._runner.error.connect(self._on_error)
        self._export_pending = False

        layout = QVBoxLayout(self)

        nav = QHBoxLayout()
        self._prev_btn = QPushButton("\u2190 \u4e0a\u4e00\u5f20")
        self._prev_btn.clicked.connect(self._prev_photo)
        nav.addWidget(self._prev_btn)
        self._photo_label = QLabel("\u672a\u9009\u62e9\u7167\u7247")
        self._photo_label.setAlignment(Qt.AlignCenter)
        nav.addWidget(self._photo_label, 1)
        self._next_btn = QPushButton("\u4e0b\u4e00\u5f20 \u2192")
        self._next_btn.clicked.connect(self._next_photo)
        nav.addWidget(self._next_btn)
        layout.addLayout(nav)

        ops = QGroupBox("Operations")
        ops_layout = QVBoxLayout(ops)

        rotate_row = QHBoxLayout()
        self._rotate_cb = QCheckBox("Rotate")
        self._rotate_cb.toggled.connect(self._on_param_changed)
        rotate_row.addWidget(self._rotate_cb)
        self._rotate_mode = QComboBox()
        self._rotate_mode.addItems(["auto detect", "0\u00b0", "90\u00b0", "180\u00b0", "270\u00b0"])
        self._rotate_mode.currentIndexChanged.connect(self._on_rotate_mode_changed)
        rotate_row.addWidget(self._rotate_mode, 1)
        ops_layout.addLayout(rotate_row)

        denoise_row = QHBoxLayout()
        self._denoise_cb = QCheckBox("Denoise")
        self._denoise_cb.toggled.connect(self._on_param_changed)
        denoise_row.addWidget(self._denoise_cb)
        denoise_row.addWidget(QLabel("strength"))
        self._denoise_slider = QSlider(Qt.Horizontal)
        self._denoise_slider.setRange(10, 100)
        self._denoise_slider.setValue(50)
        self._denoise_slider.valueChanged.connect(self._on_param_changed)
        denoise_row.addWidget(self._denoise_slider, 1)
        self._denoise_value = QLabel("0.5")
        self._denoise_slider.valueChanged.connect(lambda v: self._denoise_value.setText(f"{v / 100:.1f}"))
        denoise_row.addWidget(self._denoise_value)
        ops_layout.addLayout(denoise_row)

        inpaint_row = QHBoxLayout()
        self._inpaint_cb = QCheckBox("Inpaint")
        self._inpaint_cb.toggled.connect(self._on_param_changed)
        inpaint_row.addWidget(self._inpaint_cb)
        inpaint_row.addWidget(QLabel("strength"))
        self._inpaint_strength = QComboBox()
        self._inpaint_strength.addItems(["low", "medium", "high"])
        self._inpaint_strength.setCurrentIndex(1)
        self._inpaint_strength.currentTextChanged.connect(self._on_param_changed)
        inpaint_row.addWidget(self._inpaint_strength, 1)
        ops_layout.addLayout(inpaint_row)

        clean_row = QHBoxLayout()
        self._clean_cb = QCheckBox("Clean")
        self._clean_cb.toggled.connect(self._on_param_changed)
        clean_row.addWidget(self._clean_cb)
        clean_row.addWidget(QLabel("strength"))
        self._clean_slider = QSlider(Qt.Horizontal)
        self._clean_slider.setRange(10, 100)
        self._clean_slider.setValue(50)
        self._clean_slider.valueChanged.connect(self._on_param_changed)
        clean_row.addWidget(self._clean_slider, 1)
        self._clean_value = QLabel("0.5")
        self._clean_slider.valueChanged.connect(lambda v: self._clean_value.setText(f"{v / 100:.1f}"))
        clean_row.addWidget(self._clean_value)
        ops_layout.addLayout(clean_row)

        enhance_row = QHBoxLayout()
        self._enhance_cb = QCheckBox("Enhance")
        self._enhance_cb.toggled.connect(self._on_param_changed)
        enhance_row.addWidget(self._enhance_cb)
        enhance_row.addWidget(QLabel("strength"))
        self._enhance_slider = QSlider(Qt.Horizontal)
        self._enhance_slider.setRange(10, 100)
        self._enhance_slider.setValue(50)
        self._enhance_slider.valueChanged.connect(self._on_param_changed)
        enhance_row.addWidget(self._enhance_slider, 1)
        self._enhance_value = QLabel("0.5")
        self._enhance_slider.valueChanged.connect(lambda v: self._enhance_value.setText(f"{v / 100:.1f}"))
        enhance_row.addWidget(self._enhance_value)
        ops_layout.addLayout(enhance_row)

        face_row = QHBoxLayout()
        self._face_cb = QCheckBox("Face Restore")
        self._face_cb.toggled.connect(self._on_param_changed)
        face_row.addWidget(self._face_cb)
        face_row.addWidget(QLabel("fidelity"))
        self._face_slider = QSlider(Qt.Horizontal)
        self._face_slider.setRange(0, 100)
        self._face_slider.setValue(70)
        self._face_slider.valueChanged.connect(self._on_param_changed)
        face_row.addWidget(self._face_slider, 1)
        self._face_value = QLabel("0.7")
        self._face_slider.valueChanged.connect(lambda v: self._face_value.setText(f"{v / 100:.1f}"))
        face_row.addWidget(self._face_value)
        ops_layout.addLayout(face_row)

        sr_row = QHBoxLayout()
        self._sr_cb = QCheckBox("Super Res")
        self._sr_cb.toggled.connect(self._on_param_changed)
        sr_row.addWidget(self._sr_cb)
        sr_row.addWidget(QLabel("scale"))
        self._sr_scale = QComboBox()
        self._sr_scale.addItems(["2x", "4x"])
        self._sr_scale.currentTextChanged.connect(self._on_param_changed)
        sr_row.addWidget(self._sr_scale, 1)
        ops_layout.addLayout(sr_row)

        layout.addWidget(ops)

        zoom_row = QHBoxLayout()
        zoom_row.addStretch(1)
        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setRange(10, 500)
        self._zoom_slider.setValue(100)
        self._zoom_slider.valueChanged.connect(lambda v: self._compare.set_zoom(v / 100.0))
        zoom_row.addWidget(QLabel("Zoom"))
        zoom_row.addWidget(self._zoom_slider)
        self._zoom_label = QLabel("100%")
        self._zoom_slider.valueChanged.connect(lambda v: self._zoom_label.setText(f"{v}%"))
        zoom_row.addWidget(self._zoom_label)
        zoom_row.addStretch(1)
        layout.addLayout(zoom_row)

        self._compare = BeforeAfterView()
        layout.addWidget(self._compare, 1)

        self._compare_slider = QSlider(Qt.Horizontal)
        self._compare_slider.setRange(1, 99)
        self._compare_slider.setValue(50)
        self._compare_slider.valueChanged.connect(self._compare.set_position)
        layout.addWidget(self._compare_slider)

        export_btn = QPushButton("Export This Photo")
        export_btn.clicked.connect(self._export_current)
        layout.addWidget(export_btn)

    def set_photos(self, crop_outputs: list[dict], scan_stem: str = ""):
        self._states.clear()
        for item in crop_outputs:
            region = item["region"]
            crop_path = item["crop"]
            oriented_path = item["oriented"]
            state = PhotoState(
                region_id=region.id,
                original_path=oriented_path,
                output_dir=crop_path.parent.parent / "wizard",
                scan_stem=scan_stem,
            )
            state.output_dir.mkdir(parents=True, exist_ok=True)
            state.steps["orientation"]["path"] = oriented_path
            self._states[region.id] = state
        self._current_id = None
        self._refresh_nav()

    def _refresh_nav(self):
        ids = list(self._states.keys())
        if not ids:
            self._photo_label.setText("\u672a\u9009\u62e9\u7167\u7247")
            self._compare.set_images(None, None)
            return
        if self._current_id not in self._states:
            self._current_id = ids[0]
        idx = ids.index(self._current_id)
        self._photo_label.setText(f"Photo {idx + 1} / {len(ids)}: {self._current_id}")
        self._prev_btn.setEnabled(idx > 0)
        self._next_btn.setEnabled(idx < len(ids) - 1)
        self._load_state()

    def _load_state(self):
        if self._current_id is None:
            return
        s = self._states[self._current_id]
        self._rotate_cb.blockSignals(True)
        self._inpaint_cb.blockSignals(True)
        self._face_cb.blockSignals(True)
        self._sr_cb.blockSignals(True)
        self._denoise_cb.blockSignals(True)
        self._clean_cb.blockSignals(True)
        self._enhance_cb.blockSignals(True)
        self._inpaint_strength.blockSignals(True)
        self._face_slider.blockSignals(True)
        self._sr_scale.blockSignals(True)
        self._denoise_slider.blockSignals(True)
        self._clean_slider.blockSignals(True)
        self._enhance_slider.blockSignals(True)
        self._rotate_mode.blockSignals(True)

        self._rotate_cb.setChecked(s.steps["orientation"]["enabled"])
        self._denoise_cb.setChecked(s.steps["denoise"]["enabled"])
        self._inpaint_cb.setChecked(s.steps["inpaint"]["enabled"])
        self._clean_cb.setChecked(s.steps["clean"]["enabled"])
        self._enhance_cb.setChecked(s.steps["enhance"]["enabled"])
        self._face_cb.setChecked(s.steps["face_restore"]["enabled"])
        self._sr_cb.setChecked(s.steps["super_res"]["enabled"])
        strength = s.steps["inpaint"]["params"].get("strength", "medium")
        idx = self._inpaint_strength.findText(strength)
        if idx >= 0:
            self._inpaint_strength.setCurrentIndex(idx)
        d_strength = s.steps["denoise"]["params"].get("strength", 0.5)
        self._denoise_slider.setValue(int(d_strength * 100))
        self._denoise_value.setText(f"{d_strength:.1f}")
        c_strength = s.steps["clean"]["params"].get("strength", 0.5)
        self._clean_slider.setValue(int(c_strength * 100))
        self._clean_value.setText(f"{c_strength:.1f}")
        e_strength = s.steps["enhance"]["params"].get("strength", 0.5)
        self._enhance_slider.setValue(int(e_strength * 100))
        self._enhance_value.setText(f"{e_strength:.1f}")
        fidelity = s.steps["face_restore"]["params"].get("fidelity", 0.7)
        self._face_slider.setValue(int(fidelity * 100))
        self._face_value.setText(f"{fidelity:.1f}")
        manual_angle = s.steps["orientation"]["params"].get("manual_angle", -1)
        if manual_angle >= 0:
            angle_map = {0: 1, 90: 2, 180: 3, 270: 4}
            self._rotate_mode.setCurrentIndex(angle_map.get(manual_angle, 1))
        else:
            self._rotate_mode.setCurrentIndex(0)

        self._rotate_cb.blockSignals(False)
        self._denoise_cb.blockSignals(False)
        self._inpaint_cb.blockSignals(False)
        self._clean_cb.blockSignals(False)
        self._enhance_cb.blockSignals(False)
        self._face_cb.blockSignals(False)
        self._sr_cb.blockSignals(False)
        self._inpaint_strength.blockSignals(False)
        self._face_slider.blockSignals(False)
        self._sr_scale.blockSignals(False)
        self._denoise_slider.blockSignals(False)
        self._clean_slider.blockSignals(False)
        self._enhance_slider.blockSignals(False)
        self._rotate_mode.blockSignals(False)

        self._show_comparison()

    def _show_comparison(self):
        if self._current_id is None:
            return
        s = self._states[self._current_id]
        orientation_step = s.steps.get("orientation")
        before = (orientation_step["path"] if orientation_step and orientation_step["enabled"] and orientation_step["path"] else s.original_path)
        after = s.final_path() or before
        self._compare.set_images(before, after)

    def _on_rotate_mode_changed(self, idx: int):
        if self._current_id is None:
            return
        s = self._states[self._current_id]
        s.steps["orientation"]["path"] = None
        if idx == 0:
            s.steps["orientation"]["params"].pop("manual_angle", None)
        else:
            angles = [0, 0, 90, 180, 270]
            s.steps["orientation"]["params"]["manual_angle"] = angles[idx]
        self._on_param_changed()

    def _on_param_changed(self, *args):
        if self._current_id is None:
            return
        s = self._states[self._current_id]
        s.enable("orientation", self._rotate_cb.isChecked())
        s.enable("denoise", self._denoise_cb.isChecked())
        s.enable("inpaint", self._inpaint_cb.isChecked())
        s.enable("clean", self._clean_cb.isChecked())
        s.enable("enhance", self._enhance_cb.isChecked())
        s.enable("face_restore", self._face_cb.isChecked())
        s.enable("super_res", self._sr_cb.isChecked())
        s.set_param("denoise", "strength", self._denoise_slider.value() / 100.0)
        s.set_param("inpaint", "strength", self._inpaint_strength.currentText())
        s.set_param("clean", "strength", self._clean_slider.value() / 100.0)
        s.set_param("enhance", "strength", self._enhance_slider.value() / 100.0)
        s.set_param("face_restore", "fidelity", self._face_slider.value() / 100.0)
        scale_text = self._sr_scale.currentText()
        s.set_param("super_res", "scale", int(scale_text.replace("x", "")))
        self._runner.schedule(s)

    def _on_finished(self, region_id: str, final_path: Path):
        if region_id == self._current_id:
            self._show_comparison()
            if getattr(self, '_export_pending', False):
                self._export_pending = False
                self._do_export()

    def _on_error(self, region_id: str, error_msg: str):
        if region_id == self._current_id:
            self._compare.set_images(None, None)
            self._photo_label.setText(f"Error: {error_msg}")

    def _prev_photo(self):
        ids = list(self._states.keys())
        if not ids or self._current_id is None:
            return
        idx = ids.index(self._current_id)
        if idx > 0:
            self._current_id = ids[idx - 1]
            self._refresh_nav()

    def _next_photo(self):
        ids = list(self._states.keys())
        if not ids or self._current_id is None:
            return
        idx = ids.index(self._current_id)
        if idx < len(ids) - 1:
            self._current_id = ids[idx + 1]
            self._refresh_nav()

    def _export_current(self):
        if self._current_id is None:
            return
        s = self._states[self._current_id]
        self._export_pending = True
        self._runner.schedule(s)

    def _do_export(self):
        s = self._states[self._current_id]
        final = s.final_path()
        if final and final.exists():
            from shutil import copy2
            export_dir = s.output_dir.parent / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            prefix = f"{s.scan_stem}_" if s.scan_stem else ""
            dst = export_dir / f"{prefix}{s.region_id}_restored.png"
            copy2(final, dst)
            self._show_toast(f"Exported: {dst.name}")
        else:
            self._show_toast("Export failed")

    def _show_toast(self, msg: str):
        toast = QLabel(msg, self)
        toast.setStyleSheet("background: #1e293b; color: #e2e8f0; padding: 12px 24px; border-radius: 6px; font-size: 14px;")
        toast.setAlignment(Qt.AlignCenter)
        toast.adjustSize()
        toast.move((self.width() - toast.width()) // 2, self.height() - 80)
        toast.show()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, toast.hide)
        QTimer.singleShot(2200, toast.deleteLater)
