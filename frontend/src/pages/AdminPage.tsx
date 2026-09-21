import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  AdminArtifact,
  AdminAudit,
  AdminDocument,
  AdminMedia,
  AdminSummary,
  clearAdminToken,
  getAdminArtifacts,
  getAdminAudit,
  getAdminDocuments,
  getAdminMedia,
  getAdminMediaDownloadUrl,
  getAdminSummary,
  getSavedAdminToken,
  linkAdminMedia,
  reviewAdminDocument,
  saveAdminToken,
  unlinkAdminMedia,
  updateAdminArtifact,
  uploadAdminDocument,
  uploadAdminMedia,
} from "../api/admin";

type AdminTab = "overview" | "artifacts" | "documents" | "media" | "audit";
type ArtifactForm = Pick<AdminArtifact, "name" | "era" | "category" | "description" | "location" | "material">;

const emptySummary: AdminSummary = {
  artifacts: 0,
  documents: 0,
  media_assets: 0,
  approved_documents: 0,
  documents_needing_review: 0,
  media_links_needing_review: 0,
};

const mediaLabels: Record<AdminMedia["media_type"], string> = { image: "图片", audio: "音频", video: "视频" };

function artifactForm(artifact: AdminArtifact): ArtifactForm {
  return {
    name: artifact.name,
    era: artifact.era ?? "",
    category: artifact.category ?? "",
    description: artifact.description ?? "",
    location: artifact.location ?? "",
    material: artifact.material ?? "",
  };
}

