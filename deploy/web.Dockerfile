FROM node:22-alpine AS build

WORKDIR /app

RUN corepack enable

ARG VITE_AGENTREVIEW_API_URL=http://127.0.0.1:8000
ENV VITE_AGENTREVIEW_API_URL=$VITE_AGENTREVIEW_API_URL

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile

COPY apps/web ./apps/web
RUN pnpm --filter agentreviewops-web build

FROM nginx:1.27-alpine

COPY deploy/web.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

EXPOSE 80
