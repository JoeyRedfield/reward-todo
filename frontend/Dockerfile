FROM my-project-frontend:latest

WORKDIR /app

COPY package.json .
RUN npm install

COPY index.html .
COPY src ./src
COPY vite.config.js .

CMD ["npm", "run", "dev"]
