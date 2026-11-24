"""Composition root: Settings → frozen Container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.application.llm.chat_model import ChatModel
from backend.application.llm.embedder import Embedder
from backend.application.parsing.archive_extractor import ArchiveExtractor
from backend.application.parsing.document_chunker import DocumentChunker
from backend.application.parsing.document_parser import DocumentParser
from backend.application.storage.document_storage import DocumentStorage
from backend.application.wiring import SessionBound as SessionBound
from backend.application.wiring import wire_session_bound
from backend.config import Settings
from backend.domain.providers import LlmProvider
from backend.infrastructure.local_fs import LocalDocumentStorage
from backend.infrastructure.ollama_chat import OllamaChatModel
from backend.infrastructure.ollama_embed import OllamaEmbedder
from backend.infrastructure.openai_chat import OpenAIChatModel
from backend.infrastructure.openai_embed import OpenAIEmbedder
from backend.infrastructure.parsing.archive import build_archive_extractor
from backend.infrastructure.parsing.chunking import build_document_chunker
from backend.infrastructure.parsing.parsers.default import build_document_parser
from backend.infrastructure.postgres.engine import create_engine, create_session_factory
from backend.infrastructure.postgres.job_queue import PostgresJobQueue
from backend.infrastructure.postgres.repositories.document import PostgresDocumentRepository
from backend.infrastructure.postgres.repositories.engagement import PostgresEngagementRepository
from backend.infrastructure.postgres.repositories.session import PostgresSessionRepository
from backend.infrastructure.postgres.repositories.upload import PostgresUploadRepository
from backend.infrastructure.postgres.vector_index import PostgresVectorIndex


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    chat_model: ChatModel
    embedder: Embedder
    document_storage: DocumentStorage
    document_parser: DocumentParser
    document_chunker: DocumentChunker
    archive_extractor: ArchiveExtractor

    def bind(self, session: AsyncSession) -> SessionBound:
        engagements = PostgresEngagementRepository(session)
        documents = PostgresDocumentRepository(session)
        sessions = PostgresSessionRepository(session)
        uploads = PostgresUploadRepository(session)
        vector_index = PostgresVectorIndex(session)
        jobs = PostgresJobQueue(session)
        return wire_session_bound(
            engagements=engagements,
            documents=documents,
            sessions=sessions,
            uploads=uploads,
            chat=self.chat_model,
            embedder=self.embedder,
            storage=self.document_storage,
            archives=self.archive_extractor,
            settings=self.settings,
            jobs=jobs,
            vector_index=vector_index,
            document_parser=self.document_parser,
        )


def _build_chat(settings: Settings) -> ChatModel:
    match settings.llm_provider:
        case LlmProvider.OPENAI:
            key = settings.openai_api_key
            assert key is not None
            return OpenAIChatModel(
                api_key=key.get_secret_value(),
                model=settings.llm_model,
                timeout_seconds=settings.model_timeout_seconds,
                max_concurrent_calls=settings.max_concurrent_model_calls,
            )
        case LlmProvider.OLLAMA:
            return OllamaChatModel(
                base_url=settings.ollama_base_url,
                model=settings.llm_model,
                timeout_seconds=settings.model_timeout_seconds,
                max_concurrent_calls=settings.max_concurrent_model_calls,
                num_ctx=settings.ollama_num_ctx,
            )
        case _:
            assert_never(settings.llm_provider)


def _build_embedder(settings: Settings) -> Embedder:
    match settings.embedding_provider:
        case LlmProvider.OPENAI:
            key = settings.openai_api_key
            assert key is not None
            return OpenAIEmbedder(
                api_key=key.get_secret_value(),
                model=settings.embedding_model,
                timeout_seconds=settings.model_timeout_seconds,
                max_concurrent_calls=settings.max_concurrent_model_calls,
            )
        case LlmProvider.OLLAMA:
            return OllamaEmbedder(
                base_url=settings.ollama_base_url,
                model=settings.embedding_model,
                timeout_seconds=settings.model_timeout_seconds,
                max_concurrent_calls=settings.max_concurrent_model_calls,
            )
        case _:
            assert_never(settings.embedding_provider)


def build_container(settings: Settings) -> Container:
    engine = create_engine(settings)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        chat_model=_build_chat(settings),
        embedder=_build_embedder(settings),
        document_storage=LocalDocumentStorage(settings.document_storage_path),
        document_parser=build_document_parser(),
        document_chunker=build_document_chunker(),
        archive_extractor=build_archive_extractor(),
    )
