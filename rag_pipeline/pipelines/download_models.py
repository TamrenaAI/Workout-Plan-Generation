
from rag_pipeline.paths import MODELS_DIR
from rag_pipeline.model_registry import MODELS




def download_models(
    model_names: list[str] | None = None,
) -> None:

    MODELS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if model_names is None:
        model_names = list(MODELS.keys())

    for model_name in model_names:

        if model_name not in MODELS:
            raise ValueError(
                f"Unknown model: {model_name}"
            )

        spec = MODELS[model_name]

        model_path = MODELS_DIR / model_name

        if model_path.exists():
            print(f"{model_name} already exists.")
            continue

        print(f"⬇️ Downloading {spec.huggingface_name}...")

        model = spec.model_class(
            spec.huggingface_name,
            device="cpu",
        )

        model.save(
            str(model_path),
        )

        print(f"Saved to {model_path}")

def main():
    download_models()


if __name__ == "__main__":
    main()

