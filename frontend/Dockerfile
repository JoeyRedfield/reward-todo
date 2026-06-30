FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html .
COPY src ./src
COPY vite.config.js .

CMD ["npm", "run", "dev"]
