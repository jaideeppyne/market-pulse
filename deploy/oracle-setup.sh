#!/usr/bin/env bash
# Market Pulse — Oracle Cloud Always Free one-shot setup.
#
# Works on BOTH Always-Free images:
#   * Ubuntu 22.04 / 24.04  (apt, ufw or no host firewall)
#   * Oracle Linux 8/9      (dnf, firewalld + restrictive iptables)
#
# It will:
#   1. Install Docker Engine + compose plugin (distro-aware)
#   2. Clone or update the Market Pulse repo
#   3. Write a .dockerignore so the giant local DB / venv / node_modules never
#      land in the Docker build context (huge image + slow build otherwise)
#   4. Generate a strong MARKET_PULSE_WRITE_KEY into deploy/.env (idempotent)
#   5. Open the app port (8765) in the OS firewall (firewalld AND iptables)
#   6. Build + start with the Oracle-tuned compose (persistent DB volume)
#
# You STILL must add an ingress rule for TCP 8765 in the OCI Console
# (Security List or NSG) — the OS firewall and the cloud firewall are separate.
set -euo pipefail

REPO_URL="https://github.com/jaideeppyne/market-pulse.git"
APP_PORT="8765"

echo "=== Market Pulse — Oracle Cloud Always Free setup ==="

# ---------------------------------------------------------------------------
# 0. Detect distro / package manager
# ---------------------------------------------------------------------------
if command -v apt-get >/dev/null 2>&1; then
  PKG="apt"
elif command -v dnf >/dev/null 2>&1; then
  PKG="dnf"
else
  echo "Unsupported distro (need apt or dnf). Aborting." >&2
  exit 1
fi
echo "[0/6] Detected package manager: $PKG"

# ---------------------------------------------------------------------------
# 1. Install Docker
# ---------------------------------------------------------------------------
echo "[1/6] Installing Docker..."
if ! command -v docker >/dev/null 2>&1; then
  if [ "$PKG" = "apt" ]; then
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg git
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  else
    # Oracle Linux 8/9
    sudo dnf install -y dnf-utils git
    sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  fi
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER" || true
else
  echo "Docker already installed, skipping."
fi

# ---------------------------------------------------------------------------
# 2. Clone / update repo
# ---------------------------------------------------------------------------
echo "[2/6] Cloning / updating Market Pulse..."
cd ~
if [ -d "market-pulse/.git" ]; then
  cd market-pulse
  git pull --ff-only || true
else
  git clone "$REPO_URL"
  cd market-pulse
fi
REPO_DIR="$(pwd)"

# ---------------------------------------------------------------------------
# 3. Keep the build context lean.
#    The repo's `COPY . .` would otherwise pull in any local data/*.db, the
#    Python .venv, and web/node_modules — bloating the image by hundreds of MB.
#    A fresh clone is already clean, but writing this makes rebuilds safe even
#    after the app has created a large data/market_pulse.db on disk.
# ---------------------------------------------------------------------------
echo "[3/6] Writing .dockerignore to keep the build context small..."
cat > "$REPO_DIR/.dockerignore" <<'EOF'
.git
.venv
.venv*
**/__pycache__
**/*.pyc
web/node_modules
web/dist
data/*.db
data/*.db-wal
data/*.db-shm
data/*.bak
*.log
EOF

# ---------------------------------------------------------------------------
# 4. Generate a write key for the public instance (idempotent).
# ---------------------------------------------------------------------------
echo "[4/6] Ensuring deploy/.env has a write key..."
mkdir -p "$REPO_DIR/deploy"
ENV_FILE="$REPO_DIR/deploy/.env"
if [ ! -f "$ENV_FILE" ] || ! grep -q '^MARKET_PULSE_WRITE_KEY=' "$ENV_FILE"; then
  KEY="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  echo "MARKET_PULSE_WRITE_KEY=${KEY}" >> "$ENV_FILE"
  echo "  -> Generated MARKET_PULSE_WRITE_KEY (saved in deploy/.env). KEEP THIS SECRET."
  echo "     Send it as the 'X-API-Key' header for any write/mutating API call."
else
  echo "  -> deploy/.env already has a MARKET_PULSE_WRITE_KEY, keeping it."
fi

# ---------------------------------------------------------------------------
# 5. Open the app port in the OS firewall (separate from the OCI Security List!)
# ---------------------------------------------------------------------------
echo "[5/6] Opening port ${APP_PORT} in the host firewall..."
if command -v firewall-cmd >/dev/null 2>&1 && sudo systemctl is-active --quiet firewalld; then
  sudo firewall-cmd --permanent --add-port=${APP_PORT}/tcp
  sudo firewall-cmd --reload
  echo "  -> firewalld: opened ${APP_PORT}/tcp"
else
  # Oracle Linux images often ship restrictive iptables WITHOUT firewalld active.
  if sudo iptables -L INPUT -n 2>/dev/null | grep -q "REJECT"; then
    sudo iptables -I INPUT -p tcp --dport ${APP_PORT} -m state --state NEW,ESTABLISHED -j ACCEPT || true
    # Persist (netfilter-persistent on Ubuntu, /etc/iptables on OL if present)
    if command -v netfilter-persistent >/dev/null 2>&1; then
      sudo netfilter-persistent save || true
    elif [ -d /etc/iptables ]; then
      sudo bash -c "iptables-save > /etc/iptables/rules.v4" || true
    fi
    echo "  -> iptables: inserted ACCEPT for ${APP_PORT}/tcp"
  else
    echo "  -> No restrictive host firewall detected; nothing to open at OS level."
  fi
fi

# ---------------------------------------------------------------------------
# 6. Build + start
# ---------------------------------------------------------------------------
echo "[6/6] Building and starting Market Pulse (first build takes a few minutes)..."
mkdir -p "$REPO_DIR/data"
# `sg docker` lets the freshly-added group take effect without re-login.
COMPOSE="docker compose -f deploy/docker-compose.oracle.yml --env-file deploy/.env"
if id -nG "$USER" | grep -qw docker; then
  $COMPOSE up -d --build
else
  sudo $COMPOSE up -d --build
fi

echo ""
echo "Waiting for the service to become healthy..."
sleep 15
(docker ps --filter name=market-pulse || sudo docker ps --filter name=market-pulse) 2>/dev/null | grep market-pulse || true

PUBLIC_IP="$(curl -s --max-time 5 ifconfig.me || echo 'YOUR_VM_PUBLIC_IP')"
echo ""
echo "=== DONE (almost) ==="
echo "Local check on the VM:"
echo "  curl -f http://localhost:${APP_PORT}/api/health"
echo ""
echo "PUBLIC URL (after you add the OCI ingress rule below):"
echo "  http://${PUBLIC_IP}:${APP_PORT}"
echo ""
echo "FINAL MANUAL STEP — open the port in the OCI Console (cloud firewall):"
echo "  Instance -> VNIC -> Subnet -> Security List (or NSG) -> Add Ingress Rule"
echo "    Stateless: No   Source CIDR: 0.0.0.0/0   IP Protocol: TCP"
echo "    Destination Port Range: ${APP_PORT}"
echo ""
echo "Your write key (needed for X-API-Key on write calls) is in: deploy/.env"
echo "Logs:   docker logs -f market-pulse"
echo "Update: cd ~/market-pulse && git pull && $COMPOSE up -d --build"
