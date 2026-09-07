import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { getGameAudioClue, type GameAudioClue } from "../api/client";

type GameQuestion = {
  id: string;
  category: "三交史" | "基础文物知识";
  difficulty?: "入门" | "进阶";
  question: string;
  options: string[];
  answerIndex: number;
  explanation: string;
  source: string;
};

const QUESTION_BANK: GameQuestion[] = [
  {
    id: "three-01",
    category: "三交史",
    question: "“三交史”这一主题强调的三个关键词是？",
    options: ["交往、交流、交融", "交通、交易、交税", "交战、交替、交割", "教化、教习、教育"],
    answerIndex: 0,
    explanation: "本游戏以“交往、交流、交融”为主线，理解文物背后的历史联系。",
    source: "本项目“三交史”主题设定",
  },
  {
    id: "three-02",
    category: "三交史",
    question: "已入库资料提到，土司制度在什么时期正式形成？",
    options: ["元代", "唐代", "明代", "民国时期"],
    answerIndex: 0,
    explanation: "资料指出，土司制度在元代正式形成。",
    source: "《元明清之际三交史背景信息》",
  },
  {
    id: "three-03",
    category: "三交史",
    question: "元代设置土司的重要作用之一是什么？",
    options: ["将边地首领纳入中央王朝治理体系", "完全取消地方治理", "只管理海外贸易", "只负责修建道路"],
    answerIndex: 0,
    explanation: "元代通过设置土司，逐步将边地民族地区首领纳入治理体系。",
    source: "《元明清之际三交史背景信息》",
  },
  {
    id: "three-04",
    category: "三交史",
    question: "资料中提到，明代哪些文化在土司地区广泛传播并促进交融？",
    options: ["儒、释、道文化", "只传播一种外来文字", "只传播航海技术", "只传播现代工业文化"],
    answerIndex: 0,
    explanation: "儒、释、道文化的传播，是促进民族文化交融的因素之一。",
    source: "《元明清之际三交史背景信息》",
  },
  {
    id: "three-05",
    category: "三交史",
    question: "清代加强中央直接管辖、推动进一步融合的重要政策是？",
    options: ["改土归流", "闭关锁国", "分封诸侯", "废除州县"],
    answerIndex: 0,
    explanation: "“改土归流”促进了边陲地区进一步纳入中央政府管辖。",
    source: "《元明清之际三交史背景信息》",
  },
  {
    id: "three-06",
    category: "三交史",
    question: "元明清时期土司地区关系演进的总体趋势更接近哪一项？",
    options: ["由控制与冲突走向交融共生", "始终完全隔绝", "只发生经济竞争", "由共生走向彻底断绝"],
    answerIndex: 0,
    explanation: "资料将这一过程概括为融合共生的历史演进。",
    source: "《元明清之际三交史背景信息》",
  },
  {
    id: "three-07",
    category: "三交史",
    question: "革命文物在民族交往交流交融中可以发挥什么作用？",
    options: ["见证共同历史并促进文化认同", "替代所有历史研究", "只用于商业交易", "与文化交流无关"],
    answerIndex: 0,
    explanation: "革命文物的展示、研究与传播能增进文化认同。",
    source: "《近代背景资料》",
  },
  {
    id: "three-08",
    category: "三交史",
    question: "学习文物时，为什么要同时关注它的历史背景？",
    options: ["能理解文物与不同群体交往交流交融的联系", "只为记住更多编号", "可以忽略文物来源", "能直接判断市场价格"],
    answerIndex: 0,
    explanation: "文物不仅是器物，也承载历史环境、群体联系和文化记忆。",
    source: "本项目“三交史”主题设定",
  },
  {
    id: "basic-01",
    category: "基础文物知识",
    question: "“凤凰八卦铜镜”这一名称直接提示了它的哪类纹样线索？",
    options: ["凤凰与八卦纹样", "海浪与帆船纹样", "葡萄与莲花纹样", "山水与人物画像"],
    answerIndex: 0,
    explanation: "名称本身提示了凤凰和八卦两类纹样，是识别这件文物的基础线索。",
    source: "馆藏目录：凤凰八卦铜镜",
  },
  {
    id: "basic-02",
    category: "基础文物知识",
    question: "“唐崖长官司印”最能帮助我们了解哪一类历史？",
    options: ["土司制度与地方治理", "近代铁路建设", "海洋捕捞技术", "天文观测方法"],
    answerIndex: 0,
    explanation: "“长官司印”是理解唐崖土司及地方治理历史的重要文物线索。",
    source: "馆藏目录：唐崖长官司印",
  },
];

type PreparedQuestion = Omit<GameQuestion, "options" | "answerIndex"> & {
  options: string[];
  answerIndex: number;
};

type AnswerRecord = {
  question: PreparedQuestion;
  selectedAnswer: string;
  isCorrect: boolean;
};

const ROUND_SIZE = 8;

function shuffle<T>(items: T[]): T[] {
  const result = [...items];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [result[index], result[swapIndex]] = [result[swapIndex], result[index]];
  }
  return result;
}

function validateQuestionBank(bank: GameQuestion[]): GameQuestion[] {
  if (bank.length < ROUND_SIZE) throw new Error("小游戏题库至少需要 8 道题目。");
  for (const question of bank) {
    if (question.options.length < 2 || question.answerIndex < 0 || question.answerIndex >= question.options.length) {
      throw new Error(`题目 ${question.id} 的答案配置无效。`);
    }
    if (new Set(question.options).size !== question.options.length) {
      throw new Error(`题目 ${question.id} 存在重复选项。`);
    }
  }
  return bank;
}

const VALIDATED_QUESTION_BANK = validateQuestionBank(QUESTION_BANK);

function prepareQuestion(question: GameQuestion): PreparedQuestion {
  const indexedOptions = question.options.map((option, index) => ({ option, index }));
  const shuffledOptions = shuffle(indexedOptions);
  return {
    ...question,
    options: shuffledOptions.map(({ option }) => option),
    answerIndex: shuffledOptions.findIndex(({ index }) => index === question.answerIndex),
  };
}

function createRound(): PreparedQuestion[] {
  const threeHistory = shuffle(VALIDATED_QUESTION_BANK.filter((question) => question.category === "三交史")).slice(0, 6);
  const basicKnowledge = shuffle(VALIDATED_QUESTION_BANK.filter((question) => question.category === "基础文物知识")).slice(0, 2);
  return shuffle([...threeHistory, ...basicKnowledge]).map(prepareQuestion);
}

function getResultTitle(score: number) {
  if (score === ROUND_SIZE) return "三交史达人";
  if (score >= 6) return "文物探索者";
  if (score >= 4) return "历史观察员";
  return "文物新朋友";
}

type JourneyChapter = "交往" | "交流" | "交融";

const CHAPTER_EXPLANATIONS: Record<JourneyChapter, string> = {
  "交往": "建立人物、制度与地方之间的联系",
  "交流": "观察思想、器物与文化如何传播互鉴",
  "交融": "把多条线索连起来，理解共同发展与认同",
};

const CLUE_CHAPTERS: Record<string, JourneyChapter> = {
  "唐崖土司牌坊": "交往",
  "唐崖长官司印": "交往",
  "土司制度": "交往",
  "文化传播": "交流",
  "凤凰八卦铜镜": "交流",
  "改土归流": "交融",
  "交融共生": "交融",
};

function getClueChapter(clue: string): JourneyChapter {
  return CLUE_CHAPTERS[clue] ?? "交往";
}

type JourneyOption = {
  label: string;
  clue: string;
  tag?: string;
};

