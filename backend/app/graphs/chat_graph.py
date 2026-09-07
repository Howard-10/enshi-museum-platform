"""LangGraph orchestration for intent, evidence, and answer composition."""

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

MEDIA_WORDS = ("\u56fe\u7247", "\u89c6\u9891", "\u97f3\u9891")
OUT_OF_SCOPE_REQUEST_WORDS = (
    "\u5e02\u573a\u4ef7\u683c",
    "\u4ef7\u683c",
    "\u4f30\u4ef7",
    "\u8d5d\u54c1",
    "\u771f\u4f2a",
    "\u95ed\u9986",
    "\u5f00\u9986",
    "\u5f00\u653e\u65f6\u95f4",
    "\u9884\u7ea6",
    "\u8d2d\u7968",
    "\u5916\u661f",
)


def _normalized_query(value: str) -> str:
    """Remove conversational punctuation before comparing catalog names."""

    return "".join(
        character
        for character in value
        if character.isalnum() or "\u4e00" <= character <= "\u9fff"
    )


def _primary_artifact(
    query: str, artifacts: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Select an artifact only when the retrieval result identifies it clearly."""

    if not artifacts:
        return None
    compact_query = _normalized_query(query)
    named_matches = [
        artifact
        for artifact in artifacts
        if artifact.get("name")
        and _normalized_query(str(artifact["name"])) in compact_query
    ]
    if named_matches:
        return max(named_matches, key=lambda artifact: len(str(artifact["name"])))
    return artifacts[0] if len(artifacts) == 1 else None


def _local_answer(
    query: str,
    artifacts: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    """Compose a useful answer from approved evidence without an LLM."""

    artifact = _primary_artifact(query, artifacts)
    if artifact:
        name = str(artifact.get("name") or "\u8fd9\u4ef6\u6587\u7269")
        facts = [
            f"\u5e74\u4ee3：{artifact['era']}" if artifact.get("era") else None,
            f"\u5730\u70b9：{artifact['location']}" if artifact.get("location") else None,
            f"\u6750\u8d28：{artifact['material']}" if artifact.get("material") else None,
        ]
        fact_text = "；".join(fact for fact in facts if fact)
        if fact_text:
            answer = f"\u9986\u5185\u76ee\u5f55\u663e\u793a\uff0c\u201c{name}\u201d\u5df2\u786e\u8ba4\u7684\u4fe1\u606f\u662f：{fact_text}\u3002"
            if any(word in query for word in ("\u4ecb\u7ecd", "\u662f\u4ec0\u4e48", "\u8bb2\u8bb2", "\u8bf4\u8bf4")):
                answer += "\u76ee\u524d\u9986\u5185\u76ee\u5f55\u6682\u672a\u8bb0\u5f55\u8fd9\u4ef6\u6587\u7269\u7684\u5f62\u5236\u3001\u7eb9\u9970\u3001\u7528\u9014\u7b49\u66f4\u8be6\u7ec6\u4fe1\u606f\u3002"
        elif citations and citations[0].get("excerpt"):
            answer = f"\u9986\u5185\u8d44\u6599\u663e\u793a\uff0c\u201c{name}\u201d\u76f8\u5173\u8bb0\u5f55\u4e3a：{citations[0]['excerpt']}"
        else:
            answer = f"\u9986\u5185\u76ee\u5f55\u5df2\u6536\u5f55\u201c{name}\u201d\uff0c\u5f53\u524d\u53ef\u786e\u8ba4\u5176\u4e3a\u9986\u85cf\u6587\u7269\u3002"
        if citations:
            answer += f"\u672c\u6b21\u540c\u65f6\u627e\u5230 {len(citations)} \u9879\u76f8\u5173\u8d44\u6599\uff0c\u4e0b\u9762\u53ef\u4ee5\u5c55\u5f00\u67e5\u770b\u51fa\u5904\u3002"
        return answer

    if citations:
        citation = citations[0]
        title = citation.get("title") or "\u76f8\u5173\u9986\u5185\u8d44\u6599"
        excerpt = citation.get("excerpt")
        if excerpt:
            return f"\u6211\u5728\u9986\u5185\u8d44\u6599\u201c{title}\u201d\u4e2d\u67e5\u5230\u4e0e\u4f60\u95ee\u9898\u76f8\u5173\u7684\u5185\u5bb9：{excerpt}"
        return f"\u6211\u5728\u9986\u5185\u8d44\u6599\u4e2d\u67e5\u5230\u201c{title}\u201d\u4e0e\u4f60\u7684\u95ee\u9898\u76f8\u5173\uff0c\u4e0b\u9762\u5217\u51fa\u4e86\u672c\u6b21\u56de\u7b54\u4f9d\u636e\u3002"

    return "\u6211\u6682\u65f6\u53ea\u68c0\u7d22\u5230\u76f8\u5173\u7ebf\u7d22\uff0c\u8fd8\u4e0d\u80fd\u4ece\u5df2\u5ba1\u6838\u9986\u5185\u8d44\u6599\u4e2d\u786e\u8ba4\u5177\u4f53\u7b54\u6848\u3002"


class ChatState(TypedDict):
    """Shared state passed between the chat workflow nodes."""

    session_id: str
    user_query: str
    intent: str
    answer: str
    citations: list[dict[str, str | None]]
    media: list[dict[str, str]]
    retrieval: dict[str, Any]
    answer_scope: str
    notice: str | None
    evidence_status: str
    reason_codes: list[str]


def classify_intent(state: ChatState) -> dict[str, str]:
    """A deterministic pre-classifier until model-based intent routing is enabled."""

    intent = "media" if any(word in state["user_query"] for word in MEDIA_WORDS) else "knowledge"
    return {"intent": intent}


def answer_query(state: ChatState) -> dict[str, object]:
    """Build a transparent evidence-first reply until LLM generation is configured."""

    retrieval = state["retrieval"]
    artifacts = retrieval["artifacts"]
    citations = retrieval["citations"]
    media = retrieval["media"]
    evidence_status = state["evidence_status"]
    if evidence_status == "conflicting":
        return {
            "answer": "馆内资料存在同级证据冲突，目前不能给出确定性结论。",
            "answer_scope": "insufficient_evidence",
            "notice": "系统已保留冲突原因，未调用聊天模型。",
            "citations": citations,
            "media": [],
        }
    if evidence_status != "sufficient":
        return {
            "answer": "暂未检索到足以支撑回答的已审核馆内证据。可换一个更具体的文物名称、时代或地点再试。",
            "answer_scope": "insufficient_evidence",
            "notice": "本地资料不足或尚待审核；外部搜索保持关闭，系统不会用模型猜测代替证据。",
            "citations": citations,
            "media": media,
        }
    if any(word in state["user_query"] for word in OUT_OF_SCOPE_REQUEST_WORDS):
        return {
            "answer": "\u76ee\u524d\u672c\u5730\u9986\u85cf\u8d44\u6599\u65e0\u6cd5\u6838\u9a8c\u8fd9\u4e2a\u95ee\u9898\u3002\u7cfb\u7edf\u4e0d\u4f1a\u62ff\u6587\u7269\u8d44\u6599\u63a8\u6d4b\u5e02\u573a\u4ef7\u683c\u3001\u771f\u4f2a\u3001\u5b9e\u65f6\u5f00\u9986\u4fe1\u606f\u6216\u9884\u7ea6\u4e8b\u9879\u3002",
            "answer_scope": "insufficient_evidence",
            "notice": "\u8be5\u95ee\u9898\u8d85\u51fa\u5f53\u524d\u9986\u85cf\u8d44\u6599\u7684\u53ef\u6838\u9a8c\u8303\u56f4\uff1b\u5916\u90e8\u641c\u7d22\u4ecd\u4fdd\u6301\u5173\u95ed\u3002",
            "citations": [],
            "media": [],
        }
    if state["intent"] == "media" and media:
        artifact = _primary_artifact(state["user_query"], artifacts)
        artifact_name = artifact["name"] if artifact else "\u76f8\u5173\u6587\u7269"
        labels = {"video": "\u89c6\u9891", "audio": "\u97f3\u9891", "image": "\u56fe\u7247"}
        media_types = sorted({labels.get(item.get("type"), "\u5a92\u4f53") for item in media})
        type_text = "、".join(media_types)
        answer = f"\u6211\u627e\u5230\u201c{artifact_name}\u201d\u7684 {len(media)} \u4e2a{type_text}\u8d44\u6599，\u4e0b\u9762\u53ef\u4ee5\u76f4\u63a5\u64ad\u653e\u6216\u67e5\u770b\u3002"
    elif artifacts or citations:
        answer = _local_answer(state["user_query"], artifacts, citations)
        return {
            "answer": answer,
            "answer_scope": "internal_only",
            "notice": "\u672c\u6b21\u56de\u7b54\u4ec5\u4f9d\u636e\u672c\u5730\u9986\u85cf\u8d44\u6599\uff0c\u672a\u8c03\u7528\u5927\u6a21\u578b\u6216\u5916\u90e8\u641c\u7d22\u3002",
            "citations": citations,
            "media": media,
        }
    else:
        answer = "\u6682\u672a\u68c0\u7d22\u5230\u8db3\u4ee5\u652f\u6491\u56de\u7b54\u7684\u672c\u5730\u9986\u85cf\u8d44\u6599\u3002\u53ef\u6362\u4e00\u4e2a\u66f4\u5177\u4f53\u7684\u6587\u7269\u540d\u79f0\u3001\u65f6\u4ee3\u6216\u5730\u70b9\u518d\u8bd5\u3002"
        return {
            "answer": answer,
            "answer_scope": "insufficient_evidence",
            "notice": "\u672c\u5730\u8d44\u6599\u4e0d\u8db3\uff0c\u4e14\u5916\u90e8\u641c\u7d22\u4ecd\u4fdd\u6301\u5173\u95ed\uff1b\u7cfb\u7edf\u4e0d\u4f1a\u7528\u6a21\u578b\u731c\u6d4b\u4ee3\u66ff\u8bc1\u636e\u3002",
            "citations": [],
            "media": media,
        }
    return {
        "answer": answer,
        "answer_scope": "internal_only",
        "notice": "\u672c\u6b21\u56de\u7b54\u4ec5\u4f9d\u636e\u672c\u5730\u9986\u85cf\u8d44\u6599\u3002",
        "citations": citations,
        "media": media,
    }


def build_chat_graph():
    builder = StateGraph(ChatState)
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("answer_query", answer_query)
    builder.add_edge(START, "classify_intent")
    builder.add_edge("classify_intent", "answer_query")
    builder.add_edge("answer_query", END)
    return builder.compile()


chat_graph = build_chat_graph()
