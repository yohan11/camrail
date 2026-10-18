# ==============================================================================
# CAMRAIL RailMind Lite - Frontend Dockerfile Durci (Non-Root USER app)
# ==============================================================================
# Image officielle Node.js 20 Alpine épinglée (vérifiée le 2026-10-18)
FROM node:20.18.0-alpine AS base

WORKDIR /app

FROM base AS deps
RUN apk add --no-cache libc6-compat
COPY package.json package-lock.json* ./
RUN npm install

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# IMPORTANT : NEXT_PUBLIC_API_URL est figé au build dans Next.js.
# En mode HTTPS unifié derrière Nginx, cette valeur peut être /api/v1 (relative).
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Création de l'utilisateur de sécurité non-root 'app' (UID 1001)
RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 -G app app

COPY --from=builder /app/public ./public
COPY --from=builder --chown=app:app /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

USER app

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npm", "run", "start"]