type JourneyStopId = "enshi" | "xianfeng" | "tangya";
type JourneyInteraction = "single" | "pair" | "sequence";

type JourneyStage = {
  id: string;
  chapter: JourneyChapter;
  stopId: JourneyStopId;
  interaction: JourneyInteraction;
  title: string;
  prompt: string;
  hint: string;
  options: JourneyOption[];
  correctIndex?: number;
  correctIndexes?: number[];
  sequenceOrder?: number[];
  evidenceLink?: [string, string];
  explanation: string;
  source: string;
  reward: string;
};

type PreparedJourneyStage = Omit<JourneyStage, "options" | "correctIndex"> & {
  options: JourneyOption[];
  correctIndex?: number;
  correctIndexes?: number[];
  sequenceOrder?: number[];
};

type JourneyAnswer = {
  stage: PreparedJourneyStage;
  selectedIndexes: number[];
  isCorrect: boolean;
};

function isJourneySelectionCorrect(stage: PreparedJourneyStage, selectedIndexes: number[]) {
  if (stage.interaction === "single") return selectedIndexes.length === 1 && selectedIndexes[0] === stage.correctIndex;
  if (stage.interaction === "pair") {
    const expected = [...(stage.correctIndexes ?? [])].sort((a, b) => a - b);
    const actual = [...selectedIndexes].sort((a, b) => a - b);
    return expected.length === actual.length && expected.every((index, position) => index === actual[position]);
  }
  return selectedIndexes.length === stage.options.length && selectedIndexes.every((index, position) => index === stage.sequenceOrder?.[position]);
}

function getJourneyInteractionLabel(interaction: JourneyInteraction) {
  if (interaction === "pair") return "证据配对";
  if (interaction === "sequence") return "关系排序";
  return "线索识别";
}

function getJourneyInteractionInstruction(interaction: JourneyInteraction) {
  if (interaction === "pair") return "玩法：从线索卡中选出两张，完成一组“证据 + 关系”配对。";
  if (interaction === "sequence") return "玩法：按历史发展的顺序依次点击三张章节卡。";
  return "玩法：判断最能接上当前历史线索的一张卡。";
}

type InvestigationActionId = "observe" | "archive" | "listen";

const INVESTIGATION_ACTIONS: { id: InvestigationActionId; label: string; description: string }[] = [
  { id: "observe", label: "观察器物", description: "不消耗资源，从形制、名称或纹样中自己找证据" },
  { id: "archive", label: "查阅档案", description: "自动打开本关提示，从制度和背景中确认关系" },
  { id: "listen", label: "听取讲解", description: "返还 1 次洞察，从口述线索中捕捉文化联系" },
];

function getInvestigationActionLabel(action: InvestigationActionId) {
  return INVESTIGATION_ACTIONS.find((item) => item.id === action)?.label ?? "未选择";
}

function getInvestigationNote(action: InvestigationActionId, stage: PreparedJourneyStage) {
  if (action === "observe") return `观察记录：先留意“${stage.reward}”的名称、形制或可见线索，再判断它与${stage.chapter}的关系。`;
  if (action === "archive") return `档案记录：本关要追踪的是“${CHAPTER_EXPLANATIONS[stage.chapter]}”，不要只看单件文物。`;
  return `讲解记录：${stage.explanation.split("。")[0]}。把这句话和你在现场看到的证据放在一起思考。`;
}

type EvidenceLink = {
  clues: [string, string];
  chapter: JourneyChapter;
  explanation: string;
};

function getEvidenceLinkKey(clues: [string, string] | string[]) {
  return [...clues].sort().join("::");
}

const EVIDENCE_LINKS: EvidenceLink[] = [
  { clues: ["唐崖长官司印", "土司制度"], chapter: "交往", explanation: "印章是地方治理的器物证据，土司制度让地方首领与中央治理体系建立联系。" },
  { clues: ["文化传播", "凤凰八卦铜镜"], chapter: "交流", explanation: "文化传播提供背景，铜镜上的凤凰与八卦纹样提供器物观察入口。" },
  { clues: ["土司制度", "改土归流"], chapter: "交融", explanation: "从土司制度到改土归流，可以观察制度联系逐步加深的历史过程。" },
  { clues: ["唐崖土司牌坊", "唐崖长官司印"], chapter: "交往", explanation: "牌坊与长官司印把唐崖土司相关遗存和地方治理线索放回同一条探索路线。" },
  { clues: ["文化传播", "交融共生"], chapter: "交融", explanation: "文化传播是理解不同群体相互影响、走向交融共生的一条重要线索。" },
];

type JourneyEvidenceBoardProps = {
  unlockedClues: string[];
  selectedClues: string[];
  connectedLinks: string[];
  requiredLink?: [string, string];
  feedback: string;
  onSelectClue: (clue: string) => void;
};

function JourneyEvidenceBoard({ unlockedClues, selectedClues, connectedLinks, requiredLink, feedback, onSelectClue }: JourneyEvidenceBoardProps) {
  const requiredKey = requiredLink ? getEvidenceLinkKey(requiredLink) : null;
  const coreConnected = requiredKey ? connectedLinks.includes(requiredKey) : false;
  const connectedEvidence = EVIDENCE_LINKS.filter((link) => connectedLinks.includes(getEvidenceLinkKey(link.clues)));

  return (
    <section className="journey-evidence-board" aria-labelledby="journey-evidence-board-title">
      <div className="journey-evidence-heading">
        <div>
          <p className="journey-map-eyebrow">调查工具 · 证据关系板</p>
          <h3 id="journey-evidence-board-title">把线索连成关系</h3>
        </div>
        <span>{selectedClues.length}/2 已选择</span>
      </div>
      <p className="journey-evidence-intro">选择两张已解锁的线索，尝试建立它们之间的历史关系。连线成功后，这条关系会留在你的调查档案里。</p>
      {requiredLink && <p className={`journey-evidence-goal ${coreConnected ? "complete" : ""}`}><b>本关关系目标：</b>{requiredLink[0]} + {requiredLink[1]} {coreConnected ? "✓ 已连通" : "· 待连通"}</p>}
      <div className="journey-evidence-cards">
        {unlockedClues.map((clue) => {
          const selected = selectedClues.includes(clue);
          const hasConnection = connectedLinks.some((key) => key.split("::").includes(clue));
          return <button className={`journey-evidence-card ${selected ? "selected" : ""} ${hasConnection ? "connected" : ""}`} key={clue} type="button" onClick={() => onSelectClue(clue)} aria-pressed={selected}><span>{selected ? selectedClues.indexOf(clue) + 1 : "◇"}</span><b>{clue}</b><small>{hasConnection ? "已有关系" : "点击加入连线"}</small></button>;
        })}
        {unlockedClues.length === 0 && <div className="journey-evidence-empty">完成第一关后，线索会出现在这里。</div>}
      </div>
      {feedback && <p className={`journey-evidence-feedback ${feedback.includes("已连通") ? "success" : "warning"}`}>{feedback}</p>}
      {connectedEvidence.length > 0 && <div className="journey-evidence-links"><span>已建立关系</span>{connectedEvidence.map((link) => <small key={getEvidenceLinkKey(link.clues)}>{link.clues[0]} → {link.clues[1]} · {link.chapter}</small>)}</div>}
    </section>
  );
}

