# PBM frontend(Next.js)。docker compose up での実行検証は未実施(TASKS T-112, A-204)
FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
