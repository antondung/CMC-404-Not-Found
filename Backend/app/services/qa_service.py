from __future__ import annotations

from typing import Any
from app.schemas import CandidateKhoan, Citation
from app.services.citation_validator import CitationValidator
from app.intelligence.llm_router import LLMRouter
from app.intelligence.embedder import Embedder
from app.adapters.qdrant_vector import QdrantVectorClient


class QAService:
    """Module 7: Hybrid RAG QA Engine with strict citation validation and fail-closed mechanism without mock fallbacks."""

    def __init__(
        self,
        qdrant_client: QdrantVectorClient | None = None,
        neo4j_driver: Any | None = None,
        llm_router: LLMRouter | None = None,
        embedder: Embedder | None = None,
        redis_pool: Any | None = None,
    ) -> None:
        self.qdrant = qdrant_client
        self.driver = neo4j_driver
        self.router = llm_router
        self.embedder = embedder
        self.redis = redis_pool
        self.validator = CitationValidator(neo4j_driver)

    async def retrieve_candidates(self, question: str, audience: str = "citizen") -> list[CandidateKhoan]:
        """Retrieve candidate Khoan strictly from Qdrant vector store and Neo4j graph expansion."""
        candidates: list[CandidateKhoan] = []
        if self.qdrant and self.embedder:
            try:
                # Embed the question, then search the real Qdrant collection by vector
                vectors = await self.embedder.embed_texts([question])
                hits = await self.qdrant.search("khoan", vectors[0], limit=5)
                for hit in hits:
                    p = hit.get("payload", {})
                    if audience == "citizen" and p.get("visibility", "public") != "public":
                        continue
                    candidates.append(CandidateKhoan(
                        khoan_id=p.get("khoan_id", ""),
                        noi_dung=p.get("noi_dung", ""),
                        score=hit.get("score", 0.0),
                    ))
            except Exception:
                pass

        if not candidates and self.driver and hasattr(self.driver, "session"):
            try:
                # Graph keyword search fallback when Qdrant is unreachable
                query = """
                MATCH (k:Khoan)
                WHERE toLower(k.noi_dung) CONTAINS toLower($kw)
                RETURN k.khoan_id AS kid, k.noi_dung AS nd
                LIMIT 5
                """
                async with self.driver.session() as session:
                    res = await session.run(query, kw=question[:30])
                    async for record in res:
                        candidates.append(CandidateKhoan(
                            khoan_id=str(record["kid"] or ""),
                            noi_dung=str(record["nd"] or ""),
                            score=0.85,
                        ))
            except Exception:
                pass

        return [c for c in candidates if c.khoan_id and c.noi_dung]

    async def answer(
        self,
        question: str,
        audience: str = "citizen",
        graph_paths_enabled: bool = False,
    ) -> dict[str, Any]:
        """Execute strictly real RAG QA flow: Retrieve -> LLM -> Citation Verify -> Fail-Closed output."""
        # 1. Retrieve candidates
        candidates = await self.retrieve_candidates(question, audience=audience)
        if not candidates:
            return {
                "answer": "Không tìm thấy điều khoản pháp lý nào liên quan trong kho dữ liệu để trả lời câu hỏi của bạn.",
                "citations": [],
                "confidence": "low",
                "graph_paths": [],
                "audience": audience,
                "refuse_reason": ["No legal candidates retrieved from Qdrant/Neo4j index."],
            }

        # 2. Call LLM synthesized answer via BE2 router
        if not self.router:
            return {
                "answer": "Hệ thống AI xử lý ngôn ngữ (BE2 Intelligence API) hiện chưa sẵn sàng. Vui lòng thử lại sau.",
                "citations": [],
                "confidence": "low",
                "graph_paths": [],
                "audience": audience,
                "refuse_reason": ["BE2 LLMRouter service unavailable."],
            }

        retrieved_context = "\n".join(f"[{c.khoan_id}] {c.noi_dung}" for c in candidates)
        prompt = (
            "retrieved_context:\n"
            f"{retrieved_context}\n\n"
            f"Câu hỏi: {question}\n"
            "Chỉ trả lời dựa trên retrieved_context ở trên. Tuyệt đối không bịa. "
            "Trả về JSON gồm: answer (string), citations (mảng {khoan_id, quote} trích nguyên văn), "
            "confidence (high|medium|low)."
        )
        try:
            llm_out = await self.router.complete(
                task="qa",
                prompt=prompt,
                schema={"required": ["answer", "citations"]},
                complexity="high",
            )
        except Exception as e:
            return {
                "answer": f"Không thể tạo lời giải từ hệ thống AI: {str(e)}",
                "citations": [],
                "confidence": "low",
                "graph_paths": [],
                "audience": audience,
                "refuse_reason": [f"LLMRouter error: {str(e)}"],
            }

        # LLM router returns a needs_review envelope when output fails schema repair
        if llm_out.get("needs_review") or llm_out.get("status") == "needs_review":
            return {
                "answer": "Chưa thể tạo câu trả lời đạt chuẩn trích dẫn. Vui lòng thử lại hoặc thu hẹp câu hỏi.",
                "citations": [],
                "confidence": "low",
                "graph_paths": [],
                "audience": audience,
                "refuse_reason": ["LLM output failed schema validation (needs_review)."],
            }

        raw_answer = llm_out.get("answer", "")
        # graph_paths must be derived from Neo4j only (SYSTEM_BACKEND principle), never from LLM output.
        raw_graph_paths: list[Any] = []
        raw_citations = llm_out.get("citations", [])

        # 3. Validate citations against canonical text (Neo4j)
        is_valid, validated_citations, errors = await self.validator.validate_quotes(raw_citations, preloaded_sources=candidates)

        # 4. Fail-Closed Strategy
        if not is_valid or not validated_citations:
            return {
                "answer": "Không đủ căn cứ hoặc trích dẫn pháp lý không khớp nguyên văn để trả lời an toàn câu hỏi này.",
                "citations": [],
                "confidence": "low",
                "graph_paths": [],
                "audience": audience,
                "refuse_reason": errors or ["All citations failed exact-match verification."],
            }

        return {
            "answer": raw_answer,
            "citations": validated_citations,
            "confidence": llm_out.get("confidence", "high"),
            "graph_paths": raw_graph_paths if (graph_paths_enabled or audience == "admin") else [],
            "audience": audience,
        }
