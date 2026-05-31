FROM nginx:alpine
RUN rm -rf /usr/share/nginx/html/*
COPY dashboard_frontend/static /usr/share/nginx/html/static
COPY dashboard_frontend/templates/portal_index.html /usr/share/nginx/html/index.html
COPY dashboard_frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]