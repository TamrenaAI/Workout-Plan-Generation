from math import log2


def hit_rate(
    ground_truth: set[int],
    retrieved: list[int],
) -> float:
    """
    Computes Hit Rate for a single query.

    Returns:
        1.0 if at least one relevant chunk is retrieved.
        0.0 otherwise.
    """
    return float(bool(ground_truth.intersection(retrieved)))

def negative_success_rate(
    retrieved: list[int],
) -> float:
    """
    Computes Negative Success Rate for a single negative query.

    Returns:
        1.0 if no chunks are retrieved.
        0.0 otherwise.
    """
    return float(len(list(retrieved)) == 0)


def precision_at_k(
    ground_truth: set[int],
    retrieved: list[int],
) -> float:
    """
    Computes Precision@k for a single query.

    Precision@k = (# relevant retrieved) / (# retrieved)
    """
    retrieved = list(retrieved)

    if not retrieved:
        return 0.0

    relevant_retrieved = len(
        ground_truth.intersection(retrieved)
    )

    return relevant_retrieved / len(retrieved)

def recall_at_k(
    ground_truth: set[int],
    retrieved: list[int],
) -> float:
    """
    Computes Recall@k for a single query.

    Recall@k = (# relevant retrieved) / (# relevant)
    """

    if not ground_truth:
        return 0.0

    relevant_retrieved = len(
        ground_truth.intersection(retrieved)
    )

    return relevant_retrieved / len(ground_truth)

def reciprocal_rank(
    ground_truth: set[int],
    retrieved: list[int],
) -> float:
    """
    Computes Reciprocal Rank (RR) for a single query.

    RR = 1 / rank of the first relevant retrieved chunk.
    Returns 0.0 if no relevant chunk is retrieved.
    """

    for rank, chunk_idx in enumerate(retrieved, start=1):
        if chunk_idx in ground_truth:
            return 1.0 / rank

    return 0.0



def ndcg(
    ground_truth: set[int],
    retrieved: list[int],
) -> float:
    """
    Computes Normalized Discounted Cumulative Gain (nDCG)
    for a single query.
    """

    if not ground_truth:
        return 0.0

    # DCG
    dcg = 0.0

    for rank, chunk_idx in enumerate(retrieved, start=1):
        if chunk_idx in ground_truth:
            dcg += 1 / log2(rank + 1)

    # IDCG (ideal ranking)
    ideal_hits = min(len(ground_truth), len(retrieved))

    idcg = sum(
        1 / log2(rank + 1)
        for rank in range(1, ideal_hits + 1)
    )

    if idcg == 0:
        return 0.0

    return dcg / idcg