import { useRef, useState, type DragEvent } from "react";
import { uploadAnalysis } from "../../../api/analyses";
import { navigate } from "../../../app/navigation";
import { Brand } from "../../../shared/components/Brand";
import { getSession, signOut } from "../../auth/services/session";

const ACCEPTED_EXTENSIONS = ["xlsx", "xls", "csv", "json", "parquet"];
const MAX_FILE_SIZE = 50 * 1024 * 1024;

function extensionOf(name: string) {
  return name.toLowerCase().split(".").pop() ?? "";
}

function sizeLabel(bytes: number) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function UploadPage() {
  const session = getSession();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [message, setMessage] = useState("");
  const [analyzing, setAnalyzing] = useState(false);

  function addFiles(incoming: File[]) {
    const rejected = incoming.find(file => !ACCEPTED_EXTENSIONS.includes(extensionOf(file.name)) || file.size > MAX_FILE_SIZE);
    if (rejected) setMessage(`${rejected.name} 的类型不受支持或超过 50 MB`);
    const valid = incoming.filter(file => ACCEPTED_EXTENSIONS.includes(extensionOf(file.name)) && file.size <= MAX_FILE_SIZE);
    if (valid.length > 1) setMessage("每次分析一个数据集，已选择第一个有效文件");
    if (valid[0]) setFiles([valid[0]]);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    addFiles(Array.from(event.dataTransfer.files));
  }

  async function startAnalysis() {
    if (!files.length) return;
    setAnalyzing(true);
    setMessage("正在上传并执行客流预测与特征分析…");
    try {
      const analysis = await uploadAnalysis(files[0]);
      window.localStorage.setItem("scenicmind.activeAnalysisId", analysis.analysisId);
      navigate("/dashboard");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "分析失败，请检查数据后重试");
      setAnalyzing(false);
    }
  }

  async function logout() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <main className="upload-page">
      <header className="upload-header">
        <Brand compact />
        <div><span>{session?.email ?? session?.username}</span><button type="button" onClick={logout}>退出</button></div>
      </header>
      <section className="upload-content">
        <div className="upload-heading"><span>DATA INPUT</span><h1>上传预测数据</h1><p>上传完成后将执行客流预测与独立特征贡献分析，再进入数据看板。</p></div>
        <div className="upload-card">
          <div className="upload-dropzone" role="button" tabIndex={0} onClick={() => inputRef.current?.click()} onKeyDown={event => (event.key === "Enter" || event.key === " ") && inputRef.current?.click()} onDragOver={event => event.preventDefault()} onDrop={handleDrop}>
            <span className="upload-icon">↑</span><strong>拖拽文件到此处</strong><p>或点击选择文件</p><small>.xlsx · .xls · .csv · .json · .parquet，单文件 ≤ 50 MB</small>
            <input ref={inputRef} hidden type="file" accept=".xlsx,.xls,.csv,.json,.parquet" onChange={event => addFiles(Array.from(event.target.files ?? []))} />
          </div>
          {files.length > 0 && <ul className="upload-file-list">{files.map((file, index) => <li key={`${file.name}-${file.size}`}><span>{extensionOf(file.name).toUpperCase()}</span><div><strong>{file.name}</strong><small>{sizeLabel(file.size)}</small></div><button type="button" aria-label={`移除 ${file.name}`} onClick={() => setFiles(current => current.filter((_, itemIndex) => itemIndex !== index))}>×</button></li>)}</ul>}
          {message && <p className="upload-message" role="status">{message}</p>}
          <div className="upload-actions"><button type="button" className="secondary" disabled={!files.length || analyzing} onClick={() => setFiles([])}>清空</button><button type="button" className="primary" disabled={!files.length || analyzing} onClick={startAnalysis}>{analyzing ? "分析中…" : "开始分析 →"}</button></div>
        </div>
      </section>
    </main>
  );
}
