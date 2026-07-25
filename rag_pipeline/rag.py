from abc import ABC, abstractmethod
from .models import RAGResponse, ScoredChunk
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from .retrievers import BaseRetriever



class BaseRAG(ABC):

    @abstractmethod
    def invoke(
        self,
        query: str,
    ) -> RAGResponse:
        ...



class RAG(BaseRAG):

    def __init__(
        self,
        retriever: BaseRetriever,
        llm: BaseChatModel,
        prompt: ChatPromptTemplate,
    ):
        self.retriever = retriever
        self.chain = prompt | llm

    def _build_context(
        self,
        chunks: list[ScoredChunk],
    ) -> str:

        return "\n\n".join(
            chunk.text
            for chunk in chunks
        )

    def invoke(
        self,
        query: str,
    ) -> RAGResponse:

        chunks = self.retriever.retrieve(
            query=query,
        )


        context = self._build_context(chunks)

        response = self.chain.invoke(
            {
                "query": query,
                "context": context,
            }
        )

        return RAGResponse(
            answer=response.content,
            chunks=chunks,
        )