export function AdminPage() {
  const [token, setToken] = useState(getSavedAdminToken);
  const [tokenInput, setTokenInput] = useState(getSavedAdminToken);
  const [summary, setSummary] = useState(emptySummary);
  const [artifacts, setArtifacts] = useState<AdminArtifact[]>([]);
  const [documents, setDocuments] = useState<AdminDocument[]>([]);
  const [media, setMedia] = useState<AdminMedia[]>([]);
  const [audit, setAudit] = useState<AdminAudit[]>([]);
  const [tab, setTab] = useState<AdminTab>("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingForm, setEditingForm] = useState<ArtifactForm | null>(null);
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [uploadArtifactId, setUploadArtifactId] = useState("");
  const [linkArtifactId, setLinkArtifactId] = useState<Record<string, string>>({});
  const [artifactQuery, setArtifactQuery] = useState("");
  const [artifactEra, setArtifactEra] = useState("all");
  const [artifactCategory, setArtifactCategory] = useState("all");
  const [mediaPreviewUrls, setMediaPreviewUrls] = useState<Record<string, string>>({});
  const [selectedMediaIds, setSelectedMediaIds] = useState<string[]>([]);
  const [bulkMediaArtifactId, setBulkMediaArtifactId] = useState("");

  const filteredArtifacts = useMemo(() => {
    const query = artifactQuery.trim().toLocaleLowerCase();
    return artifacts.filter((artifact) => {
      const matchesQuery = !query || [artifact.name, artifact.location, artifact.material, artifact.category]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLocaleLowerCase().includes(query));
      const matchesEra = artifactEra === "all" || artifact.era === artifactEra;
      const matchesCategory = artifactCategory === "all" || artifact.category === artifactCategory;
      return matchesQuery && matchesEra && matchesCategory;
    });
  }, [artifactCategory, artifactEra, artifactQuery, artifacts]);

  const loadData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const [nextSummary, nextArtifacts, nextDocuments, nextMedia, nextAudit] = await Promise.all([
        getAdminSummary(token),
        getAdminArtifacts(token),
        getAdminDocuments(token),
        getAdminMedia(token),
        getAdminAudit(token),
      ]);
      setSummary(nextSummary);
      setArtifacts(nextArtifacts);
      setDocuments(nextDocuments);
      setMedia(nextMedia);
      setAudit(nextAudit);
      const imageEntries = await Promise.all(nextMedia.filter((item) => item.media_type === "image").map(async (item) => {
        try {
          return [item.id, await getAdminMediaDownloadUrl(item.id)] as const;
        } catch {
          return null;
        }
      }));
      setMediaPreviewUrls(Object.fromEntries(imageEntries.filter((entry): entry is readonly [string, string] => Boolean(entry))));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "管理端数据读取失败");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  function login(event: FormEvent) {
    event.preventDefault();
    const next = tokenInput.trim();
    if (!next) {
      setError("请输入管理端令牌。");
      return;
    }
    saveAdminToken(next);
    setToken(next);
    setMessage("已进入本机管理端。");
  }

  function logout() {
    clearAdminToken();
    setToken("");
    setTokenInput("");
    setArtifacts([]);
    setDocuments([]);
    setMedia([]);
    setAudit([]);
    setMediaPreviewUrls({});
  }

  async function submitArtifact(event: FormEvent) {
    event.preventDefault();
    if (!editingId || !editingForm) return;
    try {
      await updateAdminArtifact(token, editingId, editingForm);
      setMessage("文物信息已保存。");
      setEditingId(null);
      setEditingForm(null);
      await loadData();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "文物信息保存失败");
    }
  }

  async function submitDocument(event: FormEvent) {
    event.preventDefault();
    if (!documentFile) return;
    try {
      await uploadAdminDocument(token, documentFile, uploadArtifactId);
      setDocumentFile(null);
      setMessage("文档已上传，当前状态为待审核；向量索引不会自动触发。");
      await loadData();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "文档上传失败");
    }
  }

  async function submitMedia(event: FormEvent) {
    event.preventDefault();
    if (!mediaFile) return;
    try {
      await uploadAdminMedia(token, mediaFile, uploadArtifactId);
      setMediaFile(null);
      setMessage("媒体已上传；关联状态默认为待审核。");
      await loadData();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "媒体上传失败");
    }
  }

  async function setDocumentReview(document: AdminDocument, status: AdminDocument["review_status"]) {
    try {
      await reviewAdminDocument(token, document.id, status);
      setMessage(`文档已标记为${status === "approved" ? "已审核" : status === "rejected" ? "已拒绝" : "待审核"}。`);
      await loadData();
    } catch (reviewError) {
      setError(reviewError instanceof Error ? reviewError.message : "审核状态保存失败");
    }
  }

  async function approvePendingDocuments() {
    const pending = documents.filter((document) => document.review_status === "needs_review");
    if (!pending.length) {
      setMessage("当前没有待审核文档。");
      return;
    }
    try {
      await Promise.all(pending.map((document) => reviewAdminDocument(token, document.id, "approved")));
      setMessage(`已批量通过 ${pending.length} 份文档。`);
      await loadData();
    } catch (reviewError) {
      setError(reviewError instanceof Error ? reviewError.message : "批量审核失败");
    }
  }

  async function linkMedia(asset: AdminMedia) {
    const artifactId = linkArtifactId[asset.id];
    if (!artifactId) return;
    try {
      await linkAdminMedia(token, asset.id, artifactId);
      setMessage("媒体关联已保存，默认为待审核。");
      await loadData();
    } catch (linkError) {
      setError(linkError instanceof Error ? linkError.message : "媒体关联失败");
    }
  }

  async function bulkLinkMedia() {
    if (!bulkMediaArtifactId || !selectedMediaIds.length) {
      setMessage("请选择媒体和要关联的文物。");
      return;
    }
    try {
      await Promise.all(selectedMediaIds.map((mediaId) => linkAdminMedia(token, mediaId, bulkMediaArtifactId)));
      setMessage(`已为 ${selectedMediaIds.length} 个媒体对象建立待审核关联。`);
      setSelectedMediaIds([]);
      setBulkMediaArtifactId("");
      await loadData();
    } catch (linkError) {
      setError(linkError instanceof Error ? linkError.message : "批量关联失败");
    }
  }

  async function unlinkMedia(asset: AdminMedia, artifactId: string) {
    try {
      await unlinkAdminMedia(token, asset.id, artifactId);
      setMessage("已解除关联，MinIO 中的原文件未删除。");
      await loadData();
    } catch (unlinkError) {
      setError(unlinkError instanceof Error ? unlinkError.message : "解除关联失败");
    }
  }

  if (!token) {
    return (
      <main className="admin-login-page">
        <form className="admin-login-card" onSubmit={login}>
          <p className="admin-eyebrow">恩施博物馆 · 本机管理端</p>
          <h1>知识库管理</h1>
          <p>这里用于管理文物目录、文档和图片/音频/视频对象。游客端不会显示编辑入口。</p>
          <label htmlFor="admin-token">管理端令牌</label>
          <input id="admin-token" type="password" value={tokenInput} onChange={(event) => setTokenInput(event.target.value)} placeholder="填写 .env 中的 ADMIN_API_TOKEN" />
          <button className="admin-primary" type="submit">进入管理端</button>
          {error && <p className="admin-error">{error}</p>}
          <small>当前是本机令牌版，正式部署前再接学校统一登录。</small>
        </form>
      </main>
    );
  }

  return (
    <main className="admin-page">
      <header className="admin-header">
        <div>
          <p className="admin-eyebrow">恩施博物馆 · 本机管理端</p>
          <h1>知识库管理</h1>
          <p>维护文物、文档、图片、音频和视频的元数据与关联关系。</p>
        </div>
        <div className="admin-header-actions">
          <button type="button" onClick={() => void loadData()} disabled={loading}>↻ 刷新</button>
          <button type="button" onClick={logout}>退出管理端</button>
        </div>
      </header>
      {error && <div className="admin-alert admin-alert-error">{error}<button type="button" onClick={() => setError("")}>关闭</button></div>}
      {message && <div className="admin-alert">{message}<button type="button" onClick={() => setMessage("")}>关闭</button></div>}
      <nav className="admin-tabs" aria-label="管理端功能">
        {(["overview", "artifacts", "documents", "media", "audit"] as AdminTab[]).map((item) => (
          <button key={item} type="button" className={tab === item ? "active" : ""} onClick={() => setTab(item)}>
            {{ overview: "总览", artifacts: "文物目录", documents: "文档资料", media: "图片 / 音频 / 视频", audit: "操作记录" }[item]}
          </button>
        ))}
      </nav>

      {tab === "overview" && <Overview summary={summary} loading={loading} audit={audit} onSelect={setTab} />}
      {tab === "artifacts" && (
        <section className="admin-section">
          <SectionHeading title="文物目录" description="修改后的目录字段会保留在 PostgreSQL，并记录到操作日志。" />
          <div className="admin-filter-bar" aria-label="文物目录筛选">
            <input type="search" value={artifactQuery} onChange={(event) => setArtifactQuery(event.target.value)} placeholder="搜索名称、地点、材质…" aria-label="搜索文物" />
            <select value={artifactEra} onChange={(event) => setArtifactEra(event.target.value)} aria-label="按年代筛选"><option value="all">全部年代</option>{Array.from(new Set(artifacts.map((artifact) => artifact.era).filter(Boolean))).map((era) => <option key={era} value={era ?? ""}>{era}</option>)}</select>
            <select value={artifactCategory} onChange={(event) => setArtifactCategory(event.target.value)} aria-label="按类别筛选"><option value="all">全部类别</option>{Array.from(new Set(artifacts.map((artifact) => artifact.category).filter(Boolean))).map((category) => <option key={category} value={category ?? ""}>{category}</option>)}</select>
            <span>显示 {filteredArtifacts.length} / {artifacts.length} 件</span>
          </div>
          <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>名称</th><th>年代</th><th>地点</th><th>材质</th><th>文档</th><th>媒体</th><th>操作</th></tr></thead><tbody>
            {filteredArtifacts.map((artifact) => editingId === artifact.id && editingForm ? (
              <tr key={artifact.id} className="admin-edit-row"><td colSpan={7}><form className="admin-edit-form" onSubmit={submitArtifact}>
                {(["name", "era", "category", "location", "material"] as Array<keyof ArtifactForm>).map((field) => <label key={field}>{({ name: "名称", era: "年代", category: "类别", location: "地点", material: "材质" } as Record<string, string>)[field]}<input value={editingForm[field] ?? ""} onChange={(event) => setEditingForm({ ...editingForm, [field]: event.target.value })} /></label>)}
                <label className="admin-wide-field">简介<textarea value={editingForm.description ?? ""} onChange={(event) => setEditingForm({ ...editingForm, description: event.target.value })} /></label>
                <div className="admin-form-actions"><button className="admin-primary" type="submit">保存</button><button type="button" onClick={() => { setEditingId(null); setEditingForm(null); }}>取消</button></div>
              </form></td></tr>
            ) : <tr key={artifact.id}><td><strong>{artifact.name}</strong><small>{artifact.category || "未分类"}</small></td><td>{artifact.era || "—"}</td><td>{artifact.location || "—"}</td><td>{artifact.material || "—"}</td><td>{artifact.document_count}</td><td>{artifact.media_count}</td><td><button type="button" className="admin-link-button" onClick={() => { setEditingId(artifact.id); setEditingForm(artifactForm(artifact)); }}>编辑</button></td></tr>)}
            {!artifacts.length && <tr><td colSpan={7} className="admin-empty">暂无文物数据</td></tr>}
          </tbody></table></div>
        </section>
      )}
      {tab === "documents" && <DocumentsSection documents={documents} artifacts={artifacts} selectedArtifactId={uploadArtifactId} setSelectedArtifactId={setUploadArtifactId} file={documentFile} setFile={setDocumentFile} onSubmit={submitDocument} onReview={setDocumentReview} onApproveAll={() => void approvePendingDocuments()} />}
      {tab === "media" && <MediaSection media={media} artifacts={artifacts} selectedArtifactId={uploadArtifactId} setSelectedArtifactId={setUploadArtifactId} file={mediaFile} setFile={setMediaFile} onSubmit={submitMedia} linkArtifactId={linkArtifactId} setLinkArtifactId={setLinkArtifactId} onLink={linkMedia} onUnlink={unlinkMedia} previewUrls={mediaPreviewUrls} selectedMediaIds={selectedMediaIds} setSelectedMediaIds={setSelectedMediaIds} bulkMediaArtifactId={bulkMediaArtifactId} setBulkMediaArtifactId={setBulkMediaArtifactId} onBulkLink={() => void bulkLinkMedia()} />}
      {tab === "audit" && <AuditSection audit={audit} />}
    </main>
  );
}