const JOURNEY_STAGES: JourneyStage[] = [
  {
    id: "contact-audio",
    chapter: "交往",
    stopId: "enshi",
    interaction: "single",
    title: "听见遗产的声音",
    prompt: "听完这段馆藏讲解，你认为它对应哪件文物？",
    hint: "先注意声音线索所属的唐崖土司相关遗存，再选择文物名称。",
    options: [
      { label: "唐崖土司牌坊", clue: "声音 → 唐崖土司遗存" },
      { label: "唐崖长官司印", clue: "声音 → 地方治理文物" },
      { label: "凤凰八卦铜镜", clue: "声音 → 铜镜纹样" },
      { label: "虎纽錞于", clue: "声音 → 青铜乐器" },
    ],
    correctIndex: 0,
    explanation: "这段声音线索来自“唐崖土司牌坊”的馆藏关联音频，先从声音建立文物与地点的关系。",
    source: "馆藏关联媒体：唐崖土司牌坊音频",
    reward: "唐崖土司牌坊",
  },
  {
    id: "contact-01",
    chapter: "交往",
    stopId: "xianfeng",
    interaction: "pair",
    title: "把文物接到它的作用",
    prompt: "从线索卡中各选一张：哪两张能把“唐崖长官司印”接到三交主线？",
    hint: "需要一张文物卡，再接上一张说明它历史作用的关系卡。",
    options: [
      { label: "文物：唐崖长官司印", clue: "器物证据", tag: "文物" },
      { label: "文物：凤凰八卦铜镜", clue: "另一条器物线索", tag: "干扰" },
      { label: "文物：虎纽錞于", clue: "另一条器物线索", tag: "干扰" },
      { label: "关系：地方首领被纳入治理体系", clue: "制度联系", tag: "关系" },
      { label: "关系：只用于海外贸易", clue: "不符合当前线索", tag: "干扰" },
      { label: "关系：只负责修建道路", clue: "不符合当前线索", tag: "干扰" },
    ],
    correctIndexes: [0, 3],
    explanation: "印章是地方治理的器物证据；把它和“地方首领被纳入治理体系”放在一起，才能看见交往如何发生。",
    source: "馆藏目录：唐崖长官司印",
    reward: "唐崖长官司印",
  },
  {
    id: "contact-02",
    chapter: "交往",
    stopId: "xianfeng",
    interaction: "single",
    title: "让关系真正发生",
    prompt: "元代设置土司，最重要的历史作用之一是什么？",
    hint: "想一想地方首领与中央王朝之间建立了怎样的治理关系。",
    options: [
      { label: "将边地首领纳入中央王朝治理体系", clue: "首领 ↔ 治理体系" },
      { label: "完全取消地方治理", clue: "地方 → 无治理" },
      { label: "只管理海外贸易", clue: "土司 → 海外贸易" },
      { label: "只负责修建道路", clue: "土司 → 道路工程" },
    ],
    correctIndex: 0,
    evidenceLink: ["唐崖长官司印", "土司制度"],
    explanation: "元代通过设置土司，逐步将边地民族地区首领纳入治理体系。",
    source: "《元明清之际三交史背景信息》",
    reward: "土司制度",
  },
  {
    id: "exchange-01",
    chapter: "交流",
    stopId: "xianfeng",
    interaction: "pair",
    title: "找出文化传播的完整证据",
    prompt: "从线索卡中各选一张：哪两张能证明文化在土司地区发生了交流？",
    hint: "一张卡说明“传播了什么”，另一张卡说明“传播带来了什么”。",
    options: [
      { label: "文化：儒、释、道文化", clue: "思想与信仰", tag: "文化" },
      { label: "文化：只传播一种外来文字", clue: "单一传播", tag: "干扰" },
      { label: "文化：只传播航海技术", clue: "单一传播", tag: "干扰" },
      { label: "结果：在土司地区传播并促进交融", clue: "传播结果", tag: "结果" },
      { label: "结果：文化从未离开原地", clue: "与传播相反", tag: "干扰" },
      { label: "结果：只形成经济竞争", clue: "缩小了文化影响", tag: "干扰" },
    ],
    correctIndexes: [0, 3],
    explanation: "儒、释、道文化是传播内容，“在土司地区传播并促进交融”是它产生的历史结果，两张卡合起来才构成交流证据。",
    source: "《元明清之际三交史背景信息》",
    reward: "文化传播",
  },
  {
    id: "exchange-02",
    chapter: "交流",
    stopId: "tangya",
    interaction: "pair",
    title: "从器物中找出交流痕迹",
    prompt: "从线索卡中各选一张：哪两张能把“凤凰八卦铜镜”连到文化交流？",
    hint: "先选器物本身，再选它能提示的纹样与信仰线索。",
    options: [
      { label: "器物：凤凰八卦铜镜", clue: "馆藏器物", tag: "器物" },
      { label: "器物：唐崖长官司印", clue: "另一条器物线索", tag: "干扰" },
      { label: "纹样：海浪与帆船", clue: "名称未提示", tag: "干扰" },
      { label: "纹样：凤凰与八卦并置", clue: "纹样与信仰线索", tag: "证据" },
      { label: "纹样：葡萄与莲花", clue: "名称未提示", tag: "干扰" },
      { label: "纹样：山水与人物画像", clue: "名称未提示", tag: "干扰" },
    ],
    correctIndexes: [0, 3],
    evidenceLink: ["文化传播", "凤凰八卦铜镜"],
    explanation: "名称先锁定器物，再由凤凰与八卦并置读出纹样和信仰线索；这就是从器物观察文化交流的入口。",
    source: "馆藏目录：凤凰八卦铜镜",
    reward: "凤凰八卦铜镜",
  },
  {
    id: "fusion-01",
    chapter: "交融",
    stopId: "tangya",
    interaction: "single",
    title: "判断历史走向",
    prompt: "清代加强中央直接管辖、推动进一步融合的重要政策是？",
    hint: "这是从地方治理走向更深层制度联系的关键线索。",
    options: [
      { label: "改土归流", clue: "制度调整 → 进一步融合" },
      { label: "闭关锁国", clue: "交流 → 关闭" },
      { label: "分封诸侯", clue: "治理 → 分散" },
      { label: "废除州县", clue: "治理 → 撤销" },
    ],
    correctIndex: 0,
    explanation: "“改土归流”促进了边陲地区进一步纳入中央政府管辖。",
    source: "《元明清之际三交史背景信息》",
    reward: "改土归流",
  },
  {
    id: "fusion-02",
    chapter: "交融",
    stopId: "tangya",
    interaction: "sequence",
    title: "把三交关系串成历史发展",
    prompt: "请按历史关系发展的顺序，依次点击三张章节卡，完成最后一条线索链。",
    hint: "先是建立联系，再是传播互鉴，最后才是共同发展与认同。",
    options: [
      { label: "交往：建立人物、制度与地方之间的联系", clue: "第一步：建立联系", tag: "第一步" },
      { label: "交流：观察思想、器物与文化如何传播互鉴", clue: "第二步：传播互鉴", tag: "第二步" },
      { label: "交融：理解共同发展与文化认同", clue: "第三步：共同发展", tag: "第三步" },
    ],
    sequenceOrder: [0, 1, 2],
    evidenceLink: ["土司制度", "改土归流"],
    explanation: "把制度联系、文化传播和共同发展依次串起，才能理解元明清时期土司地区由交往、交流走向交融共生的历史过程。",
    source: "《元明清之际三交史背景信息》",
    reward: "交融共生",
  },
];

