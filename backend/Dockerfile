# Fetches mermaid's browser bundle so shared pages can draw diagrams without
# any third-party script host. Keep the version in step with the frontend's.
FROM node:20-alpine AS mermaid
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY}
COPY certs/ /tmp/corporate-certs/
RUN cat /tmp/corporate-certs/*.crt > /usr/local/share/corporate-ca-bundle.pem 2>/dev/null; \
    touch /usr/local/share/corporate-ca-bundle.pem
ENV NODE_EXTRA_CA_CERTS=/usr/local/share/corporate-ca-bundle.pem
ARG MERMAID_VERSION=11.16.1
WORKDIR /tmp/mermaid
RUN npm pack "mermaid@${MERMAID_VERSION}" --silent \
    && tar -xzf mermaid-*.tgz package/dist/mermaid.min.js \
    && mv package/dist/mermaid.min.js /mermaid.min.js

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

# Pre-download and warm the embedding model at build time for offline use.
COPY app/ app/
RUN python -c "from app.vectorstore.embedding import MultilingualEmbeddingFunction; MultilingualEmbeddingFunction()(['warmup'])"

COPY . .
# Kept outside /app so the dev stack's source bind mount does not hide it.
COPY --from=mermaid /mermaid.min.js /opt/mermaid/mermaid.min.js

# Serves the API on 8000 and the token-protected remote MCP listener on 8100.
CMD ["python", "-m", "app.serve"]
