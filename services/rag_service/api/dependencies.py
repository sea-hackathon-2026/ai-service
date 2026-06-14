"""Dependency composition for the RAG service."""

from functools import lru_cache

from services.rag_service.application.use_cases import (
    GenerateGroundedScripts,
    SearchKnowledge,
)
from services.rag_service.config import get_settings
from services.rag_service.infrastructure.json_knowledge_repository import (
    JsonKnowledgeRepository,
)
from services.rag_service.infrastructure.openai_script_generator import (
    OpenAIScriptGenerator,
)


@lru_cache
def get_repository() -> JsonKnowledgeRepository:
    settings = get_settings()
    return JsonKnowledgeRepository(settings.knowledge_base_path)


@lru_cache
def get_search_use_case() -> SearchKnowledge:
    return SearchKnowledge(get_repository())


@lru_cache
def get_generate_use_case() -> GenerateGroundedScripts:
    settings = get_settings()
    generator = OpenAIScriptGenerator(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )
    return GenerateGroundedScripts(get_repository(), generator)