function SectionHeading({ title, description }: { title: string; description: string }) {
  return <div className="admin-section-heading"><div><h2>{title}</h2><p>{description}</p></div></div>;
}

function Overview({ summary, loading, audit, onSelect }: { summary: AdminSummary; loading: boolean; audit: AdminAudit[]; onSelect: (tab: AdminTab) => void }) {
  const cards = [
    ["文物", summary.artifacts, "artifacts"], ["文档", summary.documents, "documents"], ["媒体对象", summary.media_assets, "media"], ["待审核", summary.documents_needing_review + summary.media_links_needing_review, "documents"],
  ] as const;
  const reviewTotal = summary.documents + summary.media_assets;
  const completeness = reviewTotal ? Math.round(((summary.approved_documents + summary.media_assets - summary.media_links_needing_review) / reviewTotal) * 100) : 0;
  return <section className="admin-section"><SectionHeading title="数据总览" description={loading ? "正在读取数据库…" : "先处理审核队列，再维护文物和媒体关系。历史趋势将在积累更多审计数据后开放。"} /><div className="admin-stat-grid">{cards.map(([label, value, target]) => <button key={label} type="button" className="admin-stat-card" onClick={() => onSelect(target)}><span>{label}</span><strong>{value}</strong><small>点击查看</small></button>)}</div><div className="admin-dashboard-grid"><div className="admin-progress-card"><div><span>资料审核完整度</span><b>{Math.max(0, Math.min(100, completeness))}%</b></div><div className="admin-progress"><i style={{ width: `${Math.max(0, Math.min(100, completeness))}%` }} /></div><small>已审核文档与媒体关联的当前快照</small></div><div className="admin-queue-card"><div><span>优先处理</span><b>{summary.documents_needing_review + summary.media_links_needing_review} 项</b></div><p>{summary.documents_needing_review ? `${summary.documents_needing_review} 份文档等待审核` : "文档审核队列已清空"}；{summary.media_links_needing_review ? `${summary.media_links_needing_review} 条媒体关系待确认` : "媒体关系暂无待确认项"}。</p><button type="button" onClick={() => onSelect("documents")}>打开审核队列 →</button></div></div><div className="admin-overview-lower"><div className="admin-safety-note"><strong>安全边界</strong><p>上传文档后状态为“待审核”，不会自动进入问答；解除媒体关联不会删除 MinIO 原文件；所有修改都会记录操作日志。</p></div><div className="admin-timeline"><strong>最近操作</strong>{audit.slice(0, 4).map((item) => <div key={item.id}><span>{new Date(item.created_at).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })}</span><p>{item.action} · {item.object_type}</p></div>)}{!audit.length && <small>暂无操作记录</small>}</div></div></section>;
}

