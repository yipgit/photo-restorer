# Photo Restorer

跨平台老照片扫描整理与修复工具：从 A4 扫描/手机拍摄图中自动识别多张照片，裁切、透视/方向校正，并通过可配置 pipeline 做污点/霉点修复、人脸修复、超分和整体增强。

## 目标平台

- 开发/基础运行：macOS（无独显也可跑裁切、校正、预览）
- 主力运行：Windows + NVIDIA RTX 3070 / CUDA
- 形态：Python CLI + 本地 API + 桌面 UI（Tauri/Web UI scaffold）

## 当前 MVP

已包含：

- 项目骨架
- 可配置 preset
- CLI：批量 detect / run / inspect-config
- OpenCV 照片区域检测与透视裁切核心代码
- 方向识别接口与保守规则
- 模型 adapter 接口：LaMa、CodeFormer、Real-ESRGAN、DiffBIR/API 预留
- FastAPI 本地服务 scaffold
- 桌面 UI 原型页面

AI 模型暂以 adapter/stub 接口落位，后续逐个接入真实模型权重。

## 运行方式

当前版本是开发期 scaffold，不需要 Docker，也还不是完整安装包形态。

- 后端/CLI：Python 本地环境
- 前端：Vite + React 本地开发服务
- 桌面壳：预留 Tauri 方向，当前先用 Web UI scaffold

开发时通常开两个终端：一个跑 FastAPI 后端，一个跑前端 Vite。

## 后端安装

```bash
cd photo-restorer
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[api]'
```

完整图像处理依赖：

```bash
pip install -e '.[vision,api]'
```

GPU 修复依赖后续按模型分包安装。

## 启动后端 API

```bash
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uvicorn photo_restorer.api.server:app --reload --host 127.0.0.1 --port 8787
```

后端默认地址：`http://127.0.0.1:8787`

健康检查：

```bash
curl http://127.0.0.1:8787/health
```

## 启动前端 UI

```bash
cd apps/desktop
npm install
npm run dev
```

前端默认地址：`http://127.0.0.1:5173`

构建前端静态文件：

```bash
npm run build
```

说明：当前 UI 是 React/Vite 原型页，下一步会接入后端 `/run`、项目队列、检测框编辑和图片前后对比。完整 Tauri 桌面打包还未接入。

## 是否需要 Docker？

暂时不需要。

原因：

- 当前 MVP 主要是本地文件处理、OpenCV 裁切、FastAPI、本地 UI；原生 Python + Node 更直接。
- 后续 Windows + RTX 3070 跑 CUDA 模型时，Docker 会额外引入 NVIDIA Container Toolkit、磁盘挂载、模型缓存、GUI/文件选择等复杂度。
- 如果未来要做服务化部署或远程 GPU API，再补 Dockerfile / docker-compose 更合适。

## CLI

```bash
photo-restorer inspect-config --preset family_photo_default
photo-restorer detect ./scans --out ./projects/demo/project.json
photo-restorer run ./scans --preset family_photo_default --out ./outputs/demo --save-intermediate
photo-restorer run ./scan.jpg --preset crop_only --out ./outputs/crop --only-crop
```

## 本地 API

```bash
uvicorn photo_restorer.api.server:app --reload --port 8787
```

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

A4 scan → 页面预处理 → 照片检测 → 多照片裁切 → 透视矫正 → 方向识别 → 风格 preset → 局部缺陷修复 → 整体恢复 → 人脸修复 → 超分输出。
