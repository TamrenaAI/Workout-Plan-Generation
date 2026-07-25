import argparse

from rag_pipeline.embeddings import (
    load_dense_model,
    load_sparse_model,
)

from rag_pipeline.evaluators import RetrieverExperimentRunner
from rag_pipeline.factory import (
    create_filtered_retriever,
    create_hybrid_retriever,
    create_reranking_retriever,
)
from rag_pipeline.llms import (
    LLMConfig,
    LLMProvider,
    create_llm,
)
from rag_pipeline.paths import get_evaluation_dataset_path, RERANKER_DIR
from rag_pipeline.qdrant import create_qdrant_client
from rag_pipeline.rerankers import CrossEncoderReranker
import json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval pipelines on an evaluation dataset.",
    )

    parser.add_argument(
        "--collection",
        required=True,
        help="Qdrant collection to evaluate.",
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

def main() -> None:
    args = parse_args()

    # Load evaluation dataset
    dataset_path = get_evaluation_dataset_path(args.collection)
    with dataset_path.open("r", encoding="utf-8") as f:
        evaluation_dataset = json.load(f)

    print(f"Loaded {len(evaluation_dataset)} evaluation queries.")
    evaluation_dataset = [
        *[x for x in evaluation_dataset if x["type"] == "single_chunk"][:5],
        *[x for x in evaluation_dataset if x["type"] == "multi_chunk"][:5],
        *[x for x in evaluation_dataset if x["type"] == "negative"][:5],
    ]

    # Load models
    print("Loading models...")

    dense_model = load_dense_model()
    sparse_model = load_sparse_model()
    reranker = CrossEncoderReranker(
        model_name=RERANKER_DIR,
        device="cpu"
    )
    llm = create_llm(LLM_CONFIG)

    print("Models loaded.")

    # Create Qdrant client
    print("Connecting to Qdrant...")

    qdrant = create_qdrant_client()

    print("Connected.")

    # Create retrievers
    print("Creating retrievers...")
    hybrid_retriever = create_hybrid_retriever(
        client=qdrant,
        collection_name=args.collection,
        dense_model=dense_model,
        sparse_model=sparse_model,
        top_k=3,
    )

    hybrid_retriever_for_reranker = create_hybrid_retriever(
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

    filtered_retriever_for_reranker = create_filtered_retriever(
        retriever=hybrid_retriever_for_reranker,
        collection_name=args.collection,
        llm=llm,
    )

    hybrid_reranker = create_reranking_retriever(
        retriever=hybrid_retriever_for_reranker,
        reranker=reranker,
        top_k=3,
    )

    filtered_hybrid_reranker = create_reranking_retriever(
        retriever=filtered_retriever_for_reranker,
        reranker=reranker,
        top_k=3,
    )

    print("Retrievers created.")

    # Run experiments
    runner = RetrieverExperimentRunner(
        evaluation_dataset=evaluation_dataset,
    )

    experiments = [
        ("Hybrid", hybrid_retriever),
        ("Hybrid + Metadata", filtered_retriever),
        ("Hybrid + Reranker", hybrid_reranker),
        ("Hybrid + Metadata + Reranker", filtered_hybrid_reranker),
    ]

    for name, retriever in experiments:
        runner.run(
            name=name,
            retriever=retriever,
        )
        print(f"{name} finished")

    summary = runner.summary()
    summary_by_type = runner.summary_by_type()
    print("Summary:\n", summary)
    print("="*50)
    print("Summary by Type:\n", summary_by_type)
    summary.to_csv(f"rag_data/evaluation/results/{str(args.collection)}_summary.csv")
    summary_by_type.to_csv(f"rag_data/evaluation/results/{str(args.collection)}_summary_by_type.csv")


    


    

if __name__ == "__main__":
    main()