function DocumentsSection({ documents, artifacts, selectedArtifactId, setSelectedArtifactId, file, setFile, onSubmit, onReview, onApproveAll }: { documents: AdminDocument[]; artifacts: AdminArtifact[]; selectedArtifactId: string; setSelectedArtifactId: (value: string) => void; file: File | null; setFile: (value: File | null) => void; onSubmit: (event: FormEvent) => void; onReview: (document: AdminDocument, status: AdminDocument["review_status"]) => void; onApproveAll: () => void }) {
  const pendingCount = documents.filter((document) => document.review_status === "needs_review").length;
  return <section className="admin-section"><SectionHeading title="文档资料" description="资料按 Word 文档管理；标题沿用文件名，不会自动改成文物分类。“次要文物信息”等字样只是原始文件名，上传后仍需审核。" /><form className="admin-upload-bar" onSubmit={onSubmit}><input type="file" accept=".docx" onChange={(event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] ?? null)} /><select value={selectedArtifactId} onChange={(event) => setSelectedArtifactId(event.target.value)}><option value="">不关联具体文物</option>{artifacts.map((artifact) => <option key={artifact.id} value={artifact.id}>{artifact.name}</option>)}</select><button className="admin-primary" type="submit" disabled={!file}>上传文档</button><button className="admin-batch-button" type="button" onClick={onApproveAll} disabled={!pendingCount}>批量通过 {pendingCount} 项</button></form><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>导入标题 / 原文件名</th><th>关联文物</th><th>分块</th><th>状态</th><th>操作</th></tr></thead><tbody>{documents.map((document) => <tr key={document.id}><td><strong>{document.title}</strong><small>原文件：{document.source_filename}</small></td><td>{document.artifact_name || "—"}</td><td>{document.chunk_count}</td><td><StatusPill status={document.review_status} /></td><td className="admin-actions"><button type="button" className="admin-link-button" onClick={() => void onReview(document, "approved")}>通过</button><button type="button" className="admin-link-button danger" onClick={() => void onReview(document, "rejected")}>拒绝</button></td></tr>)}{!documents.length && <tr><td colSpan={5} className="admin-empty">暂无文档数据</td></tr>}</tbody></table></div></section>;
}

