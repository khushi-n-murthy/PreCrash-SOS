# ==============================================================================
# PreCrash SoS: Predictive Emergency Dispatch Portal
# Frontend Service Container Specification (Member D Strategy)
# ==============================================================================

# Layer 1: Establish high-performance, lightweight web server base image
FROM nginx:alpine

# Layer 2: Clean default document root to avoid indexing standard Nginx artifacts
RUN rm -rf /usr/share/nginx/html/*

# Layer 3: Map directory assets into the container file system (UPDATED CONTEXT)
# Copy static resources relative to the project root context
COPY dashboard_frontend/static /usr/share/nginx/html/static

# Copy portal_index.html template relative to the project root context
COPY dashboard_frontend/templates/portal_index.html /usr/share/nginx/html/index.html

# Layer 4: Expose the standard internal web container ingress traffic port 80
EXPOSE 80

# Layer 5: Define runtime execution command to run Nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]