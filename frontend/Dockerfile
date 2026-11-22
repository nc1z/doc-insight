# Build context is the repo root: the pnpm lockfile and workspace config live there.
FROM node:26.13.1-alpine AS build

ENV HUSKY=0

RUN npm install --global pnpm@11

WORKDIR /repo

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY frontend/package.json frontend/
COPY backend/package.json backend/
COPY tools/openapi-gen/package.json tools/openapi-gen/
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --filter frontend

COPY frontend/ frontend/
RUN pnpm --filter frontend build


FROM nginx:1.30-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/frontend/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1
