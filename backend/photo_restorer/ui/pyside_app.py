from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable
import math

try:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QAction, QColor, QPainter, QPen, QPixmap, QPolygonF
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QGraphicsEllipseItem,
        QGraphicsItem,
        QGraphicsPixmapItem,
        QGraphicsPolygonItem,
        QGraphicsScene,
        QGraphicsView,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSlider,
        QSpinBox,
        QSplitter,
        QStatusBar,
        QVBoxLayout,
        QWidget,
        QTabWidget,
        QGroupBox,
        QScrollArea,
        QSizePolicy,
    )
except Exception as exc:  # pragma: no cover
    raise RuntimeError("PySide6 is required. Install with: pip install -e '.[desktop]'") from exc

from photo_restorer.core.crop import crop_and_rectify
from photo_restorer.core.detect import detect_photo_regions
from photo_restorer.core.orientation import OrientationResult, apply_orientation, detect_orientation
from photo_restorer.core.pipeline_steps import DEFAULT_PIPELINE
from photo_restorer.core.types import PhotoRegion

POINT_RADIUS = 6
PRESETS = [
    ("family_photo_default", "家庭照片默认"),
    ("conservative_archive", "档案保守"),
    ("aggressive_restore", "翻新增强"),
    ("ai_high_restore", "AI 高修复（接口预留）"),
    ("crop_only", "只裁切整理"),
]

