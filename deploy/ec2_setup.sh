#!/usr/bin/env bash
set -e

echo "=================================================="
echo " AWS EC2 Deployment Setup for Distributed URL Shortener "
echo "=================================================="

# Update system packages
echo "[1/5] Updating OS packages..."
sudo apt-get update -y && sudo apt-get upgrade -y

# Install Docker
echo "[2/5] Installing Docker..."
sudo apt-get install -y ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Enable and start Docker service
echo "[3/5] Starting Docker service..."
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# Setup project directory
echo "[4/5] Preparing environment..."
if [ ! -f .env.prod ]; then
    echo "Creating .env.prod template..."
    cat <<EOF > .env.prod
PROJECT_NAME="Distributed URL Shortener"
ENVIRONMENT="production"
BASE_URL="http://$(curl -s http://checkip.amazonaws.com)"
API_V1_STR="/api/v1"

# Connect to AWS RDS PostgreSQL:
DATABASE_URL="postgresql+asyncpg://<RDS_USER>:<RDS_PASS>@<RDS_HOST>:5432/<RDS_DBNAME>"
DB_POOL_SIZE=25
DB_MAX_OVERFLOW=10

# Connect to AWS ElastiCache Redis:
REDIS_URL="redis://<ELASTICACHE_PRIMARY_ENDPOINT>:6379/0"
CACHE_TTL_SECONDS=86400
CLICK_STREAM_KEY="url:click_stream"

WORKER_BATCH_SIZE=100
WORKER_POLL_INTERVAL=0.5
EOF
    echo ".env.prod created. Please edit with your RDS and ElastiCache endpoints before running."
fi

# Build and start services
echo "[5/5] Launching production cluster..."
echo "Run the following command once .env.prod is configured:"
echo "sudo docker compose -f docker-compose.prod.yml up -d --build"
echo "=================================================="
echo "Setup complete! Verify with: curl http://localhost/health"
