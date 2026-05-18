import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API_BASE = 'http://127.0.0.1:8787';
const PRESETS = [
  ['crop_only', '只裁切整理'],
  ['family_photo_default', '家庭照片默认'],
  ['conservative_archive', '档案保守'],
  ['aggressive_restore', '翻新增强'],
  ['ai_high_restore', 'AI 高修复（接口预留）'],
];

function App() {
  const [file, setFile] = useState(null);
  const [preset, setPreset] = useState('crop_only');
  const [onlyCrop, setOnlyCrop] = useState(true);
  const [status, setStatus] = useState('准备就绪');
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const previewUrl = useMemo(() => file ? URL.createObjectURL(file) : '', [file]);

  async function checkBackend() {
    setBusy(true);
    setError('');
    setStatus('正在检查后端...');
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setHealth(data);
      setStatus(`后端已连接：v${data.version}`);
    } catch (err) {
      setError(`无法连接后端。请先运行：uvicorn photo_restorer.api.server:app --reload --host 127.0.0.1 --port 8787`);
      setStatus('后端未连接');
    } finally {
      setBusy(false);
    }
  }

  async function runPipeline() {
    if (!file) {
      setError('请先选择一张 A4 扫描图或测试图片。');
      return;
    }
    setBusy(true);
    setError('');
    setResult(null);
    setStatus('正在上传并处理...');
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('preset', preset);
      form.append('only_crop', String(onlyCrop));
      const res = await fetch(`${API_BASE}/run`, { method: 'POST', body: form });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const data = await res.json();
      setResult(data);
      setStatus(`完成：识别/输出 ${data.photos?.length || 0} 张照片`);
    } catch (err) {
      setError(String(err.message || err));
      setStatus('处理失败');
    } finally {
      setBusy(false);
    }
  }

  return <main>
    <header className="hero">
      <div>
        <h1>Photo Restorer</h1>
        <p>扫描老照片自动裁切、方向校正与修复增强。</p>
      </div>
      <button onClick={checkBackend} disabled={busy}>检查后端</button>
    </header>

    <section className="panel">
      <h2>1. 导入扫描图</h2>
      <div className="upload-row">
        <label className="file-picker">
          <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          选择图片
        </label>
        <span>{file ? file.name : '未选择文件'}</span>
      </div>
      {previewUrl && <img className="preview" src={previewUrl} alt="input preview" />}
    </section>

    <section className="panel controls">
      <h2>2. 选择方案并运行</h2>
      <label>
        处理方案
        <select value={preset} onChange={(e) => setPreset(e.target.value)}>
          {PRESETS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <label className="checkbox">
        <input type="checkbox" checked={onlyCrop} onChange={(e) => setOnlyCrop(e.target.checked)} />
        只做裁切/校正（当前推荐；AI 模型 adapter 后续接入）
      </label>
      <button className="primary" onClick={runPipeline} disabled={busy || !file}>{busy ? '处理中...' : '开始处理'}</button>
    </section>

    <section className="panel">
      <h2>3. 状态</h2>
      <p className="status">{status}</p>
      {health && <pre>{JSON.stringify(health, null, 2)}</pre>}
      {error && <p className="error">{error}</p>}
    </section>

    {result && <section className="panel">
      <h2>4. 输出结果</h2>
      <p>Job: <code>{result.jobId}</code></p>
      <div className="results">
        {(result.photos || []).map((photo, index) => <figure key={`${photo.source_image}-${photo.region_id}-${index}`}>
          {photo.final_url && <img src={`${API_BASE}${photo.final_url}`} alt={`result ${index + 1}`} />}
          <figcaption>{photo.region_id}</figcaption>
        </figure>)}
      </div>
      <details>
        <summary>查看 metadata</summary>
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </details>
    </section>}
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
