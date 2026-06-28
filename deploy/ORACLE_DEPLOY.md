# Deploy Market Pulse on Oracle Cloud Always Free (Completely Free)

This guide lets you get a **public, always-on** version of Market Pulse at zero cost using Oracle Cloud's generous Always Free tier.

> For the full, copy-pasteable, non-expert runbook (including the no-SSH OCI
> Cloud Shell path), see **[`../DEPLOY_OCI_RUNBOOK.md`](../DEPLOY_OCI_RUNBOOK.md)** at the repo root.
> This file is the quick reference.

## Why Oracle Cloud?
- Truly always-free (no expiration)
- Ampere ARM instances: **2 OCPU / 12 GB RAM total** on the Always Free tier
  (this dropped from 4 OCPU / 24 GB in June 2026 — older guides are stale)
- 200 GB total block storage (boot + block combined) + 10 TB/month outbound
- Full Docker support
- Public IPv4 included

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
4. **Shape** (choose one that shows the **Always Free-eligible** label):
   - Best: `VM.Standard.A1.Flex` (Ampere ARM) — give it up to **2 OCPU and 12 GB RAM** (the Always Free max as of June 2026).
   - Fallback: `VM.Standard.E2.1.Micro` (AMD, 1/8 OCPU + **1 GB RAM** — tight for this app; expect slow scans).
5. **Boot Volume**: keep the default 50 GB (minimum is 47 GB). Do NOT push it toward 200 GB — that uses your entire free block-storage allotment in one instance.
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

Even after the script runs, traffic is blocked by **two** separate firewalls.
The setup script already opens the **OS firewall** (firewalld/iptables) for you;
you must still open the **OCI cloud firewall**:

1. In Oracle Console, open your Instance → click the **Subnet** under "Primary VNIC".
2. Click the **Security List** (usually "Default Security List for ...").
3. Click **Add Ingress Rules**.
4. Fill:
   - **Stateless**: leave unchecked (stateful).
   - **Source CIDR**: `0.0.0.0/0` (for public access) **or** your home IP for safety.
   - **IP Protocol**: TCP
   - **Destination Port Range**: `8765`
5. Save.

> Note: Oracle Linux images ship with restrictive iptables, so the port MUST be
> open in BOTH the OS firewall AND the Security List/NSG. The script handles the
> OS side; if you reinstalled or skipped it, open it manually:
> `sudo firewall-cmd --permanent --add-port=8765/tcp && sudo firewall-cmd --reload`
> (or the iptables equivalent on minimal images).

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

## Cost & reclaim warnings (stay at $0)

- **Idle reclaim**: Oracle may reclaim Always Free instances that are idle for 7
  days (95th-percentile CPU <20% AND network <20%, plus memory <20% on ARM). This
  app's always-on scanners keep CPU/network active, so a running Market Pulse is
  not "idle". To be extra safe, convert the account to **Pay As You Go** — you are
  still charged $0 as long as you stay within Always Free limits, and PAYG accounts
  are exempt from idle reclamation.
- **Block storage**: keep boot volume at ~50 GB. The free cap is 200 GB total
  (boot + block combined). A 200 GB boot volume consumes the whole allotment.
- **Outbound data**: 10 TB/month is free. A scanner + dashboard is nowhere near
  this; only worry if you proxy large downloads through the box.
- **Second VNIC / extra public IPs / load balancer beyond the one free flexible
  LB**: avoid unless you know they're free.

## Troubleshooting

- **Can't reach the site**: Check BOTH the OCI Security List ingress rule AND the
  OS firewall (`sudo firewall-cmd --list-ports` or `sudo iptables -L INPUT -n`).
- **Container not starting**: `docker logs market-pulse`
- **Writes return 401/403**: that's expected on a public box — send the
  `MARKET_PULSE_WRITE_KEY` (from `deploy/.env`) as the `X-API-Key` header.
- **Low resources**: The compose already slows the scanners. Raise the intervals
  further in `config.yaml` (mounted read-only) or via env in the compose.
- **ARM "out of host capacity"**: try a different Availability Domain, retry later,
  or upgrade to Pay As You Go (unlocks more capacity; still $0 within free limits).

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