function MediaSection({ media, artifacts, selectedArtifactId, setSelectedArtifactId, file, setFile, onSubmit, linkArtifactId, setLinkArtifactId, onLink, onUnlink, previewUrls, selectedMediaIds, setSelectedMediaIds, bulkMediaArtifactId, setBulkMediaArtifactId, onBulkLink }: { media: AdminMedia[]; artifacts: AdminArtifact[]; selectedArtifactId: string; setSelectedArtifactId: (value: string) => void; file: File | null; setFile: (value: File | null) => void; onSubmit: (event: FormEvent) => void; linkArtifactId: Record<string, string>; setLinkArtifactId: (value: Record<string, string>) => void; onLink: (asset: AdminMedia) => void; onUnlink: (asset: AdminMedia, artifactId: string) => void; previewUrls: Record<string, string>; selectedMediaIds: string[]; setSelectedMediaIds: (value: string[]) => void; bulkMediaArtifactId: string; setBulkMediaArtifactId: (value: string) => void; onBulkLink: () => void }) {
  const toggleMedia = (id: string) => setSelectedMediaIds(selectedMediaIds.includes(id) ? selectedMediaIds.filter((item) => item !== id) : [...selectedMediaIds, id]);
  return <section className="admin-section"><SectionHeading title="图片、音频、视频" description="媒体保留原始文件名，不会自动改名；先选择文物再上传，或上传后手动建立关联。相同内容会按 SHA-256 去重。" /><form className="admin-upload-bar" onSubmit={onSubmit}><input type="file" accept=".jpg,.jpeg,.png,.webp,.m4a,.mp3,.wav,.mp4,.mov,.avi" onChange={(event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] ?? null)} /><select value={selectedArtifactId} onChange={(event) => setSelectedArtifactId(event.target.value)}><option value="">先上传，不关联文物</option>{artifacts.map((artifact) => <option key={artifact.id} value={artifact.id}>{artifact.name}</option>)}</select><button className="admin-primary" type="submit" disabled={!file}>上传媒体</button></form><div className="admin-bulk-bar"><span>已选择 {selectedMediaIds.length} 个媒体</span><select value={bulkMediaArtifactId} onChange={(event) => setBulkMediaArtifactId(event.target.value)} aria-label="批量关联文物"><option value="">批量选择文物</option>{artifacts.map((artifact) => <option key={artifact.id} value={artifact.id}>{artifact.name}</option>)}</select><button className="admin-batch-button" type="button" onClick={onBulkLink} disabled={!selectedMediaIds.length || !bulkMediaArtifactId}>批量建立关联</button></div><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>选择</th><th>预览</th><th>原始文件</th><th>类型</th><th>大小</th><th>已关联文物</th><th>新增关联</th></tr></thead><tbody>{media.map((asset) => <tr key={asset.id}><td><input type="checkbox" checked={selectedMediaIds.includes(asset.id)} onChange={() => toggleMedia(asset.id)} aria-label={`选择${asset.original_filename}`} /></td><td>{asset.media_type === "image" && previewUrls[asset.id] ? <img className="admin-media-thumb" src={previewUrls[asset.id]} alt="媒体缩略图" /> : <span className={`admin-media-icon ${asset.media_type}`}>{asset.media_type === "audio" ? "♫" : asset.media_type === "video" ? "▶" : "▧"}</span>}</td><td><strong>{asset.original_filename}</strong><small>内容指纹：{asset.sha256.slice(0, 12)}…</small></td><td>{mediaLabels[asset.media_type]}</td><td>{Math.ceil(asset.byte_size / 1024)} KB</td><td>{asset.links.length ? asset.links.map((link) => <span className="admin-chip" key={link.artifact_id}>{link.artifact_name}<button type="button" onClick={() => void onUnlink(asset, link.artifact_id)} aria-label={`解除${link.artifact_name}关联`}>×</button></span>) : <span className="admin-muted">未关联</span>}</td><td><div className="admin-inline-action"><select value={linkArtifactId[asset.id] ?? ""} onChange={(event) => setLinkArtifactId({ ...linkArtifactId, [asset.id]: event.target.value })}><option value="">选择文物</option>{artifacts.map((artifact) => <option key={artifact.id} value={artifact.id}>{artifact.name}</option>)}</select><button type="button" className="admin-link-button" onClick={() => onLink(asset)} disabled={!linkArtifactId[asset.id]}>关联</button></div></td></tr>)}{!media.length && <tr><td colSpan={7} className="admin-empty">暂无媒体对象</td></tr>}</tbody></table></div></section>;
}

function AuditSection({ audit }: { audit: AdminAudit[] }) {
  return <section className="admin-section"><SectionHeading title="操作记录" description="所有上传、修改、审核、关联和解除关联都保留记录，便于追溯。" /><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>对象</th><th>对象 ID</th></tr></thead><tbody>{audit.map((item) => <tr key={item.id}><td>{new Date(item.created_at).toLocaleString("zh-CN")}</td><td>{item.actor}</td><td>{item.action}</td><td>{item.object_type}</td><td className="admin-id">{item.object_id || "—"}</td></tr>)}{!audit.length && <tr><td colSpan={5} className="admin-empty">暂无操作记录</td></tr>}</tbody></table></div></section>;
}

function StatusPill({ status }: { status: string }) {
  const label: Record<string, string> = { approved: "已审核", rejected: "已拒绝", needs_review: "待审核" };
  return <span className={`admin-status ${status}`}>{label[status] ?? status}</span>;
}
