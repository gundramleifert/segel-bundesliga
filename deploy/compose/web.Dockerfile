# The site for the Compose stack: the SPA built with Vite, served by nginx, which also
# proxies /api to the api service — the same split Render runs (a static site with an
# /api/* rewrite to the API, render.yaml), so the browser stays same-origin.
# Build context: repo root.

FROM node:22.20.0-alpine AS build
RUN npm install -g pnpm@12.16.0
WORKDIR /web
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --prod=false
COPY web/ ./
# The role switcher and the other development tools are compiled in or left out at build
# time (web/src/dev/devTools.ts); compose.yaml passes SBL_DEV_LOGIN through here.
ARG VITE_DEV_TOOLS=false
ENV VITE_DEV_TOOLS=${VITE_DEV_TOOLS}
RUN pnpm build

FROM nginx:1.29.1-alpine
COPY deploy/compose/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
