# ── Stage 1: builder — install deps and build the SvelteKit SPA ──
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies — cached layer, only re-builds when package files change
COPY package.json ./
RUN npm install

# Copy source and build the static SPA (adapter-static outputs to build/)
COPY . .
RUN npm run build


# ── Stage 2: runtime — nginx serving the built SPA + proxying /api ─
FROM nginx:1.27-alpine AS runtime

# Remove the default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom nginx config (SPA fallback + /api proxy)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built static assets from the builder
COPY --from=builder /app/build /usr/share/nginx/html

# nginx:alpine already ships as a non-root-friendly image; the default user is nginx.
# We keep the image small — no extra packages needed.

EXPOSE 80

# Healthcheck — nginx serves the SPA index, any 2xx/3xx is healthy
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
