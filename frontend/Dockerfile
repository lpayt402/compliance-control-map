FROM node:22.23.2-alpine3.23 AS build
WORKDIR /app
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack pnpm install --frozen-lockfile
COPY frontend/ ./
RUN corepack pnpm build

FROM nginxinc/nginx-unprivileged:1.30.4-alpine3.24
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
