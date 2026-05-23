FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_AGENTREVIEW_API_URL=http://127.0.0.1:8000
ENV VITE_AGENTREVIEW_API_URL=$VITE_AGENTREVIEW_API_URL

COPY apps/web/package*.json ./
RUN npm ci

COPY apps/web ./
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/web.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
