import argparse

from rag_pipeline.embeddings import (
    load_dense_model,
    load_sparse_model,
)

from rag_pipeline.factory import (
    create_hybrid_retriever,
    create_filtered_retriever,
    create_reranking_retriever,
    create_rag,
)

from rag_pipeline.llms import create_llm
from rag_pipeline.qdrant import create_qdrant_client
from rag_pipeline.prompts import RAG_PROMPT
from rag_pipeline.rerankers import CrossEncoderReranker
from rag_pipeline.paths import RERANKER_DIR
from rag_pipeline.llms import (
    LLMConfig,
    LLMProvider,
    create_llm,
)



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RAG inference.",
    )

    parser.add_argument(
        "--collection",
        required=True,
        help="Qdrant collection.",
    )

    parser.add_argument(
        "--query",
        required=True,
        help="User query.",
    )

    return parser.parse_args()


# LLM_CONFIG = LLMConfig(
#     provider=LLMProvider.NVIDIA,
#     model="nvidia/nemotron-3-super-120b-a12b",
# )

LLM_CONFIG = LLMConfig(
    provider=LLMProvider.GROQ,
    model="openai/gpt-oss-120b",
)

# LLM_CONFIG = LLMConfig(
#    provider=LLMProvider.GEMINI,
#    model="models/gemini-2.5-flash"
# )

# LLM_CONFIG = LLMConfig(
#     provider=LLMProvider.OPENROUTER,
#     model="nvidia/nemotron-3-ultra-550b-a55b:free",
#     temperature=0
# )

# LLM_CONFIG = LLMConfig(
#     provider=LLMProvider.ITI,
#     model="anthropic.claude-sonnet-4-6",
#     temperature=0
# )



def main():

    args = parse_args()

    print("Loading models...")

    dense_model = load_dense_model()
    sparse_model = load_sparse_model()
    reranker = CrossEncoderReranker(
        model_name=RERANKER_DIR,
        device="cpu"
    )

    print("Models loaded.")

    print("Connecting to Qdrant...")

    qdrant = create_qdrant_client()

    print("Connected.")

    print("Creating LLM...")

    llm = create_llm(LLM_CONFIG)

    print("Creating retriever...")

    hybrid_retriever = create_hybrid_retriever(
        client=qdrant,
        collection_name=args.collection,
        dense_model=dense_model,
        sparse_model=sparse_model,
        top_k=10,
    )

    filtered_retriever = create_filtered_retriever(
        retriever=hybrid_retriever,
        collection_name=args.collection,
        llm=llm,
    )


    final_retriever = create_reranking_retriever(
        retriever=filtered_retriever,
        reranker=reranker,
        top_k=3,
    )

    print("Creating RAG...")

    rag = create_rag(
        retriever=final_retriever,
        llm=llm,
        prompt=RAG_PROMPT,
    )

    print("Running query...\n")

    response = rag.invoke(
        args.query
    )


    print("=" * 50)
    print("ANSWER")
    print("=" * 50)

    print(response.answer)


if __name__ == "__main__":
    main()

