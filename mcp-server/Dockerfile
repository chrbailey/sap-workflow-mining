# SAP Workflow Mining - MCP Server
# Node.js 20 base image for MCP protocol server

FROM node:20-alpine

# Set environment variables
ENV NODE_ENV=production \
    PORT=3000

# Set working directory
WORKDIR /app

# Install build dependencies for native modules
RUN apk add --no-cache python3 make g++

# Copy package files first (for layer caching)
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci --only=production --ignore-scripts \
    && npm cache clean --force

# Install dev dependencies for building TypeScript
RUN npm ci --only=development --ignore-scripts

# Copy TypeScript config and source
COPY tsconfig.json ./
COPY src/ ./src/

# Build TypeScript to JavaScript
RUN npm run build

# Remove dev dependencies after build
RUN npm prune --production

# Remove build dependencies to reduce image size
RUN apk del python3 make g++

# Create non-root user for security
RUN addgroup -g 1001 -S appgroup \
    && adduser -S appuser -u 1001 -G appgroup \
    && chown -R appuser:appgroup /app

USER appuser

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))" || exit 1

# Default command
CMD ["node", "dist/index.js"]

# Labels
LABEL maintainer="SAP Workflow Mining Team" \
      version="1.0.0" \
      description="MCP server for SAP workflow mining"
