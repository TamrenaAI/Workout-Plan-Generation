#!/bin/sh
set -e

if [ -n "$RAG_MODELS_S3_BUCKET" ]; then
  aws s3 sync "s3://${RAG_MODELS_S3_BUCKET}/${RAG_MODELS_S3_PREFIX:-models}" /app/data/models
fi

exec "$@"
