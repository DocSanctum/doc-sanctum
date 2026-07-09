FROM node:20-alpine AS dev
WORKDIR /app

# Optional corporate proxy for npm install (leave unset for direct internet access)
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY}

# Optional corporate CA certificate(s), for TLS-intercepting proxies.
# Drop PEM-encoded certs as frontend/certs/*.crt (gitignored) before building;
# an empty directory is a no-op. NODE_EXTRA_CA_CERTS extends (not replaces)
# Node's default trust store, so it covers npm install below without
# disabling verification of everything else.
COPY certs/ /tmp/corporate-certs/
RUN cat /tmp/corporate-certs/*.crt > /usr/local/share/corporate-ca-bundle.pem 2>/dev/null; \
    touch /usr/local/share/corporate-ca-bundle.pem
ENV NODE_EXTRA_CA_CERTS=/usr/local/share/corporate-ca-bundle.pem

COPY package.json .
RUN npm install
COPY . .

FROM dev AS build
RUN npm run build

FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
