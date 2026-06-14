"""RAG service REST endpoints."""

from fastapi import APIRouter, Depends

from services.rag_service.api.dependencies import (
    get_generate_use_case,
    get_search_use_case,
)
from services.rag_service.api.schemas import (
    DocumentResponse,
    GenerateScriptsRequest,
    PipelineResponse,
    ScriptResponse,
    SearchRequest,
)
from services.rag_service.application.use_cases import (
    GenerateGroundedScripts,
    SearchKnowledge,
)
from services.rag_service.config import get_settings
from services.rag_service.domain.models import AudienceComment

router = APIRouter()


@router.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "healthy", "service": settings.service_name}


@router.post(
    "/v1/retrieval/search",
    response_model=list[DocumentResponse],
    tags=["retrieval"],
)
def search_knowledge(
    request: SearchRequest,
    use_case: SearchKnowledge = Depends(get_search_use_case),
) -> list[DocumentResponse]:
    return [
        DocumentResponse(tag=document.tag, text=document.text, score=document.score)
        for document in use_case.execute(request.query, request.top_k)
    ]


@router.post(
    "/v1/scripts/generate",
    response_model=PipelineResponse,
    tags=["generation"],
)
def generate_scripts(
    request: GenerateScriptsRequest,
    use_case: GenerateGroundedScripts = Depends(get_generate_use_case),
) -> PipelineResponse:
    result = use_case.execute(
        comments=[
            AudienceComment(text=comment.text, timestamp=comment.timestamp)
            for comment in request.comments
        ],
        top_k=request.top_k,
        max_batch_size=request.max_batch_size,
    )
    scripts = [
        ScriptResponse(
            text=script.text,
            intent=script.intent.value,
            emotion=script.emotion,
            call_to_action=script.call_to_action,
            confidence=script.confidence,
            source_comments=list(script.source_comments),
            retrieved_tags=list(script.retrieved_tags),
            latency_ms=script.latency_ms,
        )
        for script in result.scripts
    ]
    return PipelineResponse(
        received_count=result.received_count,
        filtered_count=result.filtered_count,
        generated_count=len(scripts),
        scripts=scripts,
    )
