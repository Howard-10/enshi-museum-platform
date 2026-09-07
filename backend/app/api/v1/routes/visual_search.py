"""Visitor-facing visual lookup against the approved museum catalog."""

from __future__ import annotations

import base64
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from langchain_core.messages import HumanMessage
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.core import Artifact, ArtifactCatalogRecord, ArtifactMediaLink, Document, MediaAsset
from app.db.session import get_db_session
from app.schemas.visual_search import (
    RecognizedArtifact,
    VisualIdentification,
    VisualSearchResponse,
)
from app.services.answer_generation import generate_grounded_answer
from app.services.model_clients import create_chat_client
from app.services.model_readiness import get_model_readiness
from app.services.rag_pipeline import RagPipeline
from app.services.visual_similarity import search_similar_images

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]

MAX_IMAGE_BYTES = 20 * 1024 * 1024
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MIN_MATCH_CONFIDENCE = 0.55
MIN_MODEL_MATCH_CONFIDENCE = 0.90


def _fallback_answer(artifact: dict[str, object]) -> str:
    facts = [
        f"时代：{artifact['era']}" if artifact.get("era") else None,
        f"地点：{artifact['location']}" if artifact.get("location") else None,
        f"材质：{artifact['material']}" if artifact.get("material") else None,
    ]
    fact_text = "；".join(item for item in facts if item)
    return (
        f"图片与馆藏目录中的“{artifact['name']}”最匹配。"
        + (f"目录信息：{fact_text}。" if fact_text else "目前目录中暂未记录更多基本信息。")
    )


