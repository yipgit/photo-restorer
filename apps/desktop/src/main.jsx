import React from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

function App() {
  return <main>
    <h1>Photo Restorer</h1>
    <p>扫描老照片自动裁切、方向校正与修复增强。</p>
    <section className="grid">
      <div><h2>1 导入</h2><p>A4 扫描图 / 手机拍摄 / 批量目录</p></div>
      <div><h2>2 裁切</h2><p>自动识别多张照片，支持人工拖拽修正</p></div>
      <div><h2>3 修复</h2><p>选择档案保守、家庭默认、翻新增强或 AI 高修复</p></div>
      <div><h2>4 对比导出</h2><p>Before/After 预览，批量输出与 metadata</p></div>
    </section>
    <p className="note">UI scaffold 已建立；下一步接入本地 FastAPI /run、项目队列和图片对比组件。</p>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