class BeforeAfterView(QWidget):
    def __init__(self):
        super().__init__()
        self.before = QPixmap()
        self.after = QPixmap()
        self.position = 50
        self.setMinimumHeight(320)
        self.setStyleSheet("background: #0f172a; border: 1px solid #64748b;")

    def set_images(self, before_path: Path | None, after_path: Path | None):
        self.before = QPixmap(str(before_path)) if before_path else QPixmap()
        self.after = QPixmap(str(after_path)) if after_path else QPixmap()
        self.update()

    def set_position(self, value: int):
        self.position = max(1, min(99, value))
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0f172a"))
        if self.before.isNull() and self.after.isNull():
            painter.setPen(QColor("#cbd5e1"))
            painter.drawText(self.rect(), Qt.AlignCenter, "修复结果对比预览")
            return
        source = self.before if not self.before.isNull() else self.after
        target = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        scaled = source.scaled(target.size().toSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = target.x() + (target.width() - scaled.width()) / 2
        y = target.y() + (target.height() - scaled.height()) / 2
        image_rect = QRectF(x, y, scaled.width(), scaled.height())
        if not self.after.isNull():
            painter.drawPixmap(image_rect.toRect(), self.after)
        if not self.before.isNull():
            clip_width = image_rect.width() * self.position / 100
            painter.save()
            painter.setClipRect(QRectF(image_rect.x(), image_rect.y(), clip_width, image_rect.height()))
            painter.drawPixmap(image_rect.toRect(), self.before)
            painter.restore()
        divider_x = image_rect.x() + image_rect.width() * self.position / 100
        painter.setPen(QPen(QColor("#f8fafc"), 2))
        painter.drawLine(int(divider_x), int(image_rect.y()), int(divider_x), int(image_rect.bottom()))
        painter.setBrush(QColor("#2563eb"))
        painter.setPen(QPen(QColor("#f8fafc"), 3))
        painter.drawEllipse(QPointF(divider_x, image_rect.center().y()), 15, 15)
        painter.setPen(QColor("#e2e8f0"))
        painter.drawText(image_rect.adjusted(10, 10, -10, -10), Qt.AlignTop | Qt.AlignLeft, "修复前")
        painter.drawText(image_rect.adjusted(10, 10, -10, -10), Qt.AlignTop | Qt.AlignRight, "修复后")

class DraggablePoint(QGraphicsEllipseItem):
    def __init__(self, polygon_item: "EditablePolygonItem", index: int, point: QPointF):
        super().__init__(-POINT_RADIUS, -POINT_RADIUS, POINT_RADIUS * 2, POINT_RADIUS * 2)
        self.polygon_item = polygon_item
        self.index = index
        self.setPos(point)
        self.setBrush(QColor("#f97316"))
        self.setPen(QPen(QColor("#111827"), 1))
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(10)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.polygon_item.update_from_handles()
        return super().itemChange(change, value)

class EditablePolygonItem(QGraphicsPolygonItem):
    def __init__(self, region: PhotoRegion):
        self.region = region
        polygon = QPolygonF([QPointF(x, y) for x, y in region.polygon])
        super().__init__(polygon)
        self.setPen(QPen(QColor("#22c55e"), 3))
        self.setBrush(QColor(34, 197, 94, 35))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(5)
        self.handles: list[DraggablePoint] = []

    def add_handles(self, scene: QGraphicsScene):
        for i, point in enumerate(self.polygon()):
            handle = DraggablePoint(self, i, point)
            self.handles.append(handle)
            scene.addItem(handle)

    def update_from_handles(self):
        if not self.handles:
            return
        points = [h.pos() for h in self.handles]
        self.setPolygon(QPolygonF(points))
        self.region.polygon = [(float(p.x()), float(p.y())) for p in points]

    def set_highlight(self, active: bool):
        self.setPen(QPen(QColor("#38bdf8" if active else "#22c55e"), 4 if active else 3))

class ImageCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item: QGraphicsPixmapItem | None = None
        self.polygons: list[EditablePolygonItem] = []
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def load_image(self, path: Path):
        self.scene.clear()
        self.polygons = []
        pixmap = QPixmap(str(path))
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def set_regions(self, regions: Iterable[PhotoRegion]):
        for item in self.polygons:
            for handle in item.handles:
                self.scene.removeItem(handle)
            self.scene.removeItem(item)
        self.polygons = []
        for region in regions:
            item = EditablePolygonItem(region)
            self.scene.addItem(item)
            item.add_handles(self.scene)
            self.polygons.append(item)

    def highlight(self, index: int):
        for i, item in enumerate(self.polygons):
            item.set_highlight(i == index)

    def remove_region(self, index: int):
        if not (0 <= index < len(self.polygons)):
            return
        item = self.polygons.pop(index)
        for handle in item.handles:
            self.scene.removeItem(handle)
        self.scene.removeItem(item)

    def add_manual_region(self):
        rect = self.scene.sceneRect()
        w, h = rect.width(), rect.height()
        margin_x, margin_y = w * 0.25, h * 0.25
        region = PhotoRegion(
            id=f"manual_{len(self.polygons)+1:03d}",
            polygon=[(margin_x, margin_y), (w - margin_x, margin_y), (w - margin_x, h - margin_y), (margin_x, h - margin_y)],
            confidence=1.0,
            source="manual",
        )
        item = EditablePolygonItem(region)
        self.scene.addItem(item)
        item.add_handles(self.scene)
        self.polygons.append(item)
        return region

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photo Restorer - PySide MVP")
        self.resize(1400, 900)
        self.image_path: Path | None = None
        self.regions: list[PhotoRegion] = []
        self.crop_outputs: list[dict] = []
        self.restore_outputs: list[dict] = []
        self.canvas = ImageCanvas()
        self.region_list = QListWidget()
        self.crop_list = QListWidget()
        self.result_list = QListWidget()
        self.compare_view = BeforeAfterView()
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._build_ui()
        self._build_menu()

    def _build_menu(self):
        open_action = QAction("打开图片", self)
        open_action.triggered.connect(self.open_image)
        self.menuBar().addAction(open_action)

    def _build_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._prepare_tab(), "1. 识别 / 裁剪 / 方向")
        self.tabs.addTab(self._restore_tab(), "2. 选择修复效果")
        self.tabs.addTab(self._compare_tab(), "3. 前后对比")
        self.setCentralWidget(self.tabs)

    def _prepare_tab(self):
        splitter = QSplitter()
        splitter.addWidget(self.canvas)
        splitter.addWidget(self._side_panel())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        return splitter

    def _restore_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel("从第一个 tab 得到的多张照片中选择要修复的图片，并选择修复效果。")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("修复方案"))
        self.preset_combo = QComboBox()
        for value, label in PRESETS:
            self.preset_combo.addItem(label, value)
        preset_row.addWidget(self.preset_combo)
        layout.addLayout(preset_row)

        pipe_group = QGroupBox("Pipeline 步骤")
        pipe_layout = QVBoxLayout(pipe_group)
        self.step_checks: dict[str, QCheckBox] = {}
        for step in DEFAULT_PIPELINE:
            cb = QCheckBox(step.label)
            cb.setChecked(step.enabled)
            self.step_checks[step.key] = cb
            pipe_layout.addWidget(cb)
        self.manual_rotation = QSpinBox(); self.manual_rotation.setRange(-270, 270); self.manual_rotation.setSingleStep(90); self.manual_rotation.setValue(0)
        rotate_row = QHBoxLayout(); rotate_row.addWidget(QLabel("手动旋转角度")); rotate_row.addWidget(self.manual_rotation); pipe_layout.addLayout(rotate_row)
        layout.addWidget(pipe_group)

        select_row = QHBoxLayout()
        all_btn = QPushButton("全选")
        all_btn.clicked.connect(lambda: self._set_all_crop_checks(True))
        none_btn = QPushButton("清空")
        none_btn.clicked.connect(lambda: self._set_all_crop_checks(False))
        run_btn = QPushButton("修复选中照片")
        run_btn.clicked.connect(self.run_selected_restores)
        select_row.addWidget(all_btn); select_row.addWidget(none_btn); select_row.addStretch(1); select_row.addWidget(run_btn)
        layout.addLayout(select_row)

        self.crop_list.itemSelectionChanged.connect(self.preview_selected_crop)
        layout.addWidget(self.crop_list, 1)
        return page

    def _compare_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel("查看修复前/修复后效果；拖动滑杆移动中间竖轴。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        splitter = QSplitter()
        self.result_list.currentRowChanged.connect(self.show_compare_result)
        splitter.addWidget(self.result_list)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.compare_view, 1)
        self.compare_slider = QSlider(Qt.Horizontal)
        self.compare_slider.setRange(5, 95)
        self.compare_slider.setValue(50)
        self.compare_slider.valueChanged.connect(self.compare_view.set_position)
        right_layout.addWidget(self.compare_slider)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        layout.addWidget(splitter, 1)
        return page

    def _side_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        open_btn = QPushButton("打开扫描图")
        open_btn.clicked.connect(self.open_image)
        layout.addWidget(open_btn)

        detect_group = QGroupBox("裁切识别参数")
        detect_layout = QVBoxLayout(detect_group)
        self.min_area = QDoubleSpinBox(); self.min_area.setRange(0.001, 0.2); self.min_area.setSingleStep(0.005); self.min_area.setValue(0.006)
        self.canny_low = QSpinBox(); self.canny_low.setRange(1, 255); self.canny_low.setValue(25)
        self.canny_high = QSpinBox(); self.canny_high.setRange(1, 255); self.canny_high.setValue(120)
        self.blur = QSpinBox(); self.blur.setRange(1, 31); self.blur.setSingleStep(2); self.blur.setValue(5)
        self.max_area = QDoubleSpinBox(); self.max_area.setRange(0.05, 1.0); self.max_area.setSingleStep(0.05); self.max_area.setValue(0.95)
        self.morph = QSpinBox(); self.morph.setRange(0, 7); self.morph.setValue(2)
        self.approx = QDoubleSpinBox(); self.approx.setRange(0.005, 0.08); self.approx.setSingleStep(0.005); self.approx.setValue(0.02)
        self.expand_px = QSpinBox(); self.expand_px.setRange(-50, 100); self.expand_px.setValue(0)
        self.auto_redetect = QCheckBox("参数变化后自动重新识别")
        for widget in [self.min_area, self.max_area, self.canny_low, self.canny_high, self.blur, self.morph, self.approx]:
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(self.detect_regions_if_auto)
        for label, widget in [
            ("最小面积比例", self.min_area), ("最大面积比例", self.max_area), ("Canny low", self.canny_low), ("Canny high", self.canny_high),
            ("模糊核", self.blur), ("闭运算次数", self.morph), ("四边形拟合", self.approx), ("裁切扩边/羽化(px)", self.expand_px)
        ]:
            row = QHBoxLayout(); row.addWidget(QLabel(label)); row.addWidget(widget); detect_layout.addLayout(row)
        detect_btn = QPushButton("重新识别照片")
        detect_btn.clicked.connect(self.detect_regions)
        detect_layout.addWidget(self.auto_redetect)
        detect_layout.addWidget(detect_btn)
        layout.addWidget(detect_group)

        edit_group = QGroupBox("识别结果 / 手工调点")
        edit_layout = QVBoxLayout(edit_group)
        self.region_list.currentRowChanged.connect(self.canvas.highlight)
        edit_layout.addWidget(self.region_list)
        add_btn = QPushButton("手工新增四点框")
        add_btn.clicked.connect(self.add_manual_region)
        delete_btn = QPushButton("删除选中框")
        delete_btn.clicked.connect(self.delete_selected_region)
        export_btn = QPushButton("裁切选中照片并预览")
        export_btn.clicked.connect(self.crop_selected)
        edit_layout.addWidget(add_btn); edit_layout.addWidget(delete_btn); edit_layout.addWidget(export_btn)
        self.crop_preview = QLabel("裁切预览")
        self.crop_preview.setAlignment(Qt.AlignCenter)
        self.crop_preview.setMinimumHeight(180)
        self.crop_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.crop_preview.setStyleSheet("border: 1px solid #64748b; background: #0f172a; color: #cbd5e1;")
        edit_layout.addWidget(self.crop_preview)
        layout.addWidget(edit_group)

        next_group = QGroupBox("进入修复")
        next_layout = QVBoxLayout(next_group)
        crop_all_btn = QPushButton("裁切全部照片并进入修复选择")
        crop_all_btn.clicked.connect(self.crop_all_for_restore)
        next_layout.addWidget(crop_all_btn)
        layout.addWidget(next_group)

        layout.addStretch(1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(panel)
        return scroll

    def open_image(self):
        filename, _ = QFileDialog.getOpenFileName(self, "选择扫描图", "", "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp)")
        if not filename:
            return
        self.image_path = Path(filename)
        self.canvas.load_image(self.image_path)
        self.regions = []
        self.crop_outputs = []
        self.restore_outputs = []
        self.region_list.clear()
        self.crop_list.clear()
        self.result_list.clear()
        self.compare_view.set_images(None, None)
        self.status.showMessage(f"已打开：{self.image_path}")

    def detect_regions(self):
        if not self.image_path:
            QMessageBox.warning(self, "未打开图片", "请先打开一张扫描图。")
            return
        try:
            self.regions = detect_photo_regions(
                self.image_path,
                min_area_ratio=float(self.min_area.value()),
                max_area_ratio=float(self.max_area.value()),
                canny_low=int(self.canny_low.value()),
                canny_high=int(self.canny_high.value()),
                blur_kernel=int(self.blur.value()),
                morph_iterations=int(self.morph.value()),
                approx_epsilon_ratio=float(self.approx.value()),
            )
        except Exception as exc:
            QMessageBox.critical(self, "识别失败", str(exc))
            return
        self.canvas.set_regions(self.regions)
        self._refresh_region_list()
        self.status.showMessage(f"识别到 {len(self.regions)} 张照片。可调参数后重新识别，或拖动橙色点手工调整。")

    def detect_regions_if_auto(self):
        if self.auto_redetect.isChecked() and self.image_path:
            self.detect_regions()

    def add_manual_region(self):
        if not self.image_path:
            QMessageBox.warning(self, "未打开图片", "请先打开一张扫描图。")
            return
        region = self.canvas.add_manual_region()
        self.regions.append(region)
        self._refresh_region_list()
        self.region_list.setCurrentRow(len(self.regions) - 1)

    def _refresh_region_list(self):
        self.region_list.clear()
        for r in self.regions:
            self.region_list.addItem(f"{r.id}  {r.source}  conf={r.confidence:.2f}")

    def selected_region(self) -> PhotoRegion | None:
        row = self.region_list.currentRow()
        if 0 <= row < len(self.regions):
            return self.regions[row]
        return None

    def delete_selected_region(self):
        row = self.region_list.currentRow()
        if not (0 <= row < len(self.regions)):
            QMessageBox.warning(self, "未选择照片", "请先在列表中选择要删除的框。")
            return
        self.regions.pop(row)
        self.canvas.remove_region(row)
        self._refresh_region_list()
        if self.regions:
            self.region_list.setCurrentRow(min(row, len(self.regions) - 1))
        self.status.showMessage("已删除选中识别框。")

    def region_for_crop(self, region: PhotoRegion) -> PhotoRegion:
        expand = float(self.expand_px.value())
        if expand == 0:
            return region
        cx = sum(x for x, _ in region.polygon) / len(region.polygon)
        cy = sum(y for _, y in region.polygon) / len(region.polygon)
        points = []
        for x, y in region.polygon:
            dx, dy = x - cx, y - cy
            length = math.hypot(dx, dy) or 1.0
            points.append((x + expand * dx / length, y + expand * dy / length))
        return PhotoRegion(id=region.id, polygon=points, confidence=region.confidence, source=region.source)

    def crop_selected(self):
        if not self.image_path:
            return
        region = self.selected_region()
        if not region:
            QMessageBox.warning(self, "未选择照片", "请先在列表中选择一张照片。")
            return
        out_dir = Path("outputs/pyside-crops")
        out = out_dir / f"{self.image_path.stem}_{region.id}.png"
        try:
            crop_and_rectify(self.image_path, self.region_for_crop(region), out)
        except Exception as exc:
            QMessageBox.critical(self, "裁切失败", str(exc))
            return
        pixmap = QPixmap(str(out))
        if not pixmap.isNull():
            self.crop_preview.setPixmap(pixmap.scaled(self.crop_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.status.showMessage(f"已裁切：{out}")

    def crop_all_for_restore(self):
        if not self.image_path:
            QMessageBox.warning(self, "未打开图片", "请先打开一张扫描图。")
            return
        if not self.regions:
            QMessageBox.warning(self, "没有识别结果", "请先识别照片，或手工新增四点框。")
            return
        out_dir = Path("outputs/pyside-crops")
        out_dir.mkdir(parents=True, exist_ok=True)
        self.crop_outputs = []
        try:
            for region in self.regions:
                crop_path = out_dir / f"{self.image_path.stem}_{region.id}_crop.png"
                oriented_path = out_dir / f"{self.image_path.stem}_{region.id}_oriented.png"
                crop_and_rectify(self.image_path, self.region_for_crop(region), crop_path)
                orientation = detect_orientation(crop_path)
                apply_orientation(crop_path, oriented_path, orientation)
                self.crop_outputs.append({
                    "region": region,
                    "crop": crop_path,
                    "oriented": oriented_path,
                    "orientation": orientation,
                })
        except Exception as exc:
            QMessageBox.critical(self, "裁切失败", str(exc))
            return
        self._refresh_crop_list()
        self.tabs.setCurrentIndex(1)
        self.status.showMessage(f"已裁切并校正 {len(self.crop_outputs)} 张照片，可选择修复效果。")

    def _refresh_crop_list(self):
        self.crop_list.clear()
        for item in self.crop_outputs:
            orientation = item["orientation"]
            region = item["region"]
            row = QListWidgetItem(f"{region.id}  方向={orientation.angle}°  conf={orientation.confidence:.2f}")
            row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
            row.setCheckState(Qt.Checked)
            self.crop_list.addItem(row)
        if self.crop_outputs:
            self.crop_list.setCurrentRow(0)

    def _set_all_crop_checks(self, checked: bool):
        for i in range(self.crop_list.count()):
            self.crop_list.item(i).setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def preview_selected_crop(self):
        row = self.crop_list.currentRow()
        if not (0 <= row < len(self.crop_outputs)):
            return
        pixmap = QPixmap(str(self.crop_outputs[row]["oriented"]))
        if not pixmap.isNull():
            self.crop_preview.setPixmap(pixmap.scaled(self.crop_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def selected_crop_indexes(self) -> list[int]:
        return [i for i in range(self.crop_list.count()) if self.crop_list.item(i).checkState() == Qt.Checked]

    def run_selected_restores(self):
        indexes = self.selected_crop_indexes()
        if not indexes:
            QMessageBox.warning(self, "未选择照片", "请至少选择一张要修复的照片。")
            return
        if not self.image_path:
            return
        enabled = [key for key, cb in self.step_checks.items() if cb.isChecked()]
        preset = self.preset_combo.currentData()
        out_dir = Path("outputs/pyside-pipeline")
        out_dir.mkdir(parents=True, exist_ok=True)
        self.restore_outputs = []
        try:
            for i in indexes:
                item = self.crop_outputs[i]
                region = item["region"]
                before_path = item["oriented"]
                final_path = out_dir / f"{self.image_path.stem}_{region.id}_final.png"
                angle = int(self.manual_rotation.value()) if "orientation" in enabled else 0
                if angle:
                    apply_orientation(before_path, final_path, OrientationResult(angle=angle, confidence=1.0, evidence=["manual_rotation"]))
                else:
                    from shutil import copy2
                    copy2(before_path, final_path)
                metadata = {
                    "source": str(self.image_path),
                    "region": region.__dict__,
                    "preset": preset,
                    "enabled_steps": enabled,
                    "before": str(before_path),
                    "final": str(final_path),
                }
                (out_dir / f"{self.image_path.stem}_{region.id}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
                self.restore_outputs.append({"region": region, "before": before_path, "after": final_path, "metadata": metadata})
        except Exception as exc:
            QMessageBox.critical(self, "修复失败", str(exc))
            return
        self._refresh_result_list()
        self.tabs.setCurrentIndex(2)
        self.status.showMessage(f"修复完成：{len(self.restore_outputs)} 张照片。当前 AI 修复步骤仍为占位，已支持前后对比。")

    def _refresh_result_list(self):
        self.result_list.clear()
        for item in self.restore_outputs:
            self.result_list.addItem(f"{item['region'].id}  {item['after']}")
        if self.restore_outputs:
            self.result_list.setCurrentRow(0)

    def show_compare_result(self, row: int):
        if not (0 <= row < len(self.restore_outputs)):
            self.compare_view.set_images(None, None)
            return
        item = self.restore_outputs[row]
        self.compare_view.set_images(item["before"], item["after"])

    def run_pipeline_placeholder(self):
        region = self.selected_region()
        if not self.image_path or not region:
            QMessageBox.warning(self, "未选择照片", "请先打开图片并选择照片。")
            return
        enabled = [key for key, cb in self.step_checks.items() if cb.isChecked()]
        out_dir = Path("outputs/pyside-pipeline")
        out_dir.mkdir(parents=True, exist_ok=True)
        crop_path = out_dir / f"{self.image_path.stem}_{region.id}_crop.png"
        final_path = out_dir / f"{self.image_path.stem}_{region.id}_final.png"
        crop_and_rectify(self.image_path, self.region_for_crop(region), crop_path)
        angle = int(self.manual_rotation.value()) if "orientation" in enabled else 0
        apply_orientation(crop_path, final_path, OrientationResult(angle=angle, confidence=1.0 if angle else 0.0, evidence=["manual_rotation" if angle else "manual_or_future_detector"]))
        metadata = {"source": str(self.image_path), "region": region.__dict__, "enabled_steps": enabled, "final": str(final_path)}
        (out_dir / f"{self.image_path.stem}_{region.id}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status.showMessage(f"Pipeline 已运行（当前 AI 步骤为占位）：{final_path}")

def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
