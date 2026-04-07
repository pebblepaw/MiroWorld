FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html ./
COPY components.json metadata.json ./
COPY eslint.config.js postcss.config.js tailwind.config.ts tsconfig.app.json tsconfig.json tsconfig.node.json vite.config.ts vitest.config.ts playwright.config.ts playwright-fixture.ts ./
COPY public ./public
COPY src ./src
COPY scripts ./scripts

RUN npm run build

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
