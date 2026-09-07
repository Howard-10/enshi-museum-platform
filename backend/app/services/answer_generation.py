"""Evidence-pack-only chat generation with a strict post-generation citation guard."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, settings
from app.services.citation_validator import CitationValidator
from app.services.model_clients import create_chat_client
from app.services.model_readiness import get_model_readiness


class GeneratedAnswer(BaseModel):
    internal_answer: str = ""
    internal_citations: list[str] = Field(default_factory=list)
    unverified_extension: str | None = None


_INTERNAL_FIELD_REPLACEMENTS = (
    # Use ASCII boundaries instead of ``\b``: Python treats adjacent Chinese
    # characters as word characters, so ``INTERNAL_EVIDENCE中`` would escape
    # a normal word-boundary pattern.
    (re.compile(r"(?<![A-Za-z0-9_])INTERNAL_EVIDENCE(?![A-Za-z0-9_])\s*[:：]?", re.IGNORECASE), "馆内资料"),
    (re.compile(r"(?<![A-Za-z0-9_])EXTERNAL_EVIDENCE(?![A-Za-z0-9_])\s*[:：]?", re.IGNORECASE), "馆外资料"),
    (re.compile(r"(?<![A-Za-z0-9_])USER_QUERY(?![A-Za-z0-9_])\s*[:：]?", re.IGNORECASE), "你的问题"),
    (re.compile(r"(?<![A-Za-z0-9_])SRC_\d+(?![A-Za-z0-9_])", re.IGNORECASE), "馆内来源"),
)


def clean_user_facing_text(value: str | None) -> str | None:
    """Remove prompt-internal field names before text reaches the visitor."""

    if value is None:
        return None
    cleaned = value
    for pattern, replacement in _INTERNAL_FIELD_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)
    # Some compatible chat models ignore the source-id instruction and add
    # their own bracketed source labels. Those labels are implementation
    # details; citations are rendered separately by the frontend.
    cleaned = re.sub(
        r"(?:【|\[|（|\()\s*(?:馆内|馆外)?来源(?:\s*[-–—、,，]\s*(?:馆内|馆外)?来源)*\s*(?:】|\]|）|\))",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\s+([，。；：、！？])", r"\1", cleaned)
    cleaned = re.sub(r"([，。；：、！？])\s+", r"\1", cleaned)
    return cleaned.strip()


def put_relation_conclusion_first(value: str) -> str:
    """Keep the visitor-facing answer focused on the asked relationship."""

    sentences = [part.strip() for part in re.split(r"(?<=[。！？])", value) if part.strip()]
    conclusion_index = next(
        (
            index
            for index, sentence in enumerate(sentences)
            if "三交的直接证据" in sentence or "直接联系起来" in sentence
        ),
        None,
    )
    if conclusion_index is None or conclusion_index == 0:
        return value
    conclusion = sentences.pop(conclusion_index)
    return "".join([conclusion, *sentences])


def build_evidence_pack(
    retrieval: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    allowed: dict[str, dict[str, Any]] = {}
    for index, citation in enumerate(retrieval.get("citations", []), start=1):
        source_id = f"SRC_{index:03d}"
        source = {"source_id": source_id, **citation}
        sources.append(source)
        allowed[source_id] = citation
    return sources, allowed


async def generate_grounded_answer(
    query: str,
    retrieval: dict[str, Any],
    *,
    config: Settings = settings,
) -> tuple[dict[str, Any] | None, str | None]:
    """Generate only when enabled; invalid output is discarded as a whole."""

    if not get_model_readiness(config).chat_generation_enabled:
        return None, "chat_generation_disabled"
    sources, allowed = build_evidence_pack(retrieval)
    if not sources:
        return None, "no_allowed_internal_sources"
    has_internal_source = any(source.get("source_type") == "internal" for source in sources)
    has_external_source = any(source.get("source_type") == "external" for source in sources)
    has_catalog_source = any(
        source.get("source_type") == "internal"
        and source.get("authority_level") == "P1_catalog"
        for source in sources
    )
    has_background_source = any(
        source.get("source_type") == "internal"
        and source.get("authority_level") != "P1_catalog"
        for source in sources
    )
    catalog_only = bool(sources) and has_catalog_source and not has_background_source
    catalog_with_background = has_catalog_source and has_background_source
    catalog_instruction = (
        "回答分成两层：先说明本件文物的标准目录事实，再说明已审核背景资料所支持的三交历史脉络。"
        "背景资料只能解释时代、交流、文化联系等宏观脉络，不能把相似器物的形制、纹饰或用途写成这件文物的事实。"
        "如果背景资料没有明确提到本件文物，不得根据文物名称、纹样或材质自行推断制作、使用、象征意义、传播路径或三交价值。"
        "如果资料没有证明本件与某一事件的直接关系，要明确说现有馆内资料没有记载直接关联。"
        "这时最多补充两句时代背景，不得写‘本件体现、反映、印证、见证了三交’或类似因果判断，"
        "也不得使用诗意、夸张或宣传式表达；不要使用‘可能、可视为、可以认为、推测’等无证据推断。"
        if catalog_with_background
        else ""
    )
    catalog_only_instruction = bool(sources) and all(
        source.get("authority_level") == "P1_catalog" for source in sources
    )
    catalog_only_text = (
        "给定的标准目录是本件文物身份和字段事实的最高依据；只要目录中出现该名称，"
        "就必须承认其已被馆内目录收录，不得回答‘未见该藏品’或把相似文物当成本件。"
        "目录没有提供的字段要明确说‘当前馆内目录未记录’，不得猜测。"
        "此类精确目录问题只回答本件的已确认字段和缺失字段，unverified_extension 必须为空，"
        "不要自动补充泛泛的通用历史背景。"
        if catalog_only_instruction
        else ""
    )
    relation_question = any(word in query for word in ("三交", "关系", "交往", "交流", "交融"))
    relation_instruction = (
        "这是一个关系判断问题。只输出两段、总计约180到260字，严格按下面顺序组织："
        "第一段先给明确结论，再写本件文物的两项馆内确定信息；第二段说明资料是否记载它与三交或某个具体事件的直接关系，"
        "最后只用一句话补充时代背景。背景不得列举其他文物、人物、群体或具体案例。优先使用这句结论：‘现有馆内资料没有把这方文物和某个具体的三交事件直接联系起来，因此不能把它说成三交的直接证据。’"
        "不要罗列其他文物名称，不要把其他文物或背景事件写成这件文物的经历，不要重复结论，"
        "不要使用‘馆内来源’、‘【馆内来源】’、‘[馆内来源]’或任何方括号来源标记。"
        if relation_question
        else ""
    )
    external_instruction = (
        "本次证据包含公开网页补充，不是本馆馆藏档案。回答中必须明确说明‘以下是公开资料补充’，"
        "不得把网页内容写成馆内已经确认的文物事实；只能根据给定网页片段回答，不能自行补充网页未出现的细节。"
        "最多写两段、180字以内；不要补充常识、背景、馆史、馆藏数量、成立年份或其他网页片段没有明确写出的信息。"
        if has_external_source
        else ""
    )
    prompt = (
        "你是面向普通游客的博物馆讲解员。只能依据给定证据写 internal_answer，"
        "不得新增、修改或猜测馆藏事实。可选 unverified_extension 只能写通用历史常识，"
        "并且不得与馆藏事实混写。internal_citations 必须只使用给定 source_id，"
        "每个馆内回答至少一个引用。INTERNAL_EVIDENCE、USER_QUERY、SRC_编号等是内部字段名，"
        "绝对不要在任何输出文字中原样出现。回答要用自然、清楚、面向游客的中文，"
        "避免研究报告腔和空泛套话，不要使用‘最多可以放在……背景下理解’、‘间接历史联系’、"
        "‘直接事例’这类绕口表达。本件事实只能复述证据中明确出现的字段；如果证据只写名称、年代、地点或材质，"
        "不要扩写成使用方式、功能、颁授对象、管辖关系、象征意义或传播路径。背景资料没有明确提到本件时，"
        "不要从名称、纹样或材质推断文化寓意、用途或传播，只能说明时代和地区背景；涉及文物与三交的关系时，遵循后面的关系问题格式。"
        "不要罗列检索到的、但与本件无关的其他文物、展览板块或历史事件。"
        "整段控制在三段以内，避免重复同一结论。"
        f"{catalog_instruction}{catalog_only_text}{relation_instruction}{external_instruction}\n\n"
        f"USER_QUERY:\n{query}\n\nINTERNAL_EVIDENCE:\n{sources}"
    )
    try:
        structured = create_chat_client(config).with_structured_output(GeneratedAnswer)
        result = await structured.ainvoke(prompt)
        generated = (
            result.model_dump()
            if isinstance(result, GeneratedAnswer)
            else GeneratedAnswer.model_validate(result).model_dump()
        )
    except Exception as error:  # noqa: BLE001 -- provider errors must transparently degrade.
        return None, f"chat_generation_error:{type(error).__name__}"
    generated["internal_answer"] = clean_user_facing_text(generated.get("internal_answer")) or ""
    generated["unverified_extension"] = clean_user_facing_text(generated.get("unverified_extension"))
    if relation_question:
        generated["internal_answer"] = put_relation_conclusion_first(generated["internal_answer"])
    if catalog_only:
        generated["unverified_extension"] = None
    if has_external_source and not has_internal_source:
        generated["unverified_extension"] = None
    validation = CitationValidator().validate(generated, set(allowed))
    if not validation.valid:
        return None, validation.reason_code
    citations = [
        {
            "source_type": allowed[source_id].get("source_type", "internal"),
            "id": source_id,
            **{key: value for key, value in allowed[source_id].items() if key != "id"},
        }
        for source_id in generated["internal_citations"]
    ]
    return {
        "answer": generated["internal_answer"],
        "citations": citations,
        "unverified_extension": generated.get("unverified_extension"),
        "answer_scope": "external_search"
        if has_external_source
        else "internal_plus_general"
        if generated.get("unverified_extension")
        else "internal_only",
    }, None
