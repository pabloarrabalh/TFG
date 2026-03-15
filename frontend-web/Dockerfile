# ── Stage 1: Build React/Vite app ────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install

COPY . .

# VITE_API_URL is injected at build time so the frontend knows where to reach
# the backend. Default to empty string so Nginx proxy handles it in local Docker.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build          # outputs to /app/dist

# ── Stage 2: Serve with Nginx ─────────────────────────────────────────────────
FROM nginx:alpine

# Remove default site
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config that proxies /api/* and /static/* to backend
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
