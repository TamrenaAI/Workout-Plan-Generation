"""
RAG knowledge base — real hybrid search + reranking pipeline. See
tools/rag/pipeline.py for the implementation; this module only re-exports
the tool contract other code depends on.
"""

from tools.rag.pipeline import search_rag

__all__ = ["search_rag"]
