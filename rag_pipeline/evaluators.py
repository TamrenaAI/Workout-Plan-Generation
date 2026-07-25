import pandas as pd
from .retrievers import BaseRetriever
from .metrics import (
    negative_success_rate,
    hit_rate,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    ndcg
)

class RetrieverEvaluator:

    POSITIVE_METRICS = {
        "Precision@k": "precision",
        "Recall@k": "recall",
        "MRR": "reciprocal_rank",
        "nDCG": "ndcg",
        "Hit Rate": "hit_rate",
    }

    NEGATIVE_METRICS = {
        "Negative Success Rate": "negative_success",
    }


    def __init__(
        self,
        retriever: BaseRetriever,
        evaluation_dataset: list[dict],
    ):
        self.retriever = retriever
        self.dataset = evaluation_dataset

        self.results = pd.DataFrame()


    @property
    def positive_results(self) -> pd.DataFrame:
        return self.results[
            self.results["type"] != "negative"
        ]


    @property
    def negative_results(self) -> pd.DataFrame:
        return self.results[
            self.results["type"] == "negative"
        ]

    def _check_results(self) -> None:
        if self.results.empty:
            raise ValueError(
                "Run evaluate() before requesting reports."
            )
        

    def _evaluate_sample(
        self,
        sample: dict,
    ) -> dict:

        question = sample["question"]
        ground_truth = set(sample["relevant_chunks"])
        query_type = sample["type"]

        retrieved_chunks = self.retriever.retrieve(question)

        retrieved_ids = [
            chunk.chunk_index
            for chunk in retrieved_chunks
        ]

        row = {
            "question": question,
            "type": query_type,

            "ground_truth": sorted(ground_truth),

            "retrieved": retrieved_ids,
            "retrieved_chunks": retrieved_chunks,

            "num_ground_truth": len(ground_truth),
            "num_retrieved": len(retrieved_ids),
        }

        if query_type == "negative":

            row["negative_success"] = negative_success_rate(
                retrieved=retrieved_ids,
            )

        else:

            row["hit_rate"] = hit_rate(
                ground_truth=ground_truth,
                retrieved=retrieved_ids,
            )

            row["precision"] = precision_at_k(
                ground_truth=ground_truth,
                retrieved=retrieved_ids,
            )

            row["recall"] = recall_at_k(
                ground_truth=ground_truth,
                retrieved=retrieved_ids,
            )

            row["reciprocal_rank"] = reciprocal_rank(
                ground_truth=ground_truth,
                retrieved=retrieved_ids,
            )

            row["ndcg"] = ndcg(
                ground_truth=ground_truth,
                retrieved=retrieved_ids,
            )

        return row
    

    def evaluate(
        self,
    ) -> pd.DataFrame:

        rows = []

        for sample in self.dataset:
            rows.append(
                self._evaluate_sample(sample)
            )

        self.results = pd.DataFrame(rows)

        return self.results
    

    def summary(
        self,
    ) -> pd.DataFrame:

        self._check_results()

        rows = []

        for display_name, column in self.POSITIVE_METRICS.items():

            rows.append(
                {
                    "Metric": display_name,
                    "Value": self.positive_results[column].mean(),
                }
            )

        for display_name, column in self.NEGATIVE_METRICS.items():

            rows.append(
                {
                    "Metric": display_name,
                    "Value": self.negative_results[column].mean(),
                }
            )

        return pd.DataFrame(rows)
    
    def summary_by_type(
        self,
    ) -> pd.DataFrame:

        self._check_results()

        rows = []

        for query_type, group in self.results.groupby("type"):

            row = {
                "Type": query_type,
                "Count": len(group),
            }

            if query_type == "negative":

                for display_name, column in self.NEGATIVE_METRICS.items():
                    row[display_name] = group[column].mean()

            else:

                for display_name, column in self.POSITIVE_METRICS.items():
                    row[display_name] = group[column].mean()

            rows.append(row)

        return pd.DataFrame(rows)


class RetrieverExperimentRunner:

    def __init__(
        self,
        evaluation_dataset: list[dict],
    ):
        self.dataset = evaluation_dataset

        self.summary_results = []
        self.type_results = []

    def run(
        self,
        name: str,
        retriever: BaseRetriever,
    ) -> None:

        evaluator = RetrieverEvaluator(
            retriever=retriever,
            evaluation_dataset=self.dataset,
        )

        evaluator.evaluate()

        summary = evaluator.summary().set_index("Metric")["Value"].to_dict()
        summary["Experiment"] = name

        self.summary_results.append(summary)

        by_type = evaluator.summary_by_type()
        by_type.insert(0, "Experiment", name)

        self.type_results.append(by_type)

    def summary(
        self,
    ) -> pd.DataFrame:

        return (
            pd.DataFrame(self.summary_results)
            .set_index("Experiment")
        )

    def summary_by_type(
        self,
    ) -> pd.DataFrame:

        return pd.concat(
            self.type_results,
            ignore_index=True,
        )


