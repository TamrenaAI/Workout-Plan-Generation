FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    awscli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# sentence-transformers pulls in torch as a transitive dependency; without pinning it
# explicitly, pip resolves the default PyPI wheel, which bundles full CUDA runtime libs
# (nvidia-cublas-cu12, nvidia-cudnn-cu12, etc.) — multiple GB never used here, since
# tools/rag/pipeline.py always loads models with device="cpu". Installing the CPU-only
# build first satisfies that dependency before requirements.txt's install ever considers it.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# database/exercises_dataset/media.tar is a single pre-built archive of the 2648
# exercise GIFs (see .dockerignore) — extracting it here means Docker's slow
# many-small-files transfer only ever has to move ONE file across the build-context
# boundary; the actual per-file work happens inside the container via native tar.
RUN tar -xf database/exercises_dataset/media.tar -C database/exercises_dataset \
    && rm database/exercises_dataset/media.tar

# Pre-download and bake RAG models (dense, reranker, sparse) into /app/data/models
# so the image is fully self-contained for deployment to AWS ECR / ECS.
RUN python -m tools.rag.pipeline

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8001

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
