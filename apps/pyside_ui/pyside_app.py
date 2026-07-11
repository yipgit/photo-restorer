from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable
import math
import json

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QAction, QColor, QPainter, QPen, QPixmap, QPolygonF
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
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
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QSplitter,
        QStatusBar,
        QVBoxLayout,
        QWidget,
        QGroupBox,
        QScrollArea,
    )
except Exception as exc:  # pragma: no cover
    raise RuntimeError("PySide6 is required. Install with: pip install -e '.[desktop]'") from exc

from photo_restorer.core.crop import crop_and_rectify
from photo_restorer.core.detect import detect_photo_regions
from photo_restorer.core.orientation import apply_orientation, detect_orientation
from photo_restorer.core.types import PhotoRegion

from pyside_ui.photo_wizard import PhotoWizard

POINT_RADIUS = 10

class DraggablePoint(QGraphicsEllipseItem):
    def __init__(self, polygon_item: "EditablePolygonItem", index: int, point: QPointF):
        super().__init__()
        r = POINT_RADIUS
        self.setRect(-r, -r, r * 2, r * 2)
        self.polygon_item = polygon_item
        self.index = index
        self.setPos(point)
        self.setBrush(QColor("#f97316"))
        self.setPen(QPen(QColor("#111827"), 2))
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(10)

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
        self.setDragMode(QGraphicsView.NoDrag)
        self.setMouseTracking(True)
        self._dragging_handle: DraggablePoint | None = None
        self._hand_dragging = False
        self._last_mouse_pos: QPointF | None = None

    def _find_handle(self, scene_pos: QPointF) -> DraggablePoint | None:
        best = None
        best_dist = POINT_RADIUS * 3
        for poly in self.polygons:
            for h in poly.handles:
                d = ((h.pos().x() - scene_pos.x()) ** 2 + (h.pos().y() - scene_pos.y()) ** 2) ** 0.5
                if d < best_dist:
                    best_dist = d
                    best = h
        return best

    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.position().toPoint())
        handle = self._find_handle(scene_pos)
        if handle is not None:
            self._dragging_handle = handle
            self._hand_dragging = False
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            self._dragging_handle = None
            self._hand_dragging = True
            self._last_mouse_pos = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging_handle is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._dragging_handle.setPos(scene_pos)
            self._dragging_handle.polygon_item.update_from_handles()
            event.accept()
        elif self._hand_dragging and self._last_mouse_pos is not None:
            pos = event.position().toPoint()
            delta = pos - self._last_mouse_pos
            self._last_mouse_pos = pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging_handle = None
        self._hand_dragging = False
        self._last_mouse_pos = None
        self.setCursor(Qt.ArrowCursor)
        event.accept()

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
        self.setWindowTitle("Photo Restorer")
        self.resize(1600, 900)
        self.image_path: Path | None = None
        self.regions: list[PhotoRegion] = []
        self.crop_outputs: list[dict] = []

        self.canvas = ImageCanvas()
        self.region_list = QListWidget()
        self.wizard = PhotoWizard()
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._scan_folder: Path | None = None
        self._scan_images: list[Path] = []
        self._scan_idx: int = -1
        self._build_ui()
        self._build_menu()

    def _build_menu(self):
        open_action = QAction("打开图片", self)
        open_action.triggered.connect(self.open_image)
        self.menuBar().addAction(open_action)
        open_folder_action = QAction("打开文件夹", self)
        open_folder_action.triggered.connect(self.open_folder)
        self.menuBar().addAction(open_folder_action)

    def _build_ui(self):
        splitter = QSplitter()
        left = self._left_panel()
        splitter.addWidget(left)
        splitter.addWidget(self.wizard)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)
        self.setCentralWidget(splitter)

    def _left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        open_btn = QPushButton("打开扫描图")
        open_btn.clicked.connect(self.open_image)
        layout.addWidget(open_btn)

        self._folder_btn = QPushButton("打开文件夹")
        self._folder_btn.clicked.connect(self.open_folder)
        layout.addWidget(self._folder_btn)

        nav_row = QHBoxLayout()
        self._prev_scan_btn = QPushButton("←")
        self._prev_scan_btn.clicked.connect(self._prev_scan)
        self._prev_scan_btn.setEnabled(False)
        nav_row.addWidget(self._prev_scan_btn)
        self._scan_label = QLabel("-")
        self._scan_label.setAlignment(Qt.AlignCenter)
        nav_row.addWidget(self._scan_label, 1)
        self._next_scan_btn = QPushButton("→")
        self._next_scan_btn.clicked.connect(self._next_scan)
        self._next_scan_btn.setEnabled(False)
        nav_row.addWidget(self._next_scan_btn)
        layout.addLayout(nav_row)

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

        edit_group = QGroupBox("识别结果")
        edit_layout = QVBoxLayout(edit_group)
        self.region_list.currentRowChanged.connect(self.canvas.highlight)
        edit_layout.addWidget(self.region_list)
        add_btn = QPushButton("手工新增四点框")
        add_btn.clicked.connect(self.add_manual_region)
        delete_btn = QPushButton("删除选中框")
        delete_btn.clicked.connect(self.delete_selected_region)
        crop_all_btn = QPushButton("裁切全部 → 进入逐张修复")
        crop_all_btn.clicked.connect(self.crop_all_for_restore)
        edit_layout.addWidget(add_btn); edit_layout.addWidget(delete_btn); edit_layout.addWidget(crop_all_btn)
        layout.addWidget(edit_group)

        layout.addStretch(1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(panel)
        container = QWidget()
        container_layout = QVBoxLayout(container); container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self.canvas, 1)
        container_layout.addWidget(scroll, 1)
        return container

    def open_image(self):
        filename, _ = QFileDialog.getOpenFileName(self, "选择扫描图", "", "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp)")
        if not filename:
            return
        self.image_path = Path(filename)
        self.canvas.load_image(self.image_path)
        self.regions = []
        self.crop_outputs = []
        self.region_list.clear()
        self.status.showMessage(f"已打开：{self.image_path}")
        self.detect_regions()
        self.crop_all_for_restore()

    def _cache_path(self) -> Path:
        return Path("outputs/ui-runs/crops") / f"{self.image_path.stem}.cache.json"

    def _load_cached_crop(self) -> bool:
        cache = self._cache_path()
        if not cache.exists():
            return False
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            return False
        mtime = self.image_path.stat().st_mtime_ns
        if data.get("image_mtime") != mtime:
            return False
        from photo_restorer.core.types import PhotoRegion
        from photo_restorer.core.orientation import OrientationResult
        self.regions = [PhotoRegion(**r) for r in data["regions"]]
        self.crop_outputs = []
        for item in data["crop_outputs"]:
            item["crop"] = Path(item["crop"])
            item["oriented"] = Path(item["oriented"])
            item["region"] = self.regions[len(self.crop_outputs)]
            item["orientation"] = OrientationResult(**item["orientation"])
            self.crop_outputs.append(item)
        self.canvas.set_regions(self.regions)
        self._refresh_region_list()
        self.wizard.set_photos(self.crop_outputs, self.image_path.stem if self.image_path else "")
        self.status.showMessage(f"已加载缓存：{len(self.regions)} 张照片")
        return True

    def _save_cached_crop(self):
        cache = self._cache_path()
        cache.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "image_path": str(self.image_path),
            "image_mtime": self.image_path.stat().st_mtime_ns,
            "regions": [r.__dict__ for r in self.regions],
            "crop_outputs": [
                {
                    "crop": str(item["crop"]),
                    "oriented": str(item["oriented"]),
                    "orientation": item["orientation"].__dict__,
                }
                for item in self.crop_outputs
            ],
        }
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择扫描图文件夹")
        if not folder:
            return
        self._scan_folder = Path(folder)
        IMG_EXT = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp'}
        self._scan_images = sorted([p for p in self._scan_folder.iterdir() if p.suffix.lower() in IMG_EXT])
        if not self._scan_images:
            QMessageBox.warning(self, "无图片", "文件夹中没有找到图片。")
            return
        self._scan_idx = 0
        self._load_current_scan()

    def _load_current_scan(self):
        if self._scan_idx < 0 or self._scan_idx >= len(self._scan_images):
            return
        self.image_path = self._scan_images[self._scan_idx]
        self._refresh_folder_nav()
        self.canvas.load_image(self.image_path)
        self.regions = []
        self.crop_outputs = []
        self.region_list.clear()
        self.status.showMessage(f"[{self._scan_idx + 1}/{len(self._scan_images)}] {self.image_path.name}")
        if not self._load_cached_crop():
            self.detect_regions()
            self.crop_all_for_restore()

    def _refresh_folder_nav(self):
        total = len(self._scan_images)
        self._scan_label.setText(f"{self._scan_idx + 1} / {total}" if total > 0 else "-")
        self._prev_scan_btn.setEnabled(self._scan_idx > 0)
        self._next_scan_btn.setEnabled(self._scan_idx < total - 1)

    def _prev_scan(self):
        if self._scan_idx > 0:
            self._scan_idx -= 1
            self._load_current_scan()

    def _next_scan(self):
        if self._scan_idx < len(self._scan_images) - 1:
            self._scan_idx += 1
            self._load_current_scan()

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
        self.status.showMessage(f"识别到 {len(self.regions)} 张照片。")

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

    def crop_all_for_restore(self):
        if not self.image_path:
            QMessageBox.warning(self, "未打开图片", "请先打开一张扫描图。")
            return
        if not self.regions:
            QMessageBox.warning(self, "没有识别结果", "请先识别照片，或手工新增四点框。")
            return
        out_dir = Path("outputs/ui-runs/crops")
        out_dir.mkdir(parents=True, exist_ok=True)
        self.crop_outputs = []
        try:
            for region in self.regions:
                crop_path = out_dir / f"{self.image_path.stem}_{region.id}_crop.png"
                oriented_path = out_dir / f"{self.image_path.stem}_{region.id}_oriented.png"
                crop_and_rectify(self.image_path, self.region_for_crop(region), crop_path)
                orientation = detect_orientation(crop_path, {"auto_rotate": True, "min_confidence": 0.7})
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
        self.wizard.set_photos(self.crop_outputs, self.image_path.stem if self.image_path else "")
        self._save_cached_crop()
        self.status.showMessage(f"已裁切 {len(self.crop_outputs)} 张照片，右侧可逐张调整修复参数。")

def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
