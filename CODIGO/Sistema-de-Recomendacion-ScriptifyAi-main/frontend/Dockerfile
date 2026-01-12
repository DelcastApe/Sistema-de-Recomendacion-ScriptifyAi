FROM nginx:alpine

# Copia TODO tu frontend (incluye /recomendador, index.html, etc.)
COPY . /usr/share/nginx/html/

# Config de Nginx (proxy /api → api:8000)
COPY nginx.conf /etc/nginx/conf.d/default.conf
