FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
ENV API_UPSTREAM=http://api:8000
ENV PORT=80
ENV NGINX_ENVSUBST_FILTER=API_UPSTREAM,PORT
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
