# Deploy Market Pulse on Oracle Cloud Always Free (Completely Free)

This guide lets you get a **public, always-on** version of Market Pulse at zero cost using Oracle Cloud's generous Always Free tier.

## Why Oracle Cloud?
- Truly always-free (no expiration)
- Powerful instances (up to 4 cores / 24 GB RAM on ARM)
- 200 GB storage + 10 TB bandwidth
- Full Docker support
- Public IP included

## Step 1: Create Oracle Cloud Account (One-time)

1. Go to https://www.oracle.com/cloud/free/
2. Click **Start for free** and sign up with your email.
3. Complete verification (email + sometimes phone).
4. Choose a region close to you (important for capacity).
5. After login, you may need to upgrade to **Pay As You Go** (still $0 if you only use Always Free resources). This often unlocks more capacity.

**Tip**: If you can't create an Ampere (ARM) instance, create any micro instance first, then the ARM shapes usually become available.

## Step 2: Create a Free VM

1. In Oracle Console, go to **Compute → Instances → Create Instance**.
2. Name it: `market-pulse`
3. **Image**: Ubuntu 22.04 (or Oracle Linux 8/9)
4. **Shape** (choose one that says **Always Free**):
   - Best: `VM.Standard.A1.Flex` (Ampere ARM) — give it 4 OCPU and 24 GB RAM if available.
   - Fallback: `VM.Standard.E2.1.Micro` (AMD)
5. **Boot Volume**: 50 GB (or more, up to your free quota).
6. **Networking**: Use default VCN. Make sure **Assign a public IPv4 address** is enabled.
7. Create the instance.

Wait 2-3 minutes until it shows **Running**.

## Step 3: Connect to Your VM via SSH

1. Download your private key (`.key` file) when creating the instance (or later from the instance page).
2. Make it private:
   ```bash
   chmod 400 your-key.key
   ```
3. Connect:
   ```bash
   ssh -i your-key.key ubuntu@YOUR_PUBLIC_IP
   ```
   (Use `opc` user if you chose Oracle Linux image.)

## Step 4: Run the Automated Setup (This is the magic part)

Once SSH'd in, run these commands one by one:

```bash
# Download the Oracle-specific setup script
wget https://raw.githubusercontent.com/jaideeppyne/market-pulse/main/deploy/oracle-setup.sh

# Make it executable
chmod +x oracle-setup.sh

# Run it (this installs Docker, clones the repo, builds, and starts everything)
./oracle-setup.sh
```

The script will:
- Install Docker + Compose
- Clone the latest Market Pulse
- Start it with Oracle-optimized settings (slower scans to stay light on free tier)
- Use a persistent Docker volume for the database

## Step 5: Open the Port in Oracle (Critical!)

Even after the script runs, traffic is blocked by default.

1. In Oracle Console, go to your Instance → **Attached VNIC** (click the name).
2. Click **Security Lists** → edit the one that is attached (usually "Default Security List").
3. Click **Add Ingress Rules**.
4. Fill:
   - **Source CIDR**: `0.0.0.0/0` (for public access) **or** your home IP for safety.
   - **Protocol**: TCP
   - **Destination Port Range**: `8765`
5. Save.

## Step 6: Access Your Public Website

After the security rule is added, wait 30 seconds, then visit:

```
http://YOUR_VM_PUBLIC_IP:8765
```

You should see the full live Market Pulse dashboard with crawlers running.

## Useful Commands (run inside the VM)

```bash
# View logs (live)
docker logs -f market-pulse

# Restart
docker compose -f ~/market-pulse/deploy/docker-compose.oracle.yml restart

# Stop
docker compose -f ~/market-pulse/deploy/docker-compose.oracle.yml down

# Update to latest code (future pulls)
cd ~/market-pulse
git pull
docker compose -f deploy/docker-compose.oracle.yml up -d --build

# Check disk / resources
df -h
docker stats
```

## Making It Even Better (Optional but Recommended)

### Nicer URL with Cloudflare (Free)
1. Sign up at cloudflare.com (free).
2. Add a domain (you can use a free `.tk`, `.ml`, or buy cheap one).
3. In Cloudflare, create a Tunnel (Zero Trust → Tunnels).
4. Run the tunnel on your Oracle VM pointing to `http://localhost:8765`.
5. You get `https://market-pulse.yourdomain.com` with free HTTPS and DDoS protection.

I can give you the exact `docker-compose` addition for Cloudflare Tunnel if you want this.

### Reduce Resource Usage Further
The setup script already uses conservative values. You can make it even lighter by editing `config.yaml` or adding more env vars.

## Troubleshooting

- **Can't reach the site**: Double-check the Security List ingress rule for port 8765.
- **Container not starting**: `docker logs market-pulse`
- **Low resources**: The script already slows down the scanners. You can increase intervals more.
- **ARM capacity error**: Try a different region or create a micro AMD instance first.

## What You Get
- Completely free public website
- 24/7 running crawlers + live WebSocket updates
- Persistent database (survives VM reboots)
- Easy updates via git + rebuild

Everything is set up for Oracle. The only manual parts are:
1. Creating the Oracle account + VM (one time)
2. Adding the security rule (one time)
3. Running the one script

After that, your Market Pulse is live for the world.

---

**Need help with the next step?** Tell me:
- "Give me the Cloudflare Tunnel docker-compose addition"
- "I ran the script, here's the error"
- Or just "next" after you create the account.

You now have a complete, copy-paste deployment for Oracle Cloud. Go create the account and run the script! 🚀