function prepareJourneyStage(stage: JourneyStage): PreparedJourneyStage {
  const indexedOptions = stage.options.map((option, index) => ({ option, index }));
  const shuffledOptions = shuffle(indexedOptions);
  return {
    ...stage,
    options: shuffledOptions.map(({ option }) => option),
    correctIndex: stage.correctIndex === undefined
      ? undefined
      : shuffledOptions.findIndex(({ index }) => index === stage.correctIndex),
    correctIndexes: stage.correctIndexes?.map((correctIndex) => shuffledOptions.findIndex(({ index }) => index === correctIndex)),
    sequenceOrder: stage.sequenceOrder?.map((sequenceIndex) => shuffledOptions.findIndex(({ index }) => index === sequenceIndex)),
  };
}

function createJourney(): PreparedJourneyStage[] {
  return JOURNEY_STAGES.map(prepareJourneyStage);
}

const CLUE_DETAILS: Record<string, { detail: string; source: string }> = {
  "唐崖土司牌坊": { detail: "馆藏声音线索把文物与唐崖土司相关遗存连接起来。", source: "馆藏关联媒体：唐崖土司牌坊音频" },
  "唐崖长官司印": { detail: "这是理解唐崖土司及地方治理历史的重要文物线索。", source: "馆藏目录：唐崖长官司印" },
  "土司制度": { detail: "元代设置土司，逐步将边地民族地区首领纳入治理体系。", source: "《元明清之际三交史背景信息》" },
  "文化传播": { detail: "儒、释、道文化的传播，是促进民族文化交融的因素之一。", source: "《元明清之际三交史背景信息》" },
  "凤凰八卦铜镜": { detail: "名称本身提示了凤凰和八卦两类纹样，是识别文物的基础线索。", source: "馆藏目录：凤凰八卦铜镜" },
  "改土归流": { detail: "这一政策促进了边陲地区进一步纳入中央政府管辖。", source: "《元明清之际三交史背景信息》" },
  "交融共生": { detail: "元明清时期土司地区关系呈现由控制与冲突走向交融共生的趋势。", source: "《元明清之际三交史背景信息》" },
};

const JOURNEY_RECOMMENDATIONS = [
  { name: "唐崖长官司印", reason: "从制度与身份进入三交史" },
  { name: "凤凰八卦铜镜", reason: "观察器物中的文化传播" },
  { name: "“荆南雄镇”牌坊", reason: "把线索放回地方空间" },
];

type JourneyMapStop = {
  id: JourneyStopId;
  code: string;
  title: string;
  subtitle: string;
  description: string;
  position: [number, number];
  color: "blue" | "gold" | "green";
  clues: string[];
};

const JOURNEY_MAP_STOPS: JourneyMapStop[] = [
  {
    id: "enshi",
    code: "恩",
    title: "恩施州博物馆",
    subtitle: "探索起点",
    description: "从馆藏文物出发，收集与三交历史有关的第一条线索。",
    position: [30.2722, 109.488],
    color: "blue",
    clues: ["唐崖土司牌坊"],
  },
  {
    id: "xianfeng",
    code: "咸",
    title: "咸丰县",
    subtitle: "地方治理与文化传播",
    description: "从县域空间继续追踪土司制度、文化传播和地方治理的联系。",
    position: [29.678, 109.14],
    color: "gold",
    clues: ["唐崖长官司印", "土司制度", "文化传播", "改土归流"],
  },
  {
    id: "tangya",
    code: "唐",
    title: "唐崖土司城遗址",
    subtitle: "三交核心 · 世界文化遗产",
    description: "唐崖河畔的土司城遗址，是这段历史路线的核心站点。",
    position: [29.69056, 109.00528],
    color: "green",
    clues: ["唐崖土司牌坊", "唐崖长官司印", "土司制度", "文化传播", "凤凰八卦铜镜", "改土归流", "交融共生"],
  },
];

function getJourneyStopId(stageIndex: number) {
  return JOURNEY_STAGES[stageIndex]?.stopId ?? "enshi";
}

function getAvailableJourneyStopIds(stageIndex: number) {
  const route: JourneyStopId[] = ["enshi", "xianfeng", "tangya"];
  const currentStopIndex = route.indexOf(getJourneyStopId(stageIndex));
  return route.slice(0, currentStopIndex + 1);
}

type JourneyGeoMapProps = {
  unlockedClues: string[];
  selectedClue: string | null;
  onSelectClue: (clue: string) => void;
  activeStopId?: JourneyStopId;
  availableStopIds?: JourneyStopId[];
  progressLabel?: string;
  compact?: boolean;
};

