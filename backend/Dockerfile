# ============================================================
# MaisEV+ Backend — Multi-stage Dockerfile
# ============================================================

# Stage BASE — compartilha ferramentas de build nativas
FROM node:20-alpine AS base
WORKDIR /usr/src/app
RUN apk add --no-cache python3 make g++

# ============================================================
# Stage DEV — com devDependencies + nodemon hot-reload
# ============================================================
FROM base AS dev
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npx", "nodemon", \
     "--watch", "src", \
     "--ext", "js,json", \
     "src/server.js"]

# ============================================================
# Stage PROD — mínimo, seguro, sem devDeps
# ============================================================
FROM base AS prod
ENV NODE_ENV=production
COPY package*.json ./
RUN npm ci --omit=dev && \
    npm cache clean --force && \
    apk del python3 make g++
COPY . .
EXPOSE 3000
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
CMD ["node", "src/server.js"]
