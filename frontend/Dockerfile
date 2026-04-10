FROM node:20-alpine AS builder

WORKDIR /app

ARG VITE_API_BASE=http://localhost:8000
ARG VITE_BOOT_MODE=demo

ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_BOOT_MODE=$VITE_BOOT_MODE

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html ./
COPY components.json metadata.json ./
COPY eslint.config.js postcss.config.js tailwind.config.ts tsconfig.app.json tsconfig.json tsconfig.node.json vite.config.ts vitest.config.ts playwright.config.ts playwright-fixture.ts ./
COPY public ./public
COPY src ./src
COPY scripts ./scripts

RUN npm run build

FROM nginx:1.27-alpine AS production

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

FROM node:20-alpine AS dev

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html ./
COPY components.json metadata.json ./
COPY eslint.config.js postcss.config.js tailwind.config.ts tsconfig.app.json tsconfig.json tsconfig.node.json vite.config.ts vitest.config.ts playwright.config.ts playwright-fixture.ts ./
COPY public ./public
COPY src ./src
COPY scripts ./scripts

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
