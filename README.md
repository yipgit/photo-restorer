# Photo Restorer

跨平台老照片扫描整理与修复工具：从 A4 扫描/手机拍摄图中自动识别多张照片，裁切、透视/方向校正，并通过可编排 pipeline 做污点/霉点修复、人脸修复、超分和整体增强。

## 目标平台

- 开发/基础运行：macOS（无独显也可跑裁切、校正、预览）
- 主力运行：Windows + NVIDIA RTX 3070 / CUDA
- 形态：Python CLI + PySide6 桌面 UI + 可选本地 API

## 当前 MVP 状态

已包含：

- Python 核心包
- CLI：批量 detect / run / inspect-config
- OpenCV 照片区域检测与透视裁切核心代码
- **PySide6 裁切工作台 MVP**：打开扫描图、调检测参数、重新识别、显示识别框、拖动四点、手工新增/删除四点框、裁切选中照片并预览、pipeline 勾选编排
- 方向识别/旋转作为独立 pipeline 步骤占位，后续接人脸/OCR/CLIP 投票
- 模型 adapter 接口：LaMa、CodeFormer、Real-ESRGAN、DiffBIR/API 预留
- FastAPI 本地服务 scaffold（可选）

AI 模型暂以 adapter/stub 接口落位，后续逐个接入真实模型权重。

## 运行方式

当前主 UI 已转向 PySide6。React/Vite 目录仍保留为早期 Web scaffold，但不再作为推荐入口。

## 安装

```bash
cd photo-restorer
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[desktop,api]'
```

如果只跑 CLI 裁切：

```bash
pip install -e '.[vision]'
```

GPU 修复依赖后续按模型分包安装。

## 启动 PySide 桌面 UI

```bash
source .venv/bin/activate  # Windows: .venv\Scripts\activate
photo-restorer-ui
```

当前 PySide UI 可用功能：

1. 打开 A4 扫描图。
2. 调整裁切识别参数：最小面积比例、最大面积比例、Canny low/high、模糊核、闭运算次数、四边形拟合参数、裁切扩边/羽化像素。
3. 点击“重新识别照片”，或打开“参数变化后自动重新识别”。
4. 在画布上查看绿色照片框，拖动橙色点手工调四角。
5. 识别漏图时点击“手工新增四点框”；误检时点击“删除选中框”。
6. 选择某张照片后点击“裁切选中照片并预览”。
7. 在 Pipeline 编排区勾选/取消步骤，设置手动旋转角度，再运行选中照片 pipeline。

> 说明：方向识别、人脸修复、去霉点、超分等步骤已经以 pipeline 形式出现在 UI 中，但当前 AI 步骤仍是占位；下一步会接真实模型和方向识别投票。

## CLI

```bash
photo-restorer inspect-config --preset family_photo_default
photo-restorer detect ./scans --out ./projects/demo/project.json
photo-restorer run ./scans --preset family_photo_default --out ./outputs/demo --save-intermediate
photo-restorer run ./scan.jpg --preset crop_only --out ./outputs/crop --only-crop
```

## 可选本地 API

```bash
uvicorn photo_restorer.api.server:app --reload --host 127.0.0.1 --port 8787
```

健康检查：

```bash
curl http://127.0.0.1:8787/health
```

## 是否需要 Docker？

暂时不需要。

原因：

- 当前 MVP 是本地图像处理和桌面交互，PySide + Python 原生运行更适合文件选择、画布调点和 GPU 模型调用。
- 后续 Windows + RTX 3070 跑 CUDA 模型时，Docker 会额外引入 NVIDIA Container Toolkit、磁盘挂载、模型缓存、GUI/文件选择等复杂度。
- 如果未来要做远程 GPU API，再补 Dockerfile / docker-compose。

## 输出结构

```text
outputs/job-id/
  00_original/
  01_detected_overlay/
  02_raw_crop/
  03_rectified/
  04_oriented/
  05_inpainted/
  06_restored/
  07_final/
  metadata/project.json
```

## 默认处理链

A4 scan → 页面预处理 → 照片检测/手工调点 → 多照片裁切 → 透视矫正 → 内容方向识别/旋转 → 风格/pipeline 参数 → 局部缺陷修复 → 整体恢复 → 人脸修复 → 超分输出。
