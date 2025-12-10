# Build stage
FROM node:20-alpine AS builder
WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .

# Set production env vars for build
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Default env vars for build (will be overridden at runtime by DigitalOcean)
# Using ARG to allow build-time override
ARG NEXT_PUBLIC_API_BASE=https://api.zkalphaflow.com
ARG NEXT_PUBLIC_API_WS_BASE=wss://api.zkalphaflow.com
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_placeholder

# Set them as ENV for the build process
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_WS_BASE=$NEXT_PUBLIC_API_WS_BASE
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

RUN npm run build

# Production stage
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built assets (public first, then standalone, then static)
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
