# Base on official Node.js Alpine image
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Install dependencies first for caching
COPY package.json package-lock.json ./
RUN npm ci

# Copy application files
COPY . .

# Build the Next.js app
RUN npm run build

# Expose port
EXPOSE 3000

# Start Next.js in production mode
CMD ["npm", "start"]