function JourneyGeoMap({ unlockedClues, selectedClue, onSelectClue, activeStopId: requestedStopId = "tangya", availableStopIds = JOURNEY_MAP_STOPS.map((stop) => stop.id), progressLabel = `已点亮 ${unlockedClues.length}/7 条线索`, compact = false }: JourneyGeoMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const [activeStopId, setActiveStopId] = useState(requestedStopId);
  const activeStop = JOURNEY_MAP_STOPS.find((stop) => stop.id === activeStopId) ?? JOURNEY_MAP_STOPS[2];
  const availableStopIdsKey = availableStopIds.join(",");

  useEffect(() => {
    setActiveStopId(requestedStopId);
  }, [requestedStopId]);

  useEffect(() => {
    if (!mapContainerRef.current) return;
    const map = L.map(mapContainerRef.current, { zoomControl: true, scrollWheelZoom: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);

    const route = JOURNEY_MAP_STOPS.map((stop) => stop.position);
    L.polyline(route, { color: "#147b78", weight: 4, opacity: 0.88, dashArray: "9 7" }).addTo(map);
    L.polyline(route, { color: "#ffffff", weight: 9, opacity: 0.8 }).bringToBack();

    JOURNEY_MAP_STOPS.forEach((stop) => {
      const canVisit = availableStopIds.includes(stop.id);
      const icon = L.divIcon({
        className: `journey-leaflet-marker marker-${stop.color} ${canVisit ? "" : "marker-locked"} ${stop.id === requestedStopId ? "marker-current" : ""}`,
        html: `<span>${stop.code}</span>`,
        iconSize: [38, 38],
        iconAnchor: [19, 19],
      });
      const marker = L.marker(stop.position, { icon }).addTo(map);
      if (canVisit) marker.on("click", () => setActiveStopId(stop.id));
    });

    map.fitBounds(L.latLngBounds(route), { padding: [26, 26] });
    return () => {
      map.remove();
    };
  }, [availableStopIdsKey, requestedStopId]);

  return (
    <section className={`journey-exploration-map ${compact ? "compact" : ""}`} aria-labelledby="journey-exploration-map-title">
      <div className="journey-map-heading">
        <div>
          <p className="journey-map-eyebrow">真实地理路线 · 恩施—咸丰—唐崖</p>
          <h3 id="journey-exploration-map-title">三交探索地图</h3>
        </div>
        <span className="journey-map-progress">{progressLabel}</span>
      </div>
      <p className="journey-map-intro">{compact ? "完成下面的任务，地图会带你前往下一站；灰色站点暂时不能前往。" : "沿着真实地理路线走进唐崖土司城，把馆藏线索放回它发生的地方。"}</p>
      <div className="journey-three-key" aria-label="三交历史主线">
        {(["交往", "交流", "交融"] as JourneyChapter[]).map((chapter) => <span className={`chapter-key-${chapter}`} key={chapter}><i />{chapter} · {CHAPTER_EXPLANATIONS[chapter]}</span>)}
      </div>
      <div className="journey-geographic-map" ref={mapContainerRef} aria-label="恩施到唐崖土司城的交互地图" />
      <div className="journey-map-attribution-note">底图：OpenStreetMap · 路线为探索叙事路线，文物线索集中在对应历史站点。</div>
      <div className="journey-map-stations" aria-label="地图站点">
        {JOURNEY_MAP_STOPS.map((stop, index) => {
          const canVisit = availableStopIds.includes(stop.id);
          return <button className={`journey-map-station ${activeStopId === stop.id ? "active" : ""} ${canVisit ? "available" : "locked"}`} key={stop.id} type="button" disabled={!canVisit} onClick={() => setActiveStopId(stop.id)} aria-current={activeStopId === stop.id ? "step" : undefined}>
            <span className={`journey-map-station-dot marker-${stop.color}`}>{index + 1}</span>
            <span><b>{stop.title}</b><small>{canVisit ? stop.subtitle : "完成前置任务后解锁"}</small></span>
          </button>;
        })}
      </div>
      <div className="journey-map-station-detail">
        <div>
          <p className="journey-map-eyebrow">{compact ? "当前任务站点" : "当前站点"}</p>
          <h4>{activeStop.title}</h4>
          <p>{activeStop.description}</p>
        </div>
        {activeStop.clues.length > 0 && (
          <div className="journey-map-station-clues">
            <span>本站线索</span>
            <div>
              {activeStop.clues.map((clue) => {
                const unlocked = unlockedClues.includes(clue);
                return <button className={`journey-map-clue chapter-${getClueChapter(clue)} ${unlocked ? "unlocked" : "locked"} ${selectedClue === clue ? "selected" : ""}`} key={clue} type="button" disabled={!unlocked} onClick={() => onSelectClue(clue)}>{unlocked ? "◇" : "○"} {clue}</button>;
              })}
            </div>
          </div>
        )}
      </div>
      {selectedClue && CLUE_DETAILS[selectedClue] && (
        <aside className="journey-map-detail journey-exploration-detail">
          <b>{selectedClue}</b>
          <p>{CLUE_DETAILS[selectedClue].detail}</p>
          <small>资料依据：{CLUE_DETAILS[selectedClue].source}</small>
        </aside>
      )}
    </section>
  );
}

export function KnowledgeGamePage({ onOpenCollection }: { onOpenCollection?: () => void }) {
  const [stages, setStages] = useState(createJourney);
  const [stageIndex, setStageIndex] = useState(0);
  const [selectedIndexes, setSelectedIndexes] = useState<number[]>([]);
  const [answerSubmitted, setAnswerSubmitted] = useState(false);
  const [investigationAction, setInvestigationAction] = useState<InvestigationActionId | null>(null);
  const [investigationCompleted, setInvestigationCompleted] = useState(false);
  const [observationPoints, setObservationPoints] = useState<string[]>([]);
  const [investigationNote, setInvestigationNote] = useState("");
  const [investigationHistory, setInvestigationHistory] = useState<InvestigationActionId[]>([]);
  const [insightTokens, setInsightTokens] = useState(3);
  const [hintVisible, setHintVisible] = useState(false);
  const [hintUsed, setHintUsed] = useState(false);
  const [wrongAttempts, setWrongAttempts] = useState(0);
  const [firstTryCorrectCount, setFirstTryCorrectCount] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [answers, setAnswers] = useState<JourneyAnswer[]>([]);
  const [unlockedClues, setUnlockedClues] = useState<string[]>([]);
  const [boardSelection, setBoardSelection] = useState<string[]>([]);
  const [connectedLinks, setConnectedLinks] = useState<string[]>([]);
  const [boardFeedback, setBoardFeedback] = useState("");
  const [selectedClue, setSelectedClue] = useState<string | null>(null);
  const [audioClue, setAudioClue] = useState<GameAudioClue | null>(null);
  const [audioError, setAudioError] = useState("");
  const [finished, setFinished] = useState(false);
  const [showGameIntro, setShowGameIntro] = useState(true);
  const current = stages[stageIndex];
  const currentStop = JOURNEY_MAP_STOPS.find((stop) => stop.id === getJourneyStopId(stageIndex)) ?? JOURNEY_MAP_STOPS[0];
  const nextStageStop = stageIndex < stages.length - 1
    ? JOURNEY_MAP_STOPS.find((stop) => stop.id === getJourneyStopId(stageIndex + 1))
    : undefined;
  const nextStop = nextStageStop?.id !== currentStop.id ? nextStageStop : undefined;
  const currentRequiredLinkKey = current.evidenceLink ? getEvidenceLinkKey(current.evidenceLink) : null;
  const currentRequiredLinkConnected = currentRequiredLinkKey ? connectedLinks.includes(currentRequiredLinkKey) : true;
  const isCorrect = answerSubmitted && isJourneySelectionCorrect(current, selectedIndexes);
  const progress = Math.round(((stageIndex + (answerSubmitted ? 1 : 0)) / stages.length) * 100);
  const chapterStats = useMemo(
    () => (["交往", "交流", "交融"] as JourneyChapter[]).map((chapter) => ({
      chapter,
      correct: answers.filter((answer) => answer.stage.chapter === chapter && answer.isCorrect).length,
      total: stages.filter((stage) => stage.chapter === chapter).length,
    })),
    [answers, stages],
  );
  const incorrectAnswers = answers.filter((answer) => !answer.isCorrect);
  const reasoningScore = Math.max(0, 100 - wrongAttempts * 8 - (3 - insightTokens) * 3);
  const coreLinks = JOURNEY_STAGES.filter((stage) => stage.evidenceLink).map((stage) => getEvidenceLinkKey(stage.evidenceLink as [string, string]));
  const completedCoreLinks = coreLinks.filter((key) => connectedLinks.includes(key)).length;
  const primaryInvestigationAction = useMemo(() => {
    const counts = investigationHistory.reduce<Record<InvestigationActionId, number>>((result, action) => ({ ...result, [action]: (result[action] ?? 0) + 1 }), { observe: 0, archive: 0, listen: 0 });
    return (Object.entries(counts).sort(([, countA], [, countB]) => countB - countA)[0]?.[0] ?? "observe") as InvestigationActionId;
  }, [investigationHistory]);

  useEffect(() => {
    void getGameAudioClue().then(setAudioClue).catch(() => setAudioError("声音线索暂时不可用，但不影响继续探索。"));
  }, []);

  function recordJourneyAttempt(selection: number[]) {
    const correct = isJourneySelectionCorrect(current, selection);
    const alreadyAttempted = answers.some((answer) => answer.stage.id === current.id);
    setAnswerSubmitted(true);
    setAnswers((records) => [...records.filter((record) => record.stage.id !== current.id), { stage: current, selectedIndexes: selection, isCorrect: correct }]);
    if (correct) {
      if (!alreadyAttempted && !hintUsed) setFirstTryCorrectCount((count) => count + 1);
      setCorrectCount((count) => count + 1);
      setUnlockedClues((clues) => clues.includes(current.reward) ? clues : [...clues, current.reward]);
    } else {
      setWrongAttempts((count) => count + 1);
    }
  }

  function revealHint() {
    if (hintVisible || answerSubmitted || insightTokens <= 0) return;
    setInsightTokens((count) => count - 1);
    setHintVisible(true);
    setHintUsed(true);
  }

  function chooseInvestigationAction(action: InvestigationActionId) {
    if (investigationAction || answerSubmitted) return;
    setInvestigationAction(action);
    setInvestigationNote(getInvestigationNote(action, current));
    setInvestigationHistory((history) => [...history, action]);
  }

  function inspectObservationPoint(point: string) {
    if (investigationAction !== "observe" || investigationCompleted) return;
    const nextPoints = observationPoints.includes(point) ? observationPoints : [...observationPoints, point];
    setObservationPoints(nextPoints);
    if (nextPoints.length >= 2) {
      setInvestigationCompleted(true);
      setInvestigationNote(`观察完成：你记录了${nextPoints.join("、")}两项证据，现在可以开始判断这条线索。`);
    }
  }

  function completeInvestigationAction() {
    if (!investigationAction || investigationCompleted) return;
    if (investigationAction === "observe") {
      if (observationPoints.length < 2) return;
      setInvestigationCompleted(true);
      return;
    }
    if (investigationAction === "archive") {
      setHintVisible(true);
      setInvestigationCompleted(true);
      setInvestigationNote(`档案已打开：你可以用“${current.hint}”作为背景线索，但仍需要自己完成判断。`);
      return;
    }
    const narration = new SpeechSynthesisUtterance(getInvestigationNote("listen", current));
    narration.lang = "zh-CN";
    window.speechSynthesis?.cancel();
    window.speechSynthesis?.speak(narration);
    setInsightTokens((count) => Math.min(3, count + 1));
    setInvestigationCompleted(true);
    setInvestigationNote("讲解播放完成：你获得了 1 次洞察机会，现在可以开始判断这条线索。");
  }

  function selectEvidenceClue(clue: string) {
    if (!unlockedClues.includes(clue)) return;
    if (boardSelection.includes(clue)) {
      setBoardSelection((selection) => selection.filter((item) => item !== clue));
      setBoardFeedback("");
      return;
    }
    const selection = boardSelection.length >= 2 ? [clue] : [...boardSelection, clue];
    setBoardSelection(selection);
    setBoardFeedback("");
    if (selection.length < 2) return;
    const link = EVIDENCE_LINKS.find((candidate) => getEvidenceLinkKey(candidate.clues) === getEvidenceLinkKey(selection));
    if (!link) {
      setBoardFeedback("这两条线索暂时没有直接关系，再换一张试试。");
      setWrongAttempts((count) => count + 1);
      return;
    }
    const key = getEvidenceLinkKey(link.clues);
    setConnectedLinks((links) => links.includes(key) ? links : [...links, key]);
    setBoardFeedback(`关系已连通：${link.clues[0]} + ${link.clues[1]} · ${link.chapter}`);
  }

  function chooseAnswer(index: number) {
    if (answerSubmitted || !investigationAction || !investigationCompleted) return;
    if (current.interaction === "single") {
      const selection = [index];
      setSelectedIndexes(selection);
      recordJourneyAttempt(selection);
      return;
    }
    if (current.interaction === "pair") {
      const selection = selectedIndexes.includes(index)
        ? selectedIndexes.filter((selected) => selected !== index)
        : selectedIndexes.length < 2
          ? [...selectedIndexes, index]
          : selectedIndexes;
      setSelectedIndexes(selection);
      if (selection.length === 2) recordJourneyAttempt(selection);
      return;
    }
    const selection = selectedIndexes.includes(index) ? selectedIndexes : [...selectedIndexes, index];
    setSelectedIndexes(selection);
    if (selection.length === current.options.length) recordJourneyAttempt(selection);
  }

  function retryCurrentStage() {
    setSelectedIndexes([]);
    setAnswerSubmitted(false);
  }

  function continueJourney() {
    if (current.evidenceLink && !currentRequiredLinkConnected) {
      setBoardFeedback(`请先在证据板上连通“${current.evidenceLink[0]} + ${current.evidenceLink[1]}”。`);
      return;
    }
    if (stageIndex === stages.length - 1) {
      setFinished(true);
      return;
    }
    setStageIndex((index) => index + 1);
    setSelectedIndexes([]);
    setAnswerSubmitted(false);
    setInvestigationAction(null);
    setInvestigationCompleted(false);
    setObservationPoints([]);
    setInvestigationNote("");
    setBoardSelection([]);
    setBoardFeedback("");
    setHintVisible(false);
    setHintUsed(false);
  }

  function restartJourney() {
    setStages(createJourney());
    setStageIndex(0);
    setSelectedIndexes([]);
    setAnswerSubmitted(false);
    setInvestigationAction(null);
    setInvestigationCompleted(false);
    setObservationPoints([]);
    setInvestigationNote("");
    setInvestigationHistory([]);
    setInsightTokens(3);
    setHintVisible(false);
    setHintUsed(false);
    setCorrectCount(0);
    setAnswers([]);
    setUnlockedClues([]);
    setBoardSelection([]);
    setConnectedLinks([]);
    setBoardFeedback("");
    setWrongAttempts(0);
    setFirstTryCorrectCount(0);
    setSelectedClue(null);
    setFinished(false);
    setShowGameIntro(true);
  }

  function startJourney() {
    setShowGameIntro(false);
  }

  if (showGameIntro) {
    return (
      <section className="game-panel journey-intro-panel" aria-labelledby="journey-intro-title">
        <p className="game-kicker">互动探索 · 三交史旅程</p>
        <h2 id="journey-intro-title">三交探索地图怎么玩？</h2>
        <p className="journey-intro-lead">你将从恩施出发，沿着真实地理路线完成 7 个历史任务。这里不是单纯答题，而是收集证据、建立关系，最后把“交往 → 交流 → 交融”连成一条历史线索。</p>
        <div className="journey-how-to-play" aria-label="玩法说明">
          <article><span>1</span><div><b>看地图</b><p>蓝色站点是当前位置，灰色站点需要完成前置任务后才能前往。</p></div></article>
          <article><span>2</span><div><b>选调查行动</b><p>每个任务先决定观察器物、查阅档案还是听取讲解，再开始推理。</p></div></article>
          <article><span>3</span><div><b>找证据</b><p>不同关卡会要求你识别线索、配对证据，或按顺序串起历史关系；每轮还有 3 次洞察机会。</p></div></article>
          <article><span>4</span><div><b>连成三交</b><p>每完成一关就点亮一张线索卡，最后要把交往、交流、交融排成完整关系链。</p></div></article>
        </div>
        <div className="journey-intro-route" aria-label="探索路线">
          <span className="intro-route-stop blue">恩施州博物馆</span><i>→</i><span className="intro-route-stop gold">咸丰县</span><i>→</i><span className="intro-route-stop green">唐崖土司城</span>
        </div>
        <button className="game-primary journey-start-button" type="button" onClick={startJourney}>开始三交探索</button>
      </section>
    );
  }

  if (finished) {
    return (
      <section className="game-panel journey-summary" aria-live="polite">
        <p className="game-kicker">三交探索完成</p>
        <div className="game-score">{correctCount}/{stages.length}</div>
        <p className="game-badge">{wrongAttempts === 0 ? "三交史完美调查员" : wrongAttempts <= 2 ? "三交史叙事大师" : "三交史探索者"}</p>
        <h2>{correctCount >= 4 ? "你已经把几条历史线索连起来了！" : "再探索一次，把线索连接得更完整。"}</h2>
        <p>你刚刚经历了“交往 → 交流 → 交融”的三章旅程。每条解锁的线索，都来自本地馆藏或已入库资料。</p>
        <div className="journey-score-breakdown" aria-label="本轮推理成绩">
          <span><small>推理完成度</small><b>{reasoningScore}%</b></span>
          <span><small>首轮连通</small><b>{firstTryCorrectCount}/{stages.length}</b></span>
          <span><small>误判次数</small><b>{wrongAttempts}</b></span>
          <span><small>核心连线</small><b>{completedCoreLinks}/{coreLinks.length}</b></span>
        </div>
        <p className="journey-investigation-summary">本轮主要调查方式：<b>{getInvestigationActionLabel(primaryInvestigationAction)}</b> · 已完成 {investigationHistory.length} 次现场行动</p>
        <section className="journey-achievements" aria-labelledby="journey-achievements-title">
          <div className="journey-section-heading"><div><p className="journey-map-eyebrow">探索成就</p><h3 id="journey-achievements-title">你的三交调查档案</h3></div><span>{Math.min(4, 1 + (wrongAttempts === 0 ? 1 : 0) + (completedCoreLinks >= 2 ? 1 : 0) + (unlockedClues.length >= 6 ? 1 : 0))}/4 已解锁</span></div>
          <div className="journey-achievement-grid">
            <article className="journey-achievement unlocked"><span>✦</span><div><b>三交史探索者</b><small>完成一次完整历史旅程</small></div></article>
            <article className={`journey-achievement ${wrongAttempts === 0 ? "unlocked" : "locked"}`}><span>◇</span><div><b>完美调查员</b><small>{wrongAttempts === 0 ? "全程保持零误判" : "全程零误判后解锁"}</small></div></article>
            <article className={`journey-achievement ${completedCoreLinks >= 2 ? "unlocked" : "locked"}`}><span>↗</span><div><b>关系建构者</b><small>{completedCoreLinks >= 2 ? "建立了两条核心关系" : "建立两条核心关系后解锁"}</small></div></article>
            <article className={`journey-achievement ${unlockedClues.length >= 6 ? "unlocked" : "locked"}`}><span>▣</span><div><b>线索收藏家</b><small>{unlockedClues.length >= 6 ? "收集了六条以上线索" : "收集六条线索后解锁"}</small></div></article>
          </div>
        </section>
        <div className="journey-chapter-report" aria-label="三章探索结果">
          {chapterStats.map((item) => (
            <article className="journey-chapter-card" key={item.chapter}>
              <span>{item.chapter}</span>
              <b>{item.correct}/{item.total}</b>
              <small>{CHAPTER_EXPLANATIONS[item.chapter]}</small>
              <small>{item.correct === item.total ? "线索已连通" : "还有线索待发现"}</small>
            </article>
          ))}
        </div>
        <JourneyGeoMap unlockedClues={unlockedClues} selectedClue={selectedClue} onSelectClue={setSelectedClue} activeStopId="tangya" progressLabel={`已点亮 ${unlockedClues.length}/7 条线索`} />
        <section className="journey-map" aria-labelledby="journey-relation-title">
          <h3 id="journey-relation-title">三交关系图 · 线索连接</h3>
          <div className="journey-map-track">
            {chapterStats.map((item, index) => {
              const chapterClues = item.chapter === "交往"
                ? ["唐崖土司牌坊", "唐崖长官司印", "土司制度"]
                : item.chapter === "交流"
                  ? ["文化传播", "凤凰八卦铜镜"]
                  : ["改土归流", "交融共生"];
              return (
                <div className="journey-map-group" key={item.chapter}>
                  <span className="journey-map-label">{item.chapter}</span>
                  {chapterClues.map((clue) => {
                    const isUnlocked = unlockedClues.includes(clue);
                    return <button className={`journey-map-node ${isUnlocked ? "unlocked" : "locked"}`} key={clue} type="button" disabled={!isUnlocked} onClick={() => setSelectedClue(clue)} aria-pressed={selectedClue === clue}>{isUnlocked ? "◇ " : "○ "}{clue}</button>;
                  })}
                  {index < 2 && <span className="journey-map-arrow" aria-hidden="true">→</span>}
                </div>
              );
            })}
          </div>
          {selectedClue && CLUE_DETAILS[selectedClue] && (
            <aside className="journey-map-detail">
              <b>{selectedClue}</b>
              <p>{CLUE_DETAILS[selectedClue].detail}</p>
              <small>资料依据：{CLUE_DETAILS[selectedClue].source}</small>
            </aside>
          )}
          <p>把文物、制度和文化线索连起来，才能看到从交往到交融的历史过程。</p>
        </section>
        <section className="journey-clues" aria-labelledby="journey-clues-title">
          <h3 id="journey-clues-title">你的三交线索册</h3>
          <div className="journey-clue-list">
            {unlockedClues.map((clue) => <span key={clue}>◇ {clue}</span>)}
            {unlockedClues.length === 0 && <small>本轮还没有解锁线索，再试一次吧。</small>}
          </div>
        </section>
        <section className="journey-recommendations" aria-labelledby="journey-recommendations-title">
          <div className="journey-section-heading"><div><p className="journey-map-eyebrow">把游戏带回展厅</p><h3 id="journey-recommendations-title">继续看看这些文物</h3></div><span>三交主题推荐</span></div>
          <div className="journey-recommendation-grid">
            {JOURNEY_RECOMMENDATIONS.map((item, index) => <article key={item.name}><span>0{index + 1}</span><div><b>{item.name}</b><small>{item.reason}</small></div></article>)}
          </div>
          {onOpenCollection && <button className="game-secondary journey-collection-button" type="button" onClick={onOpenCollection}>进入馆藏导览 →</button>}
        </section>
        {incorrectAnswers.length > 0 && (
          <section className="game-review journey-review" aria-labelledby="journey-review-title">
            <h3 id="journey-review-title">需要重新连接的线索</h3>
            <div className="game-review-list">
              {incorrectAnswers.map((answer) => (
                <article className="game-review-item" key={answer.stage.id}>
                  <b>{answer.stage.title}</b>
                  <p>你的选择：{answer.selectedIndexes.map((index) => answer.stage.options[index].label).join("、")}</p>
                  <p>更合适的线索：{answer.stage.interaction === "pair"
                    ? (answer.stage.correctIndexes ?? []).map((index) => answer.stage.options[index].label).join("、")
                    : answer.stage.interaction === "sequence"
                      ? (answer.stage.sequenceOrder ?? []).map((index) => answer.stage.options[index].label).join(" → ")
                      : answer.stage.options[answer.stage.correctIndex ?? 0].label}</p>
                </article>
              ))}
            </div>
          </section>
        )}
        <div className="journey-summary-actions"><button className="game-secondary" type="button" onClick={() => window.print()}>打印 / 保存探索报告</button><button className="game-primary" type="button" onClick={restartJourney}>重新开启三交之旅</button></div>
      </section>
    );
  }

  const nextChapter = stageIndex < stages.length - 1 ? stages[stageIndex + 1].chapter : "报告";
  return (
    <section className="game-panel journey-panel" aria-live="polite">
      <header className="game-header">
        <div>
          <p className="game-kicker">互动探索 · 三交史旅程</p>
          <h2>从一件文物，走进一段关系</h2>
        </div>
        <div className="game-count" aria-label={`第 ${stageIndex + 1} 个线索，共 ${stages.length} 个线索`}>{stageIndex + 1} / {stages.length}</div>
      </header>
      <div className="journey-chapters" aria-label="三交旅程章节">
        {(["交往", "交流", "交融"] as JourneyChapter[]).map((chapter) => {
          const active = current.chapter === chapter;
          const complete = stages.findIndex((stage) => stage.chapter === chapter) < stageIndex;
          return <span className={`${active ? "active" : ""} ${complete ? "complete" : ""}`} key={chapter}>{complete ? "✓ " : ""}{chapter}</span>;
        })}
      </div>
      <div className="game-progress" aria-label={`探索进度 ${progress}%`} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{ width: `${progress}%` }} /></div>
      <div className="journey-taskbar" aria-label="当前任务和下一站">
        <div><span>当前站点</span><b>{currentStop.title}</b><small>{currentStop.subtitle}</small></div>
        <div className="journey-taskbar-arrow" aria-hidden="true">→</div>
        <div><span>当前任务 · {current.chapter}</span><b>{current.title}</b><small>{CHAPTER_EXPLANATIONS[current.chapter]} · {nextStop ? `完成后前往：${nextStop.title}` : "完成后生成探索报告"}</small></div>
      </div>
      <JourneyGeoMap unlockedClues={unlockedClues} selectedClue={selectedClue} onSelectClue={setSelectedClue} activeStopId={getJourneyStopId(stageIndex)} availableStopIds={getAvailableJourneyStopIds(stageIndex)} progressLabel={`当前任务 ${stageIndex + 1}/${stages.length}`} compact />
      <JourneyEvidenceBoard unlockedClues={unlockedClues} selectedClues={boardSelection} connectedLinks={connectedLinks} requiredLink={current.evidenceLink} feedback={boardFeedback} onSelectClue={selectEvidenceClue} />
      <section className="journey-investigation-board" aria-labelledby="journey-investigation-title">
        <div className="journey-evidence-heading">
          <div>
            <p className="journey-map-eyebrow">调查行动 · 当前站点</p>
            <h3 id="journey-investigation-title">你准备怎么查？</h3>
          </div>
          <span>{investigationAction ? `已选择：${getInvestigationActionLabel(investigationAction)}` : "请选择一种行动"}</span>
        </div>
        <div className="journey-investigation-actions">
          {INVESTIGATION_ACTIONS.map((action) => <button className={`journey-investigation-action ${investigationAction === action.id ? "selected" : ""}`} key={action.id} type="button" onClick={() => chooseInvestigationAction(action.id)} disabled={investigationAction !== null || answerSubmitted} aria-pressed={investigationAction === action.id}><b>{action.label}</b><small>{action.description}</small></button>)}
        </div>
        {investigationNote && <p className="journey-investigation-note">{investigationNote}</p>}
        {investigationAction === "observe" && !investigationCompleted && (
          <div className="journey-action-workbench">
            <b>观察镜 · 点击至少两个观察点</b>
            <div className="journey-observation-points">
              {[
                ["名称", `展签确认：${current.reward}`],
                ["关系", `本关主题：${current.chapter} · ${CHAPTER_EXPLANATIONS[current.chapter]}`],
                ["地点", `现场位置：${currentStop.title}`],
              ].map(([point, detail]) => <button className={`journey-observation-point ${observationPoints.includes(point) ? "selected" : ""}`} key={point} type="button" onClick={() => inspectObservationPoint(point)}><span>{observationPoints.includes(point) ? "✓" : "＋"}</span><b>{point}</b><small>{observationPoints.includes(point) ? detail : "点击查看"}</small></button>)}
            </div>
          </div>
        )}
        {investigationAction === "archive" && !investigationCompleted && (
          <div className="journey-action-workbench journey-archive-workbench"><div><b>地方档案 · 未打开</b><small>这份档案记录了本关的历史背景，不会直接告诉你答案。</small></div><button className="game-secondary" type="button" onClick={completeInvestigationAction}>翻开档案</button></div>
        )}
        {investigationAction === "listen" && !investigationCompleted && (
          <div className="journey-action-workbench journey-listen-workbench"><div><b>馆藏讲解 · 待播放</b><small>播放一段现场讲解，听完后会获得一次洞察机会。</small></div><button className="game-secondary" type="button" onClick={completeInvestigationAction}>▶ 播放讲解</button></div>
        )}
        {investigationCompleted && <p className="journey-investigation-complete">✓ 调查行动已完成，现在可以处理下面的历史线索。</p>}
      </section>
      {current.id === "contact-audio" && (
        <aside className="journey-audio-clue" aria-label="馆藏声音线索">
          <div><b>馆藏声音线索</b><small>听一段唐崖土司相关讲解，再开始连接第一条关系。</small></div>
          {audioClue ? <audio controls preload="metadata" src={audioClue.url}>浏览器不支持音频播放。</audio> : <span>{audioError || "正在读取声音线索…"}</span>}
        </aside>
      )}
      <article className="journey-stage-card">
        <div className="journey-stage-topline"><span className="journey-stage-type">{current.chapter} · {current.id === "contact-audio" ? "声音线索" : getJourneyInteractionLabel(current.interaction)}</span><span>解锁：{current.reward}</span></div>
        <h3 className="game-question">{current.title}</h3>
        <p className="journey-prompt">{current.prompt}</p>
        {hintVisible
          ? <p className="journey-hint">提示：{current.hint}</p>
          : <div className="journey-hint-locked"><span>提示已隐藏，先自己观察线索</span><button className="game-secondary" type="button" onClick={revealHint} disabled={answerSubmitted || insightTokens === 0}>{insightTokens > 0 ? `查看提示 · 消耗 1 次洞察（剩余 ${insightTokens}）` : "洞察次数已用完"}</button></div>}
        <p className="journey-action-note">{!investigationAction ? "先选择一种调查行动，才能开始处理这组历史线索。" : !investigationCompleted ? "完成上方调查动作后，历史线索才会解锁。" : getJourneyInteractionInstruction(current.interaction)}{current.interaction === "pair" && ` 已选 ${selectedIndexes.length}/2`}{current.interaction === "sequence" && ` 已排 ${selectedIndexes.length}/${current.options.length}`}</p>
        <div className="journey-options" role="group" aria-label="历史线索选项">
          {current.options.map((option, index) => {
            const selected = selectedIndexes.includes(index);
            const correctOption = current.interaction === "pair"
              ? current.correctIndexes?.includes(index)
              : current.interaction === "sequence"
                ? current.sequenceOrder?.includes(index)
                : index === current.correctIndex;
            const state = !answerSubmitted
              ? selected ? "selected" : ""
              : current.interaction === "sequence"
                ? isCorrect ? "correct" : selected ? "incorrect" : "muted"
                : correctOption ? "correct" : selected ? "incorrect" : "muted";
            const order = selected ? selectedIndexes.indexOf(index) + 1 : null;
            return <button className={`journey-option ${state}`} key={option.label} type="button" onClick={() => chooseAnswer(index)} aria-pressed={selected} disabled={answerSubmitted || !investigationAction || !investigationCompleted}><span>{order ?? String.fromCharCode(65 + index)}</span><b>{option.tag && <em>{option.tag}</em>}{option.label}</b>{(selected || answerSubmitted) && <small>{option.clue}</small>}</button>;
          })}
        </div>
        {answerSubmitted && (
          <aside className={`journey-feedback ${isCorrect ? "correct reveal" : "incorrect"}`}>
            <b>{isCorrect ? `关系已建立 · 解锁“${current.reward}”` : "这条线索暂时接不上"}</b>
            <p>{current.explanation}</p>
            <p className="journey-meaning"><b>{current.chapter}：</b>{CHAPTER_EXPLANATIONS[current.chapter]}</p>
            <small>资料依据：{current.source}</small>
            {isCorrect && current.evidenceLink && !currentRequiredLinkConnected && <p className="journey-board-advance">还差一步：在上方证据板连通本关目标关系，才能推进历史路线。</p>}
            {isCorrect && <p className="journey-route-advance">路线推进：{currentStop.title} → {nextStop?.title ?? "探索报告"}</p>}
            {isCorrect
              ? <button className="game-primary" type="button" onClick={continueJourney}>{current.evidenceLink && !currentRequiredLinkConnected ? "先完成证据连线" : stageIndex === stages.length - 1 ? "生成三交报告" : `进入${nextChapter}`}</button>
              : <button className="game-secondary" type="button" onClick={retryCurrentStage}>看完提示，再选一次</button>}
          </aside>
        )}
      </article>
    </section>
  );
}