@router.post("", response_model=VisualSearchResponse)
async def visual_search(
    session: DbSession,
    image: UploadFile = File(..., description="待识别的文物图片"),
) -> VisualSearchResponse:
    """Identify an uploaded image and ground the result in the museum catalog."""

    content_type = (image.content_type or "").lower()
    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="仅支持 JPG、PNG 或 WebP 图片。")

    content = await image.read(MAX_IMAGE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="上传的图片为空。")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="图片不能超过 20MB。")

    readiness = get_model_readiness(settings)
    if not readiness.chat_generation_enabled:
        raise HTTPException(
            status_code=503,
            detail="图片识别需要启用支持视觉输入的聊天模型，请先完成模型配置。",
        )

    name_result = await session.scalars(
        select(Artifact.name)
        .outerjoin(ArtifactCatalogRecord, ArtifactCatalogRecord.artifact_id == Artifact.id)
        .outerjoin(Document, Document.artifact_id == Artifact.id)
        .outerjoin(MediaAsset, MediaAsset.artifact_id == Artifact.id)
        .outerjoin(ArtifactMediaLink, ArtifactMediaLink.artifact_id == Artifact.id)
        .where(
            or_(
                ArtifactCatalogRecord.record_kind == "artifact",
                Document.id.is_not(None),
                MediaAsset.id.is_not(None),
                ArtifactMediaLink.id.is_not(None),
            )
        )
        .distinct()
        .order_by(Artifact.name)
    )
    names = name_result.all()
    if not names:
        raise HTTPException(status_code=503, detail="馆藏目录为空，暂时无法进行图片比对。")

    by_name = {name.casefold(): name for name in names}
    visual_matches = [
        item
        for item in search_similar_images(content, settings.visual_reference_root, limit=5)
        if item["artifact"].casefold() in by_name
    ]
    if not visual_matches:
        return VisualSearchResponse(
            answer="知识库中暂时没有足够相似的参考图，系统没有强行猜测文物名称。请补充该文物的参考图片，或换一张更清晰的正面照片。",
            notice="本次未通过本地参考图相似度核验。",
            visual_matches=[],
        )

    top_visual = visual_matches[0]
    if top_visual["score"] >= 0.96:
        identification = VisualIdentification(
            artifact_name=top_visual["artifact"],
            confidence=top_visual["score"],
            visual_note=f"与知识库参考图“{top_visual['source']}”高度相似。",
        )
    else:
        candidate_text = "、".join(item["artifact"] for item in visual_matches)
        score_text = "；".join(f"{item['artifact']}={item['score']:.2f}" for item in visual_matches)
        prompt = (
            "你是博物馆图片复核助手。只能在 LOCAL_CANDIDATES 中选择一个名称，"
            "如果图片与候选都不匹配，artifact_name 必须返回 null。不得创造候选之外的名称。"
            "confidence 是 0 到 1 的小数，visual_note 只描述可见外观。\n\n"
            f"LOCAL_CANDIDATES：{candidate_text}\n"
            f"LOCAL_SIMILARITY_SCORES：{score_text}"
        )
        encoded = base64.b64encode(content).decode("ascii")
        try:
            structured = create_chat_client(settings).with_structured_output(VisualIdentification)
            result = await structured.ainvoke(
                [
                    HumanMessage(
                        content=[
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                            },
                        ]
                    )
                ]
            )
            identification = (
                result
                if isinstance(result, VisualIdentification)
                else VisualIdentification.model_validate(result)
            )
        except Exception as error:  # noqa: BLE001 -- provider errors become a visitor-facing message.
            raise HTTPException(
                status_code=502,
                detail=f"图片复核服务暂时不可用：{type(error).__name__}。",
            ) from error

    matched_name = by_name.get((identification.artifact_name or "").strip().casefold())
    candidate_names = {item["artifact"].casefold() for item in visual_matches}
    required_confidence = (
        MIN_MATCH_CONFIDENCE if top_visual["score"] >= 0.96 else MIN_MODEL_MATCH_CONFIDENCE
    )
    if (
        identification.confidence < required_confidence
        or not matched_name
        or matched_name.casefold() not in candidate_names
    ):
        return VisualSearchResponse(
            confidence=identification.confidence,
            visual_note=identification.visual_note,
            answer="参考图检索到了候选文物，但视觉复核没有达到可靠匹配标准。系统没有直接把候选当成最终答案。",
            notice="本次识别结果仅作为候选，未通过视觉复核。",
            visual_matches=visual_matches,
        )
    if not matched_name:
        return VisualSearchResponse(
            confidence=identification.confidence,
            visual_note=identification.visual_note,
            answer="暂时无法把这张图片可靠匹配到当前知识库中的文物记录。可以换一张正面、清晰且光线均匀的文物照片再试。",
            notice="本次没有得到可核验的馆藏匹配，系统没有擅自猜测文物名称。",
        )

    artifact_row = await session.scalar(select(Artifact).where(Artifact.name == matched_name))
    if artifact_row is None:
        raise HTTPException(status_code=404, detail="识别结果不在当前知识库文物记录中。")
    artifact = {
        "id": artifact_row.id,
        "name": artifact_row.name,
        "era": artifact_row.era,
        "location": None,
        "material": None,
    }
    catalog_record = await session.scalar(
        select(ArtifactCatalogRecord)
        .where(ArtifactCatalogRecord.artifact_id == artifact_row.id)
        .where(ArtifactCatalogRecord.record_kind == "artifact")
        .order_by(ArtifactCatalogRecord.row_number)
    )
    if catalog_record is not None:
        artifact["era"] = catalog_record.era or artifact["era"]
        artifact["location"] = catalog_record.location
        artifact["material"] = catalog_record.material

    retrieval = await RagPipeline(session).search(f"请介绍{matched_name}", include_media=True)
    answer = _fallback_answer(artifact)
    notice = "识别结果已限制在馆藏目录和知识库文物记录内；介绍内容优先使用馆内可追溯资料。"
    generated, generation_reason = await generate_grounded_answer(
        f"请介绍图片识别出的文物“{matched_name}”",
        retrieval,
        config=settings,
    )
    if generated is not None:
        answer = generated["answer"]
        notice = "图片匹配成功，介绍内容依据本轮馆内证据生成。"
    elif generation_reason:
        notice = f"图片匹配成功；模型导览暂不可用，已返回目录核验信息（{generation_reason}）。"

    return VisualSearchResponse(
        recognized_artifact=RecognizedArtifact(**artifact),
        confidence=identification.confidence,
        visual_note=identification.visual_note,
        answer=answer,
        notice=notice,
        citations=retrieval.get("citations", []),
        media=retrieval.get("media", []),
        visual_matches=visual_matches,
    )
