import { ChangeEvent, FormEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";

import {
  getArtifactCatalog,
  getConversationHistory,
  getArtifactMedia,
  getKnowledgeSeed,
  getPopularArtifacts,
  getSystemReadiness,
  recordArtifactVisit,
  recognizeArtifactImage,
  sendChatMessage,
} from "../api/client";
import type { ArtifactMedia, VisualSearchResponse } from "../api/client";
import type { ChatResponse, ConversationHistoryResponse, ConversationMessage } from "../types/chat";
import type { ArtifactCatalogItem, ArtifactCatalogResponse, KnowledgeSeedResponse, PopularArtifactResponse } from "../types/knowledge";
import type { SystemReadinessResponse } from "../types/system";
import { KnowledgeGamePage } from "./KnowledgeGamePage";

type NavigationKey = "chat" | "collection" | "exhibitions" | "favorites" | "history" | "games";
type ConversationTurn = { id: string; question: string; response: ChatResponse };
const SESSION_STORAGE_KEY = "enshi-museum-session-id";

function cleanVisitorText(value: string): string {
  return value
    .replace(/(?<![A-Za-z0-9_])INTERNAL_EVIDENCE(?![A-Za-z0-9_])\s*[:：]?/gi, "馆内资料")
    .replace(/(?<![A-Za-z0-9_])EXTERNAL_EVIDENCE(?![A-Za-z0-9_])\s*[:：]?/gi, "馆外资料")
    .replace(/(?<![A-Za-z0-9_])USER_QUERY(?![A-Za-z0-9_])\s*[:：]?/gi, "你的问题")
    .replace(/(?<![A-Za-z0-9_])SRC_\d+(?![A-Za-z0-9_])/gi, "馆内来源")
    .replace(/[【\[（(]\s*(?:馆内|馆外)?来源\s*[】\]）)]/gi, "");
}

const navigation: Array<{ key: NavigationKey; icon: string; label: string }> = [
  { key: "chat", icon: "◉", label: "对话" },
  { key: "collection", icon: "◈", label: "馆藏导览" },
  { key: "exhibitions", icon: "▣", label: "展览导览" },
  { key: "favorites", icon: "☆", label: "我的收藏" },
  { key: "history", icon: "◷", label: "历史记录" },
  { key: "games", icon: "♜", label: "小游戏" },
];

const suggestedQuestions = [
  { icon: "◈", text: "请介绍一下唐崖长官司印" },
  { icon: "♬", text: "西瓜碑音频" },
  { icon: "▤", text: "唐宋背景资料" },
  { icon: "⌕", text: "馆藏里有外星人文物吗" },
];

const FAVORITES_STORAGE_KEY = "enshi-museum-favorite-artifacts";

const exhibitionThemes = [
  {
    title: "三交史与土司文化",
    description: "从印章、牌坊和土司遗存中理解地方治理与文化交融。",
    keywords: ["土司", "唐崖", "施州", "永宁", "印", "牌坊", "奉天"],
  },
  {
    title: "器物与工艺",
    description: "观察铜镜、瓷器、金银器和玉石器物中的审美与技艺。",
    keywords: ["镜", "瓷", "瓶", "盘", "碗", "金", "银", "玉", "水晶"],
  },
  {
    title: "碑刻与历史记忆",
    description: "通过碑刻、墓志和遗址线索，阅读地方历史留下的文字记录。",
    keywords: ["碑", "墓志", "遗址", "牌坊"],
  },
];

function readFavoriteIds(): string[] {
  try {
    const raw = window.localStorage.getItem(FAVORITES_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function createSessionId() {
  try {
    const saved = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (saved) return saved;
    const created = `web-${crypto.randomUUID()}`;
    window.localStorage.setItem(SESSION_STORAGE_KEY, created);
    return created;
  } catch {
    return `web-${crypto.randomUUID()}`;
  }
}

function historyToTurns(messages: ConversationMessage[]): ConversationTurn[] {
  const turns: ConversationTurn[] = [];
  for (let index = 0; index < messages.length - 1; index += 1) {
    const question = messages[index];
    const answer = messages[index + 1];
    if (question.role !== "user" || answer.role !== "assistant") continue;
    turns.push({
      id: question.id,
      question: question.content,
      response: {
        session_id: "history",
        answer: cleanVisitorText(answer.content),
        intent: "history",
        answer_scope: "internal_only",
        evidence_status: "sufficient",
        reason_codes: [],
        citations: answer.citations,
        media: answer.media,
      },
    });
    index += 1;
  }
  return turns;
}

function scopeLabel(scope: ChatResponse["answer_scope"]) {
  const labels: Record<ChatResponse["answer_scope"], string> = {
    internal_only: "仅依据馆内资料",
    internal_plus_general: "馆内资料与背景参考",
    external_search: "公开资料补充",
    insufficient_evidence: "本地资料不足",
  };
  return labels[scope];
}

function evidenceStatusLabel(status: ChatResponse["evidence_status"]) {
  const labels: Record<ChatResponse["evidence_status"], string> = {
    sufficient: "证据充分",
    insufficient: "证据不足",
    conflicting: "证据存在冲突",
  };
  return labels[status];
}

function reasonCodeLabel(code: string) {
  const labels: Record<string, string> = {
    catalog_field_present: "目录字段已命中",
    p1_catalog_record: "优先使用标准目录",
    approved_document_link: "已关联审核通过的馆内资料",
    no_verified_evidence: "没有审核通过的馆藏证据",
    chat_generation_disabled: "已采用馆内资料回答",
    generation_failed: "已采用馆内资料回答",
    vector_search_unavailable: "已使用馆内资料检索",
    conflicting_internal_evidence: "馆内资料之间存在冲突",
    external_search_used: "已补充公开资料",
    external_search_empty: "公开资料未检索到可核验结果",
    external_search_budget_exhausted: "外部搜索额度已用完",
    external_search_unavailable: "外部搜索暂不可用",
  };
  return labels[code] ?? code;
}

function mediaTypeLabel(type: string) {
  const labels: Record<string, string> = { image: "图片", audio: "音频", video: "视频" };
  return labels[type] ?? "媒体";
}

function visitLabel(count: number) {
  return count > 0 ? `访问 ${count} 次` : "刚上线";
}

function inferArtifactCategory(artifact: ArtifactCatalogItem) {
  if (artifact.name.includes("碑") || artifact.name.includes("墓志") || artifact.name.includes("牌坊")) return "碑刻与建筑遗存";
  if (artifact.name.includes("印")) return "制度与身份器物";
  if (artifact.name.includes("镜") || artifact.name.includes("瓶") || artifact.name.includes("碗") || artifact.name.includes("盘")) return "器物与工艺";
  if (artifact.material?.includes("玉") || artifact.material?.includes("水晶")) return "玉石与装饰";
  return "地方历史文物";
}

function inferArtifactUse(artifact: ArtifactCatalogItem) {
  if (artifact.name.includes("印")) return "制度、身份与权力标识";
  if (artifact.name.includes("镜")) return "礼仪、装饰与日常使用";
  if (artifact.name.includes("碑") || artifact.name.includes("墓志")) return "纪事、纪念与历史记录";
  if (artifact.name.includes("牌坊")) return "纪念性建筑与地方空间";
  if (artifact.name.includes("冠") || artifact.name.includes("钗") || artifact.name.includes("扣")) return "服饰与身份装饰";
  return "用途待馆藏资料确认";
}

function compareValue(value: string | null | undefined) {
  return value || "暂无记录";
}

function ComparePanel({ items, answer, isLoading, error, onBack, onOpenArtifact }: { items: ArtifactCatalogItem[]; answer: ChatResponse | null; isLoading: boolean; error: string; onBack: () => void; onOpenArtifact: (item: ArtifactCatalogItem) => void }) {
  const [left, right] = items;
  if (!left || !right) return null;
  const rows = [
    ["年代", compareValue(left.era), compareValue(right.era)],
    ["材质", compareValue(left.material), compareValue(right.material)],
    ["出土地 / 地点", compareValue(left.location), compareValue(right.location)],
    ["类别", inferArtifactCategory(left), inferArtifactCategory(right)],
    ["用途线索", inferArtifactUse(left), inferArtifactUse(right)],
  ];
  const shared = rows.filter(([, leftValue, rightValue]) => leftValue !== "暂无记录" && leftValue === rightValue).map(([label, value]) => `${label}均为${value}`);
  return (
    <section className="collection-panel comparison-panel" aria-live="polite">
      <button className="guide-back" type="button" onClick={onBack}>← 返回馆藏目录</button>
      <p className="answer-label">研学工具 · 文物对比</p>
      <div className="comparison-heading"><div><h2>把两件文物放在一起看</h2><p>从目录事实出发，再结合馆内资料理解它们的历史联系。</p></div><span>已选择 2 件</span></div>
      <div className="comparison-artifact-headings">
        {[left, right].map((item) => <article key={item.id}><div className="comparison-artifact-mark">{item.name.slice(0, 1)}</div><div><b>{item.name}</b><small>{item.era || "年代待考"} · {item.material || "材质待考"}</small></div><button type="button" onClick={() => onOpenArtifact(item)}>查看展签 →</button></article>)}
      </div>
      <div className="comparison-table" role="table" aria-label="文物字段对比">
        {rows.map(([label, leftValue, rightValue]) => <div className="comparison-row" key={label}><strong>{label}</strong><span>{leftValue}</span><span>{rightValue}</span></div>)}
      </div>
      <section className="comparison-insight">
        <div className="comparison-section-title"><span>01</span><h3>先看共同点</h3></div>
        {shared.length ? <div className="comparison-shared-list">{shared.map((item) => <span key={item}>✓ {item}</span>)}</div> : <p>目录字段显示两件文物各有侧重，下面的馆内资料对照会进一步解释它们的联系。</p>}
      </section>
      <section className="comparison-insight comparison-ai-insight">
        <div className="comparison-section-title"><span>02</span><h3>历史背景与文化意义</h3><span className="comparison-source-badge">馆内资料核验</span></div>
        {isLoading && <div className="comparison-loading"><div className="loading-orbit" aria-hidden="true" /><p>正在整理两件文物的馆内资料…</p></div>}
        {error && <p className="panel-error">{error}</p>}
        {answer && <><p className="comparison-answer">{answer.answer}</p><div className="comparison-trust"><span>{scopeLabel(answer.answer_scope)}</span><span className={`trust-${answer.evidence_status}`}>{evidenceStatusLabel(answer.evidence_status)}</span><span>{answer.citations.length} 项来源</span></div></>}
      </section>
      <div className="guide-footer-actions"><button className="guide-secondary-action" type="button" onClick={onBack}>换两件文物</button><button className="game-primary" type="button" onClick={() => onOpenArtifact(left)}>进入{left.name}展签 →</button></div>
    </section>
  );
}

function PlaceholderPanel({ title }: { title: string }) {
  return (
    <section className="feature-placeholder">
      <div className="museum-glyph" aria-hidden="true">恩</div>
      <p className="planning-badge">规划功能 · 尚未开放</p>
      <h2>{title}</h2>
      <p>该页面保留为演示导航。等用户、权限或展览数据完成审核并入库后，再开放相应功能。</p>
    </section>
  );
}

function GuideDetailPanel({
  artifact,
  answer,
  media,
  isLoading,
  error,
  onBack,
  isFavorite,
  onToggleFavorite,
  onContinueChat,
  relatedArtifacts,
  onOpenRelated,
}: {
  artifact: ArtifactCatalogItem;
  answer: ChatResponse | null;
  media: ArtifactMedia[];
  isLoading: boolean;
  error: string;
  onBack: () => void;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  onContinueChat: () => void;
  relatedArtifacts: ArtifactCatalogItem[];
  onOpenRelated: (artifact: ArtifactCatalogItem) => void;
}) {
  const coverMedia = media.find((item) => item.media_type === "image");
  return (
    <section className="collection-panel guide-detail-panel">
      <button className="guide-back" type="button" onClick={onBack}>← 返回文物列表</button>
      <p className="answer-label">文物导览</p>
      <div className="guide-hero">
        <div className="guide-hero-copy">
          <div className="guide-detail-heading">
            <div>
              <h2>{artifact.name}</h2>
              <p>{artifact.era || "年代待考"} · {inferArtifactCategory(artifact)}</p>
            </div>
            <span className="guide-visit-badge">{visitLabel(artifact.view_count ?? 0)}</span>
          </div>
          <p className="guide-lead">这件文物来自{artifact.location || "恩施地方"}，以{artifact.material || "馆藏器物"}为主要特征，是理解地方历史与文化记忆的一条线索。</p>
          <div className="guide-actions">
            <button className={`favorite-button ${isFavorite ? "saved" : ""}`} type="button" onClick={onToggleFavorite}>
              {isFavorite ? "★ 已收藏" : "☆ 收藏这件文物"}
            </button>
            <button className="guide-ask-button" type="button" onClick={onContinueChat}>问问这件文物 →</button>
          </div>
        </div>
        <div className="guide-hero-media">
          {coverMedia ? <img src={coverMedia.url} alt={`${artifact.name}展签图片`} /> : <span aria-hidden="true">恩</span>}
        </div>
      </div>
      <div className="guide-facts" aria-label="文物基本信息">
        <div><small>时代</small><b>{artifact.era || "暂无记录"}</b></div>
        <div><small>地点</small><b>{artifact.location || "暂无记录"}</b></div>
        <div><small>材质</small><b>{artifact.material || "暂无记录"}</b></div>
        <div><small>类别</small><b>{inferArtifactCategory(artifact)}</b></div>
      </div>
      {isLoading && (
        <div className="guide-loading">
          <div className="loading-orbit" aria-hidden="true" />
          <p>正在整理馆内资料、生成导览词并读取关联媒体…</p>
        </div>
      )}
      {error && <p className="panel-error guide-error">{error}</p>}
      {answer && (
        <>
          <section className="guide-section">
            <div className="guide-section-heading"><span>01</span><h3>展厅导览词</h3></div>
            <p className="guide-section-lead">先从眼前的器物开始，再把它放回恩施的地域、制度与生活历史中。</p>
            <p className="guide-answer">{answer.answer}</p>
            {answer.notice && <small className="guide-note">{answer.notice}</small>}
          </section>
          <section className="guide-trust" aria-label="资料可信度">
            <div><span>资料范围</span><b>{scopeLabel(answer.answer_scope)}</b></div>
            <div><span>证据状态</span><b className={`trust-${answer.evidence_status}`}>{evidenceStatusLabel(answer.evidence_status)}</b></div>
            <div><span>来源数量</span><b>{answer.citations.length} 项可追溯来源</b></div>
          </section>
          {answer.citations.length > 0 && (
            <section className="guide-section">
              <div className="guide-section-heading"><span>02</span><h3>资料依据</h3></div>
              <ul className="guide-citations">
                {answer.citations.map((citation) => <li key={citation.id}>{citation.title}{citation.excerpt ? `：${citation.excerpt}` : ""}</li>)}
              </ul>
            </section>
          )}
        </>
      )}
      {media.length > 0 && (
        <section className="guide-section">
          <div className="guide-section-heading"><span>03</span><h3>看见、听见这件文物</h3></div>
          <div className="media-grid">
            {media.map((item) => (
              <article className="media-card" key={item.id}>
                <div className="media-card-heading"><span>{mediaTypeLabel(item.media_type)}</span><div className="media-card-meta">{item.media_type === "video" && <a href={item.url} target="_blank" rel="noreferrer">新窗口打开</a>}<small>{item.original_filename}</small></div></div>
                {item.media_type === "audio" && <audio controls preload="metadata" src={item.url}>浏览器不支持音频播放。</audio>}
                {item.media_type === "video" && <video controls preload="metadata" src={item.url}>浏览器不支持视频播放。</video>}
                {item.media_type === "image" && <img src={item.url} alt={`${artifact.name}关联图片`} loading="lazy" />}
              </article>
            ))}
          </div>
        </section>
      )}
      {relatedArtifacts.length > 0 && (
        <section className="guide-section guide-related-section">
          <div className="guide-section-heading"><span>04</span><h3>继续发现</h3></div>
          <p className="guide-related-intro">从同一条历史线索出发，看看这些文物如何彼此照应。</p>
          <div className="guide-related-grid">
            {relatedArtifacts.map((item) => <button className="guide-related-card" key={item.id} type="button" onClick={() => onOpenRelated(item)}><span>{item.era || "馆藏"}</span><b>{item.name}</b><small>{item.material || "地方文物"} · 查看展签 →</small></button>)}
          </div>
        </section>
      )}
      <div className="guide-footer-actions">
        <button className="guide-secondary-action" type="button" onClick={onBack}>返回文物列表</button>
        <button className="game-primary" type="button" onClick={onContinueChat}>问问这件文物 →</button>
      </div>
    </section>
  );
}

function ReadinessPanel({ readiness }: { readiness: SystemReadinessResponse }) {
  return (
    <section className="readiness-panel" aria-label="系统就绪状态">
      <div>
        <b>系统就绪状态</b>
        <span>只读</span>
      </div>
      <p>
        {readiness.documents} 份文档 · {readiness.child_chunks} 个检索分块 · {readiness.catalog_artifacts} 件目录文物 · {readiness.media_assets} 个媒体文件
      </p>
      <p>
        知识库检索：{readiness.retrieval_mode === "hybrid" ? "混合检索已启用" : "关键词检索已启用"} ｜ 向量索引：{readiness.vector_search_enabled ? "就绪" : "待确认"} ｜ 馆外资料：{readiness.web_search_enabled ? "已启用" : "关闭"}
      </p>
    </section>
  );
}

function ImageSearchPanel({ response, previewUrl }: { response: VisualSearchResponse; previewUrl: string | null }) {
  const artifact = response.recognized_artifact;
  const relatedMedia = [...response.media].sort((left, right) => {
    if (left.type === right.type) return 0;
    if (left.type === "video") return -1;
    if (right.type === "video") return 1;
    return 0;
  });
  return (
    <section className="answer-panel visual-search-panel" aria-live="polite">
      <div className="answer-topline">
        <p className="answer-label">图片识别</p>
        <span className={`evidence-badge ${artifact ? "sufficient" : "insufficient"}`}>{artifact ? "已匹配馆藏" : "暂未匹配"}</span>
      </div>
      <div className="visual-search-heading">
        {previewUrl && <img src={previewUrl} alt="待识别的文物图片" />}
        <div>
          <p className="answer-label">识别结果</p>
          <h2>{artifact ? artifact.name : "暂时无法确认"}</h2>
          {artifact && <p className="visual-confidence">目录匹配度约 {Math.round(response.confidence * 100)}%</p>}
        </div>
      </div>
      {artifact && (
        <div className="visual-facts" aria-label="识别出的文物信息">
          {artifact.era && <span><small>时代</small><b>{artifact.era}</b></span>}
          {artifact.location && <span><small>地点</small><b>{artifact.location}</b></span>}
          {artifact.material && <span><small>材质</small><b>{artifact.material}</b></span>}
        </div>
      )}
      {response.visual_note && <p className="visual-note">图片观察：{response.visual_note}</p>}
      {response.visual_matches.length > 0 && (
        <div className="visual-match-list" aria-label="本地参考图候选">
          <b>本地参考图检索</b>
          {response.visual_matches.slice(0, 3).map((match) => <span key={`${match.artifact}-${match.source}`}>{match.artifact} · {Math.round(match.score * 100)}%</span>)}
        </div>
      )}
      <p className="answer-text">{response.answer}</p>
      {response.notice && <p className="answer-notice">{response.notice}</p>}
      {response.citations.length > 0 && <p className="visual-source-count">已关联 {response.citations.length} 项馆内资料</p>}
      {relatedMedia.length > 0 && (
        <section className="media-section" aria-label="识别结果的馆藏媒体">
          <h3>相关馆藏媒体</h3>
          <div className="media-grid">
            {relatedMedia.map((item) => (
              <article className="media-card" key={item.id}>
                <div className="media-card-heading"><span>{mediaTypeLabel(item.type)}</span><div className="media-card-meta">{item.type === "video" && <a href={item.url} target="_blank" rel="noreferrer">新窗口打开</a>}<small>馆藏关联媒体</small></div></div>
                {item.type === "video" && <video controls preload="metadata" src={item.url}>浏览器不支持视频播放。</video>}
                {item.type === "audio" && <audio controls preload="metadata" src={item.url}>浏览器不支持音频播放。</audio>}
                {item.type === "image" && <img src={item.url} alt="馆藏文物资料图片" loading="lazy" />}
              </article>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}

export function ChatPage() {
  const sessionId = useMemo(createSessionId, []);
  const [activeNavigation, setActiveNavigation] = useState<NavigationKey>("chat");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [knowledgeSeed, setKnowledgeSeed] = useState<KnowledgeSeedResponse | null>(null);
  const [catalog, setCatalog] = useState<ArtifactCatalogResponse | null>(null);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [history, setHistory] = useState<ConversationHistoryResponse | null>(null);
  const [popularArtifacts, setPopularArtifacts] = useState<PopularArtifactResponse | null>(null);
  const [homeFeaturedArtifacts, setHomeFeaturedArtifacts] = useState<PopularArtifactResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [panelError, setPanelError] = useState("");
  const [readiness, setReadiness] = useState<SystemReadinessResponse | null>(null);
  const [selectedGuide, setSelectedGuide] = useState<ArtifactCatalogItem | null>(null);
  const [guideAnswer, setGuideAnswer] = useState<ChatResponse | null>(null);
  const [guideMedia, setGuideMedia] = useState<ArtifactMedia[]>([]);
  const [isGuideLoading, setIsGuideLoading] = useState(false);
  const [guideError, setGuideError] = useState("");
  const [favoriteIds, setFavoriteIds] = useState<string[]>(readFavoriteIds);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageResult, setImageResult] = useState<VisualSearchResponse | null>(null);
  const [isImageSearching, setIsImageSearching] = useState(false);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [showComparison, setShowComparison] = useState(false);
  const [comparisonAnswer, setComparisonAnswer] = useState<ChatResponse | null>(null);
  const [isComparisonLoading, setIsComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState("");

  const shownCatalogItems = useMemo(() => {
    const query = catalogQuery.trim().toLocaleLowerCase();
    if (!catalog || !query) return catalog?.items ?? [];
    return catalog.items.filter((item) =>
      [item.name, item.era, item.location, item.material]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLocaleLowerCase().includes(query)),
    );
  }, [catalog, catalogQuery]);

  const compareItems = useMemo(
    () => compareIds.map((id) => catalog?.items.find((item) => item.id === id)).filter((item): item is ArtifactCatalogItem => Boolean(item)),
    [catalog, compareIds],
  );

  useEffect(() => {
    void getSystemReadiness().then(setReadiness).catch(() => setReadiness(null));
    void getPopularArtifacts().then(setHomeFeaturedArtifacts).catch(() => setHomeFeaturedArtifacts(null));
    void getConversationHistory(sessionId)
      .then((savedHistory) => setConversation(historyToTurns(savedHistory.messages)))
      .catch(() => undefined);
  }, [sessionId]);

  useEffect(() => {
    window.localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(favoriteIds));
  }, [favoriteIds]);

  function toggleFavorite(artifactId: string) {
    setFavoriteIds((current) => current.includes(artifactId)
      ? current.filter((id) => id !== artifactId)
      : [...current, artifactId]);
  }

  function toggleCompare(artifactId: string) {
    setShowComparison(false);
    setComparisonAnswer(null);
    setComparisonError("");
    setCompareIds((current) => current.includes(artifactId)
      ? current.filter((id) => id !== artifactId)
      : current.length < 2 ? [...current, artifactId] : [current[1], artifactId]);
  }

  async function startComparison() {
    if (compareItems.length !== 2 || isComparisonLoading) return;
    const [left, right] = compareItems;
    setShowComparison(true);
    setComparisonAnswer(null);
    setComparisonError("");
    setIsComparisonLoading(true);
    try {
      const response = await sendChatMessage({
        session_id: sessionId,
        message: "请基于馆内已审核资料，对比“" + left.name + "”和“" + right.name + "”。请分别说明年代、材质、用途、出土地、历史背景和文化意义，再总结两件文物的共同点与区别。请使用清晰的小标题，只能依据馆内资料，资料不足的地方请明确说明。",
      });
      setComparisonAnswer(response);
    } catch (requestError) {
      setComparisonError(requestError instanceof Error ? requestError.message : "文物对比暂时无法生成，请稍后重试。");
    } finally {
      setIsComparisonLoading(false);
    }
  }

  async function selectNavigation(next: NavigationKey) {
    setSelectedGuide(null);
    setActiveNavigation(next);
    setPanelError("");
    if (next === "history") {
      if (history || isLoading) return;
      setIsLoading(true);
      try {
        setHistory(await getConversationHistory(sessionId));
      } catch (requestError) {
        setPanelError(requestError instanceof Error ? requestError.message : "对话记录读取失败。");
      } finally {
        setIsLoading(false);
      }
      return;
    }
    if (next === "exhibitions") {
      if (popularArtifacts || isLoading) return;
      setIsLoading(true);
      try {
        const [popularResult, catalogResult] = await Promise.allSettled([
          getPopularArtifacts(),
          catalog ? Promise.resolve(catalog) : getArtifactCatalog(),
        ]);
        if (popularResult.status === "rejected") throw popularResult.reason;
        setPopularArtifacts(popularResult.value);
        if (catalogResult.status === "fulfilled") setCatalog(catalogResult.value);
      } catch (requestError) {
        setPanelError(requestError instanceof Error ? requestError.message : "热门文物读取失败。");
      } finally {
        setIsLoading(false);
      }
      return;
    }
    if (next === "favorites") {
      if (catalog || isLoading) return;
      setIsLoading(true);
      try {
        setCatalog(await getArtifactCatalog());
      } catch (requestError) {
        setPanelError(requestError instanceof Error ? requestError.message : "收藏文物读取失败。");
      } finally {
        setIsLoading(false);
      }
      return;
    }
    if (next !== "collection" || isLoading || (catalog && knowledgeSeed)) return;
    setIsLoading(true);
    try {
      const [catalogResult, seedResult] = await Promise.allSettled([getArtifactCatalog(), getKnowledgeSeed()]);
      if (catalogResult.status === "rejected") {
        throw catalogResult.reason;
      }
      setCatalog(catalogResult.value);
      if (seedResult.status === "fulfilled") {
        setKnowledgeSeed(seedResult.value);
      }
    } catch (requestError) {
      setPanelError(requestError instanceof Error ? requestError.message : "馆藏资料读取失败。");
    } finally {
      setIsLoading(false);
    }
  }

  async function submitMessage(text: string) {
    const cleanText = text.trim();
    if (!cleanText || isSubmitting) return;
    setIsSubmitting(true);
    setError("");
    setResult(null);
    setImageResult(null);
    try {
      const response = await sendChatMessage({ session_id: sessionId, message: cleanText });
      setConversation((turns) => [...turns, { id: crypto.randomUUID(), question: cleanText, response }]);
      setResult(response);
      setHistory(null);
      setMessage("");
      setActiveNavigation("chat");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "请求失败，请稍后再试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleImageSelected(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (!file) return;
    if (!/[.](jpe?g|png|webp)$/i.test(file.name) || !["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("请选择 JPG、PNG 或 WebP 图片。");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setError("图片不能超过 20MB。");
      return;
    }
    setError("");
    setImageFile(file);
    setImageResult(null);
    setResult(null);
    setImagePreview(URL.createObjectURL(file));
  }

  function clearImage() {
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImageFile(null);
    setImagePreview(null);
    setImageResult(null);
  }

  async function handleImageSearch() {
    if (!imageFile || isImageSearching) return;
    setIsImageSearching(true);
    setError("");
    setResult(null);
    try {
      setImageResult(await recognizeArtifactImage(imageFile));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "图片识别失败，请稍后重试。");
    } finally {
      setIsImageSearching(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitMessage(message);
  }

  async function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await submitMessage(message);
    }
  }

  async function openArtifactGuide(item: ArtifactCatalogItem) {
    setSelectedGuide(item);
    setGuideAnswer(null);
    setGuideMedia([]);
    setGuideError("");
    setIsGuideLoading(true);
    try {
      const visit = await recordArtifactVisit(item.id);
      const viewedItem = { ...item, view_count: visit.view_count };
      setSelectedGuide(viewedItem);
      setPopularArtifacts((current) => current && {
        ...current,
        items: current.items.map((candidate) => candidate.id === item.id
          ? { ...candidate, view_count: visit.view_count }
          : candidate),
      });
      const [answerResult, mediaResult] = await Promise.allSettled([
        sendChatMessage({
          session_id: sessionId,
          message: `请为“${item.name}”写一份适合博物馆展厅的完整导览词。请尽量分成基本信息、历史背景、文化意义和参观重点几个部分，只能依据馆内资料，资料不足的部分请明确说明。`,
        }),
        getArtifactMedia(item.name),
      ]);
      if (answerResult.status === "rejected") throw answerResult.reason;
      setGuideAnswer(answerResult.value);
      if (mediaResult.status === "fulfilled") setGuideMedia(mediaResult.value);
      setHistory(null);
    } catch {
      setGuideError("导览内容暂时无法读取，请稍后重试。");
    } finally {
      setIsGuideLoading(false);
    }
  }

  function renderMainContent() {
    if (selectedGuide) {
      return (
        <GuideDetailPanel
          artifact={selectedGuide}
          answer={guideAnswer}
          media={guideMedia}
          isLoading={isGuideLoading}
          error={guideError}
          onBack={() => setSelectedGuide(null)}
          isFavorite={favoriteIds.includes(selectedGuide.id)}
          onToggleFavorite={() => toggleFavorite(selectedGuide.id)}
          relatedArtifacts={(catalog?.items ?? [])
            .filter((item) => item.id !== selectedGuide.id && exhibitionThemes.some((theme) => theme.keywords.some((keyword) => selectedGuide.name.includes(keyword) && item.name.includes(keyword))))
            .slice(0, 3)}
          onOpenRelated={(item) => void openArtifactGuide(item)}
          onContinueChat={() => {
            setSelectedGuide(null);
            setActiveNavigation("chat");
            setMessage(`请继续介绍${selectedGuide.name}的历史背景和文化意义`);
          }}
        />
      );
    }

    if (activeNavigation === "history") {
      if (isLoading) return <section className="collection-panel"><p>正在读取对话记录…</p></section>;
      if (panelError) return <section className="collection-panel"><h2>历史记录</h2><p className="panel-error">{panelError}</p></section>;
      return (
        <section className="collection-panel history-panel">
          <p className="answer-label">本次会话</p>
          <h2>历史记录</h2>
          <p>{history?.messages.length ? `已保存 ${history.messages.length} 条消息。` : "还没有对话。"}</p>
          <div className="history-list">
            {history?.messages.map((item) => (
              <article className={`history-message ${item.role}`} key={item.id}>
                <small>{item.role === "user" ? "访客" : "智能导览"}</small>
                <p>{item.content}</p>
              </article>
            ))}
          </div>
        </section>
      );
    }

    if (activeNavigation === "collection") {
      if (isLoading) return <section className="collection-panel"><p>正在读取馆藏资料…</p></section>;
      if (panelError) return <section className="collection-panel"><h2>馆藏导览</h2><p className="panel-error">{panelError}</p></section>;
      if (catalog) {
        if (showComparison && compareItems.length === 2) {
          return <ComparePanel items={compareItems} answer={comparisonAnswer} isLoading={isComparisonLoading} error={comparisonError} onBack={() => setShowComparison(false)} onOpenArtifact={(item) => void openArtifactGuide(item)} />;
        }
        return (
          <section className="collection-panel">
            <p className="answer-label">已入库文物目录</p>
            <h2>馆藏知识库</h2>
            <p>目录资料保留原始 Excel 来源行号；同名文物合并展示，便于追溯与去重。</p>
            <div className="seed-stat"><b>{catalog.total}</b> 件标准文物</div>
            <input className="catalog-search" type="search" value={catalogQuery} onChange={(event) => setCatalogQuery(event.target.value)} placeholder="按文物名称、时代、地点或材质查找" aria-label="搜索文物目录" />
            <div className="compare-bar" aria-label="文物对比工具">
              <div><span>文物对比</span><b>{compareIds.length}/2</b><small>{compareIds.length === 2 ? "已选两件，可以开始对比" : "从卡片中选择两件文物"}</small></div>
              <div><button className="compare-start-button" type="button" disabled={compareIds.length !== 2 || isComparisonLoading} onClick={() => void startComparison()}>开始对比 →</button><button className="compare-clear-button" type="button" onClick={() => { setCompareIds([]); setShowComparison(false); }}>清空</button></div>
            </div>
            <div className="catalog-grid">
              {shownCatalogItems.map((item) => (
                <article className="catalog-card" key={item.id}>
                  <div className="catalog-card-topline"><h3>{item.name}</h3><button className={`mini-favorite ${favoriteIds.includes(item.id) ? "saved" : ""}`} type="button" onClick={() => toggleFavorite(item.id)} aria-label={favoriteIds.includes(item.id) ? `取消收藏${item.name}` : `收藏${item.name}`}>{favoriteIds.includes(item.id) ? "★" : "☆"}</button></div>
                  <div className="catalog-tags">{item.era && <span>{item.era}</span>}{item.location && <span>{item.location}</span>}{item.material && <span>{item.material}</span>}</div>
                  <button className={compareIds.includes(item.id) ? "compare-card-action selected" : "compare-card-action"} type="button" onClick={() => toggleCompare(item.id)} aria-pressed={compareIds.includes(item.id)}>{compareIds.includes(item.id) ? "✓ 已加入对比" : "+ 加入对比"}</button>
                  <small>{item.source_rows} 条来源记录</small>
                  <button className="catalog-card-action" type="button" onClick={() => void openArtifactGuide(item)}>查看导览 →</button>
                </article>
              ))}
            </div>
            {shownCatalogItems.length === 0 && <p className="collection-note">没有匹配的文物，请换一个关键词。</p>}
            {knowledgeSeed && <p className="collection-note">Word 种子资料：{knowledgeSeed.copied_files}/{knowledgeSeed.total_files} 份已准备。</p>}
          </section>
        );
      }
    }

    if (activeNavigation === "exhibitions") {
      if (isLoading) return <section className="collection-panel"><p>正在整理热门文物…</p></section>;
      if (panelError) return <section className="collection-panel"><h2>展览导览</h2><p className="panel-error">{panelError}</p></section>;
      return (
        <section className="collection-panel exhibition-panel">
          <p className="answer-label">访问热度推荐</p>
          <h2>热门文物导览</h2>
          <p>{popularArtifacts?.has_visit_data ? "以下内容按访客实际打开导览的次数排序。" : "当前还没有历史访问记录，先展示馆藏目录中的文物；后续会根据访问量自动排序。"}</p>
          <div className="popular-grid">
            {popularArtifacts?.items.map((item, index) => (
              <article className="popular-card" key={item.id}>
                <div className="popular-card-topline"><div className="popular-rank">TOP {index + 1}</div><button className={`mini-favorite ${favoriteIds.includes(item.id) ? "saved" : ""}`} type="button" onClick={() => toggleFavorite(item.id)} aria-label={favoriteIds.includes(item.id) ? `取消收藏${item.name}` : `收藏${item.name}`}>{favoriteIds.includes(item.id) ? "★" : "☆"}</button></div>
                <h3>{item.name}</h3>
                <div className="catalog-tags">{item.era && <span>{item.era}</span>}{item.location && <span>{item.location}</span>}{item.material && <span>{item.material}</span>}</div>
                <p className="popular-count">{visitLabel(item.view_count)}</p>
                <button className="catalog-card-action" type="button" onClick={() => void openArtifactGuide(item)}>进入导览 →</button>
              </article>
            ))}
          </div>
          <div className="theme-section-heading">
            <p className="answer-label">主题路线</p>
            <h3>按主题认识恩施文物</h3>
          </div>
          <div className="exhibition-theme-list">
            {exhibitionThemes.map((theme, index) => {
              const themeItems = (catalog?.items ?? []).filter((item) => theme.keywords.some((keyword) => item.name.includes(keyword))).slice(0, 4);
              return (
                <section className={`exhibition-theme exhibition-theme-${index + 1}`} key={theme.title}>
                  <div className="exhibition-theme-cover"><span>路线 0{index + 1}</span><b>{theme.title.slice(0, 1)}</b></div>
                  <div className="exhibition-theme-content">
                    <div className="exhibition-theme-topline"><span>主题路线</span><b>{themeItems.length} 件推荐</b></div>
                    <h3>{theme.title}</h3>
                  <p>{theme.description}</p>
                  <div className="theme-route-line" aria-label={`${theme.title}推荐顺序`}>
                    {themeItems.slice(0, 3).map((item, itemIndex) => <span key={item.id}><i>{itemIndex + 1}</i>{item.name}</span>)}
                  </div>
                  <div className="theme-artifact-list">
                    {themeItems.map((item) => (
                      <button className="theme-artifact" type="button" key={item.id} onClick={() => void openArtifactGuide(item)}>
                        <span>{item.name}</span><b>→</b>
                      </button>
                    ))}
                    {themeItems.length === 0 && <small>相关目录文物正在整理。</small>}
                  </div>
                  </div>
                </section>
              );
            })}
          </div>
        </section>
      );
    }

    if (activeNavigation === "favorites") {
      if (isLoading) return <section className="collection-panel"><p>正在读取我的收藏…</p></section>;
      if (panelError) return <section className="collection-panel"><h2>我的收藏</h2><p className="panel-error">{panelError}</p></section>;
      const favoriteItems = catalog?.items.filter((item) => favoriteIds.includes(item.id)) ?? [];
      return (
        <section className="collection-panel favorites-panel">
          <p className="answer-label">本机保存</p>
          <h2>我的收藏</h2>
          <p>收藏只保存在当前浏览器，不需要登录；以后接入账号后可以继续同步。</p>
          {favoriteItems.length > 0 ? (
            <div className="catalog-grid">
              {favoriteItems.map((item) => (
                <article className="catalog-card" key={item.id}>
                  <div className="catalog-card-topline"><h3>{item.name}</h3><button className="mini-favorite saved" type="button" onClick={() => toggleFavorite(item.id)} aria-label={`取消收藏${item.name}`}>★</button></div>
                  <div className="catalog-tags">{item.era && <span>{item.era}</span>}{item.location && <span>{item.location}</span>}{item.material && <span>{item.material}</span>}</div>
                  <small>{item.source_rows} 条来源记录</small>
                  <button className="catalog-card-action" type="button" onClick={() => void openArtifactGuide(item)}>查看导览 →</button>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-favorites"><span>☆</span><h3>还没有收藏文物</h3><p>在馆藏导览或文物详情页点击“收藏”，以后可以从这里快速进入。</p></div>
          )}
        </section>
      );
    }

    if (activeNavigation === "games") return <KnowledgeGamePage onOpenCollection={() => void selectNavigation("collection")} />;

    if (activeNavigation !== "chat") return <PlaceholderPanel title={navigation.find((item) => item.key === activeNavigation)?.label ?? "规划功能"} />;

    if (isSubmitting) {
      return (
        <section className="loading-panel" aria-live="polite" aria-busy="true">
          <div className="loading-orbit" aria-hidden="true" />
          <p className="answer-label">正在处理</p>
          <h2>正在检索馆内资料</h2>
          <p>系统正在进行关键词与向量检索，并整理可追溯证据，请稍候。</p>
          <div className="loading-steps"><span>检索知识库</span><span>核验证据</span><span>生成回答</span></div>
        </section>
      );
    }

    if (isImageSearching) {
      return (
        <section className="loading-panel" aria-live="polite" aria-busy="true">
          <div className="loading-orbit" aria-hidden="true" />
          <p className="answer-label">正在识别图片</p>
          <h2>正在和馆藏目录比对</h2>
          <p>系统会先识别画面，再用馆内资料核验结果。</p>
        </section>
      );
    }

    if (imageResult) return <ImageSearchPanel response={imageResult} previewUrl={imagePreview} />;

    if (result) {
      const currentTurn = conversation[conversation.length - 1];
      return (
        <section className="chat-thread" aria-label="当前对话">
          {conversation.length > 1 && (
            <details className="conversation-history">
              <summary className="conversation-history-heading">
                <div><p className="answer-label">本次会话</p><h2>之前的对话</h2><small>历史回答已收起，不影响当前导览</small></div>
                <span>{conversation.length - 1} 轮 · 点击展开</span>
              </summary>
              <div className="conversation-history-body">
                {conversation.slice(0, -1).map((turn) => (
                  <article className="conversation-turn" key={turn.id}>
                    <div className="question-bubble"><b>你</b><p>{turn.question}</p></div>
                    <div className="previous-answer">
                      <div><b>智能导览</b><span>{turn.response.citations.length} 项来源{turn.response.media.length ? ` · ${turn.response.media.length} 个媒体` : ""}</span></div>
                      <p>{turn.response.answer}</p>
                    </div>
                  </article>
                ))}
              </div>
            </details>
          )}
          {currentTurn && (
            <div className="chat-message user-message">
              <span className="chat-avatar">你</span>
              <p>{currentTurn.question}</p>
            </div>
          )}
          <section className="answer-panel" aria-live="polite">
          <div className="answer-topline">
            <p className="answer-label">{result.intent === "media" ? "媒体导览" : "智能导览"}</p>
            <span className={`evidence-badge ${result.evidence_status}`}>{evidenceStatusLabel(result.evidence_status)}</span>
          </div>
          <p className={`answer-scope ${result.answer_scope}`}>{scopeLabel(result.answer_scope)}</p>
          <h2>关于你的问题</h2>
          <p className="answer-text">{result.answer}</p>
          {result.notice && <p className="answer-notice">{result.notice}</p>}
          {result.evidence_status !== "sufficient" && (
            <div className="answer-notice">
              <b>处理说明</b>
              <span>{result.reason_codes.length ? result.reason_codes.map(reasonCodeLabel).join("、") : "系统已采取安全降级处理。"}</span>
            </div>
          )}
          {result.citations.length > 0 && (
            <div className="citation-row">
              <div className="citation-heading"><b>{result.citations.length} 项可追溯来源</b><span>点击查看资料依据</span></div>
              <ul className="citation-list">
                {result.citations.map((citation) => (
                  <li key={citation.id}>
                    <details>
                      <summary><b>{citation.source_type === "internal" ? "馆内资料" : "外部资料"}</b>：{citation.url ? <a href={citation.url} target="_blank" rel="noreferrer">{citation.title}</a> : citation.title}</summary>
                      {citation.excerpt && <small>{citation.excerpt}</small>}
                    </details>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.unverified_extension && (
            <section className="extension-section">
              <h3>背景参考（不是本件文物的直接证据）</h3>
              <p>{result.unverified_extension}</p>
            </section>
          )}
          {result.media.length > 0 && (
            <section className="media-section" aria-label="检索到的媒体">
              <h3>相关媒体</h3>
              <div className="media-grid">
                {result.media.map((item) => (
                  <article className="media-card" key={item.id}>
                    <div className="media-card-heading"><span>{mediaTypeLabel(item.type)}</span><div className="media-card-meta">{item.type === "video" && <a href={item.url} target="_blank" rel="noreferrer">新窗口打开</a>}<small>馆藏关联媒体</small></div></div>
                    {item.type === "audio" && <audio controls preload="metadata" src={item.url}>浏览器不支持音频播放。</audio>}
                    {item.type === "video" && <video controls preload="metadata" src={item.url}>浏览器不支持视频播放。</video>}
                    {item.type === "image" && <img src={item.url} alt="馆藏文物资料图片" loading="lazy" />}
                  </article>
                ))}
              </div>
            </section>
          )}
          </section>
        </section>
      );
    }

    return (
      <section className="welcome-panel">
        <div className="museum-glyph" aria-hidden="true">恩</div>
        <h2>想了解哪件文物，直接问。</h2>
        <p>可以检索已入库的馆藏文物、背景资料和关联图片、音频或视频。</p>
        {readiness && <ReadinessPanel readiness={readiness} />}
        <div className="question-list" aria-label="推荐问题">
          {suggestedQuestions.map((question) => <button key={question.text} type="button" onClick={() => setMessage(question.text)}><span><i aria-hidden="true">{question.icon}</i>{question.text}</span><b aria-hidden="true">→</b></button>)}
        </div>
        {homeFeaturedArtifacts?.items.length ? (
          <section className="home-featured-section" aria-labelledby="home-featured-title">
            <div className="home-featured-heading"><div><p className="answer-label">今日推荐</p><h3 id="home-featured-title">从一件文物开始探索</h3></div><button type="button" onClick={() => void selectNavigation("exhibitions")}>查看全部 →</button></div>
            <div className="home-featured-grid">
              {homeFeaturedArtifacts.items.slice(0, 3).map((item) => <article className="home-featured-card" key={item.id}><div className="home-featured-card-art"><span>{item.name.slice(0, 1)}</span></div><div className="home-featured-card-body"><div><span>{item.era || "馆藏"}</span><b>{item.name}</b></div><p>{item.material || "地方文物"} · {item.location || "恩施"}</p><button type="button" onClick={() => void openArtifactGuide(item)}>查看展签 →</button></div></article>)}
            </div>
          </section>
        ) : null}
      </section>
    );
  }

  const retrievalLabel = readiness?.retrieval_mode === "hybrid" ? "混合检索" : "关键词检索";
  const runtimeDisclaimer = readiness
    ? `当前为${retrievalLabel}；知识库证据链${readiness.vector_search_enabled ? "已就绪" : "正在准备"}；馆外资料${readiness.web_search_enabled ? "已启用" : "关闭"}。`
    : "正在读取系统状态…";

  return (
    <div className="museum-shell">
      <header className="topbar"><div className="brand-mark" aria-label="恩施州博物馆">恩</div><div className="museum-name"><strong>恩施州博物馆</strong><span>ENSHI PREFECTURE MUSEUM</span></div><div className="topbar-divider" /><h1>智能导览问答</h1></header>
      <aside className="sidebar" aria-label="主导航"><nav>{navigation.map((item) => <button className={`nav-item ${activeNavigation === item.key ? "active" : ""}`} key={item.key} type="button" onClick={() => void selectNavigation(item.key)}><span aria-hidden="true">{item.icon}</span>{item.label}</button>)}</nav><div className="sidebar-bottom"><a className="admin-nav-link" href="/admin">⚙ 管理端</a><button className="guest-chip" type="button" title="登录功能将在权限模块完成后接入">◌ 访客演示模式</button><button className="clear-chat" type="button" onClick={() => { setResult(null); setConversation([]); }}>⌫ 清空对话</button></div></aside>
      <main className="chat-stage">
        {renderMainContent()}
        {activeNavigation === "chat" && <button className="mobile-search-launch" type="button" onClick={() => void selectNavigation("collection")}>⌕ 搜索馆藏</button>}
        {activeNavigation === "chat" && <form className={`composer ${isSubmitting || isImageSearching ? "composer-floating" : "composer-in-flow"}`} onSubmit={handleSubmit}><label htmlFor="question">发送问题</label><textarea id="question" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder="说说你想了解的文物、背景资料或媒体…" rows={3} /><div className="composer-tools"><div className="composer-icons" aria-hidden="true"><label className="image-upload-button" htmlFor="artifact-image">▧ <span>上传图片</span></label><input id="artifact-image" type="file" accept="image/jpeg,image/png,image/webp" onChange={handleImageSelected} /><span>◌</span><span>♬</span></div><span>Enter 发送，Shift + Enter 换行</span><button type="submit" aria-label="发送问题" disabled={isSubmitting || !message.trim()}>{isSubmitting ? "…" : "→"}</button></div>{imageFile && <div className="image-upload-preview"><img src={imagePreview ?? ""} alt="已选择的文物图片" /><span>{imageFile.name}</span><button type="button" onClick={clearImage} aria-label="移除图片">×</button><button className="image-search-submit" type="button" onClick={() => void handleImageSearch()} disabled={isImageSearching}>识别这件文物</button></div>}{error && <p className="composer-error">{error}</p>}</form>}
        {activeNavigation === "chat" && <p className="disclaimer">{runtimeDisclaimer}</p>}
      </main>
    </div>
  );
}
