#!/bin/bash
set -e

echo "=== Market Pulse - Oracle Cloud Always Free Deployment ==="
echo "This script will:"
echo "  1. Update system and install Docker + Docker Compose"
echo "  2. Clone or update the Market Pulse repo"
echo "  3. Build and run with Oracle-optimized settings (persistent DB volume)"
echo "  4. Note: You must manually add ingress rules for port 8765 to the attached NSG (ig-quick-action-NSG) and/or security list after this (see guide)"
echo ""

# 1. System update and Docker install (works on Ubuntu 22.04 / Oracle Linux)
echo "[1/5] Installing Docker..."
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo systemctl enable docker
sudo systemctl start docker

# Add current user to docker group (so no sudo needed later)
sudo usermod -aG docker $USER || true

echo "[2/5] Cloning / updating Market Pulse..."
cd ~
if [ -d "market-pulse" ]; then
  cd market-pulse
  git pull || true
else
  git clone https://github.com/jaideeppyne/market-pulse.git
  cd market-pulse
fi

echo "[3/5] Preparing Oracle-optimized compose..."
# Use the oracle specific compose if present, else create a light one
if [ ! -f deploy/docker-compose.oracle.yml ]; then
  echo "Oracle compose not found in this clone, using default with tuning..."
fi

# Make sure data dir exists for volume
mkdir -p data

echo "[4/5] Building and starting Market Pulse (this can take a few minutes first time)..."
# Use the oracle compose if it exists, fallback to normal with env
if [ -f deploy/docker-compose.oracle.yml ]; then
  docker compose -f deploy/docker-compose.oracle.yml up -d --build
else
  # Fallback: use main compose + strong env overrides for Oracle free tier
  docker compose up -d --build
fi

echo "[5/5] Waiting for service to become healthy..."
sleep 15
docker ps | grep market-pulse || true

echo ""
echo "=== DONE ==="
PUBLIC_IP=$(curl -s ifconfig.me || echo "YOUR_VM_PUBLIC_IP")
echo "Your Market Pulse should be running at:"
echo "  http://${PUBLIC_IP}:8765"
echo ""
echo "IMPORTANT NEXT STEPS (do these in Oracle Cloud Console):"
echo "1. Go to your VM → Attached VNIC → Security Lists"
echo "2. Edit the Security List for your subnet"
echo "3. Add Ingress Rule:"
echo "   - Source CIDR: 0.0.0.0/0 (or your IP for more security)"
echo "   - Protocol: TCP"
echo "   - Destination Port Range: 8765"
echo ""
echo "4. (Recommended) Restart the container after security change:"
echo "   docker compose -f deploy/docker-compose.oracle.yml restart"
echo ""
echo "To view logs: docker logs -f market-pulse"
echo "To stop:      docker compose -f deploy/docker-compose.oracle.yml down"
echo "To update later (after git pull): docker compose -f deploy/docker-compose.oracle.yml up -d --build"
echo ""
echo "The DB is stored in a Docker named volume (market_pulse_data) → survives reboots."
echo "For a nicer URL later, put Cloudflare Tunnel in front (free)."
echo ""
echo "Enjoy your free public Market Pulse scanner!"