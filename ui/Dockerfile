## UI Build stage
FROM node:24-alpine AS ui-builder
RUN npm install -g pnpm
WORKDIR /builder
COPY ./package.json ./pnpm-lock.yaml ./pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY ./ .
RUN pnpm run build


## Final stage serving the built UI with nginx
FROM nginx:alpine AS final

WORKDIR /var/www/html

# Copy built UI from the builder stage
COPY --from=ui-builder /builder/dist/ .

# Copy custom nginx configuration
COPY container/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80