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

# docker-compose sets the container's runtime HOME to the host user's HOME
# (so local filesystem sources can be browsed under the same paths) and
# bind-mounts it read-only. chromadb resolves its embedding model cache to
# Path.home()/.cache/chroma, so HOME must match the runtime value here too —
# otherwise the model warmed below is baked under the build's default /root
# and is unreachable once HOME points elsewhere at runtime.
ARG HOME=/root
ENV HOME=${HOME}

# Optional corporate CA certificate(s), for TLS-intercepting proxies.
# Drop PEM-encoded certs as backend/certs/*.crt (gitignored) before building;
# an empty directory is a no-op. Trusts them for both `pip install` below
# and the app's own outbound httpx requests to remote doc sources at runtime.
COPY certs/ /usr/local/share/ca-certificates/corporate/
RUN update-ca-certificates
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# certifi ships its own bundled roots and ignores the OS trust store above,
# so extend it with the same corporate CA(s) for libraries (httpx) that rely on it.
RUN cat /usr/local/share/ca-certificates/corporate/*.crt 2>/dev/null >> "$(python -c 'import certifi; print(certifi.where())')" || true

# Pre-download and warm the local semantic-search embedding model at build
# time (research.md §2 deployment note) so registering a source doesn't pay
# a first-run network download, and the container can run fully offline.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warmup'])"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
