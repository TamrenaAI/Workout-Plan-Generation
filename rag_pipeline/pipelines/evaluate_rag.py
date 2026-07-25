import argparse
import json

from datasets import Dataset

from ragas import evaluate
from ragas.metrics import (
    Faithfulness,
    AnswerRelevancy,
)

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
from rag_pipeline.paths import get_evaluation_dataset_path, RERANKER_DIR, DENSE_DIR
from rag_pipeline.prompts import RAG_PROMPT
from rag_pipeline.qdrant import create_qdrant_client
from rag_pipeline.ragas import SentenceTransformerRagasEmbeddings
from rag_pipeline.llms import (
    LLMConfig,
    LLMProvider,
    create_llm,
)
from rag_pipeline.rerankers import CrossEncoderReranker



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the RAG pipeline using Ragas.",
    )

    parser.add_argument(
        "--collection",
        required=True,
    )

    parser.add_argument(
        "--sample",
        type=int,
        default=5,
        help="Number of questions per type.",
    )

    return parser.parse_args()

def sample_dataset(
    dataset: list[dict],
    sample_per_type: int,
) -> list[dict]:

    sampled = []

    for question_type in (
        "single_chunk",
        "multi_chunk",
        "negative",
    ):
        subset = [
            item
            for item in dataset
            if item["type"] == question_type
        ]

        sampled.extend(
            subset[:sample_per_type]
        )

    return sampled

def build_ragas_dataset(
    rag,
    evaluation_dataset: list[dict],
) -> Dataset:

    ragas_samples = []

    for sample in evaluation_dataset:

        response = rag.invoke(
            sample["question"],
        )

        ragas_samples.append(
            {
                "user_input": sample["question"],
                "response": response.answer,
                "retrieved_contexts": [
                    chunk.text
                    for chunk in response.chunks
                ],
            }
        )

    return Dataset.from_list(
        ragas_samples,
    )

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

    ragas_embeddings = SentenceTransformerRagasEmbeddings(
        dense_model,
        str(DENSE_DIR),
    )

    llm = create_llm(LLM_CONFIG)

    print("Models loaded.")

    print("Connecting to Qdrant...")

    client = create_qdrant_client()

    print("Connected.")

    print("Creating retriever...")

    hybrid = create_hybrid_retriever(
        client=client,
        dense_model=dense_model,
        sparse_model=sparse_model,
        collection_name=args.collection,
        top_k=10,
    )

    filtered = create_filtered_retriever(
        retriever=hybrid,
        llm=llm,
        collection_name=args.collection,
    )

    retriever = create_reranking_retriever(
        retriever=filtered,
        reranker=reranker,
        top_k=3,
    )
    rag = create_rag(
        retriever=retriever,
        llm=llm,
        prompt=RAG_PROMPT,
    )

    print("Retriever created.")

    dataset_path = get_evaluation_dataset_path(
        args.collection,
    )

    with dataset_path.open(
        "r",
        encoding="utf-8",
    ) as f:
        evaluation_dataset = json.load(f)

    evaluation_dataset = sample_dataset(
        evaluation_dataset,
        args.sample,
    )

    ragas_dataset = build_ragas_dataset(
        rag,
        evaluation_dataset,
    )

    metrics = [
        Faithfulness(),
        AnswerRelevancy(
            strictness=1,
        ),
    ]

    result = evaluate(
        dataset=ragas_dataset,
        metrics=metrics,
        llm=llm,
        embeddings=ragas_embeddings,
        batch_size=1,
        raise_exceptions=True,
    )

    print(result)

    # with open(
    #     f"rag_data/evaluation/results/{args.collection}_ragas_results.json",
    #     "w",
    #     encoding="utf-8",
    # ) as f:
    #     json.dump(
    #         result.to_pandas().to_dict(orient="records"),
    #         f,
    #         indent=4,
    #         ensure_ascii=False,
    #     )

    df = result.to_pandas()

    df.to_csv(
        f"rag_data/evaluation/results/{args.collection}_ragas_results.csv",
        index=False,
    )


if __name__ == "__main__":
    main()


    



   