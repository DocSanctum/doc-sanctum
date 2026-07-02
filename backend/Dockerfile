FROM python:3.11-slim

WORKDIR /app

# Optional corporate proxy for pip install and the embedding model download below
# (leave unset for direct internet access)
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download and warm the local semantic-search embedding model at build
# time (research.md §2 deployment note) so registering a source doesn't pay
# a first-run network download, and the container can run fully offline.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warmup'])"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
