FROM node:18-slim

WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 8080

# Set environment variables
ENV NODE_ENV=production

# Start the application
CMD ["npm", "start"] 