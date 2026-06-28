# Deploy Market Pulse on Oracle Cloud Always Free — Complete Runbook ($0 forever)

This is a precise, copy-pasteable runbook to get **Market Pulse** running as a
public website on Oracle Cloud Infrastructure (OCI) **for free, with no expiry**.

It covers two paths:

- **Path A — No SSH keys (preferred):** do everything from the OCI **Cloud Shell**
  in your browser. You never paste an SSH key anywhere.
- **Path B — Local terminal / SSH (fallback):** classic `ssh -i key ...` flow.

Both paths end with the same result: `http://YOUR_PUBLIC_IP:8765` serving the
live dashboard with crawlers running and history that survives reboots.

> Reading time: ~5 min. Hands-on time: ~15–20 min (most of it waiting for the
> first Docker build).

---

## 0. What you're deploying (1-minute mental model)

- A single FastAPI app (`python -m app.main`) that also **serves the prebuilt
  frontend** from the committed `frontend/` folder — there is **no separate
  Node/React build step at deploy time** (the `web/` folder is the React source;
  the compiled output is already in `frontend/` and is what gets served).
- It listens on **port 8765** and exposes `GET /api/health`.
- It stores all history in a SQLite file at **`data/market_pulse.db`**, which we
  put on a **persistent Docker volume** so it survives reboots and rebuilds.
- It runs background scanners (prices, news, earnings) that hit `yfinance` and
  RSS feeds — so we tune the intervals down to be gentle on a free instance.

---

## 1. Verified Oracle Always Free facts (June 2026)

These drive every choice below. Sources at the bottom.

| Resource | Always Free allowance (2026) |
|---|---|
| **ARM compute** `VM.Standard.A1.Flex` | **2 OCPU + 12 GB RAM total** (1,500 OCPU-hrs + 9,000 GB-hrs/mo). *Reduced from 4 OCPU/24 GB in June 2026.* |
| **AMD compute** `VM.Standard.E2.1.Micro` | 1/8 OCPU + **1 GB RAM**, 50 Mbps, public IP. Up to 2 of them. |
| **Block storage** | **200 GB total** (boot + block combined). Default boot volume 50 GB; **minimum 47 GB**. |
| **Outbound data** | **10 TB / month** free. |
| **Public IPv4** | Included with the instance's VNIC. **Free.** |
| **Custom inbound port (8765)** | Free — you just add an ingress rule. No charge for opening ports. |
| **Idle reclaim** | Oracle may reclaim an instance idle 7 days straight (95th-pct CPU <20% **and** network <20%, **and** memory <20% on ARM). |

**Recommended shape:** `VM.Standard.A1.Flex` with **2 OCPU / 12 GB** (the full free
ARM allotment). The AMD micro's 1 GB RAM is very tight for pandas/numpy scanning —
use it only as a fallback.

**Stay free, guaranteed:** the app's always-on scanners keep CPU + network active,
so a running Market Pulse is **not "idle"** and won't be reclaimed. For extra
safety you may convert the account to **Pay As You Go (PAYG)** — you are still
billed **$0** as long as you stay within Always Free limits, and PAYG accounts are
**exempt from idle reclamation** and get better ARM capacity.

---

## 2. One-time: create the account and the VM (same for Path A and B)

### 2.1 Create the account
1. Go to <https://www.oracle.com/cloud/free/> → **Start for free**.
2. Sign up (email + card for identity verification; **Always Free resources are
   never charged**). Pick a **home region close to you** — your free resources
   live in the home region and **cannot be moved later**.

### 2.2 Create the VM
1. Console → hamburger menu → **Compute → Instances → Create instance**.
2. **Name:** `market-pulse`.
3. **Image and shape → Edit:**
   - **Image:** *Canonical Ubuntu 22.04* (simplest) — or *Oracle Linux 9* (note the
     extra OS-firewall step, handled by our script).
   - **Shape → Change shape → Ampere → `VM.Standard.A1.Flex`** → set **2 OCPUs**
     and **12 GB** memory. Confirm it shows the **"Always Free-eligible"** label.
     - If you get **"Out of host capacity"**: switch the **Availability Domain**
       dropdown and retry; try again later; or upgrade to PAYG. (See §6.)
4. **Networking:** keep the default VCN/subnet. Ensure **"Assign a public IPv4
   address" = Yes**.
5. **Add SSH keys:**
   - **Path A (no SSH):** choose **"No SSH keys"** — you'll use Cloud Shell.
     *(Or generate a key pair and ignore it; Cloud Shell injects its own key.)*
   - **Path B (SSH):** choose **"Generate a key pair for me"** and **download the
     private key** now.
6. **Boot volume:** leave the default **50 GB**. Do **not** raise it toward 200 GB
   (that would eat your whole free storage allotment).
7. **Create**. Wait until status = **Running**, then copy the **Public IP address**.

---

## 3. Path A — Deploy via OCI Cloud Shell (no SSH keys) ✅ preferred

Cloud Shell is a free browser terminal that can SSH into your instance for you.

1. In the OCI Console top bar, click the **`>_` Cloud Shell** icon (Developer
   tools). A terminal opens at the bottom. Wait for it to finish initializing.
2. **Let Cloud Shell reach your instance.** Two easy options:
   - **Easiest:** Open your instance page → **Connect** / the SSH section, and use
     the Console's built-in connect. *Or* run the one-liner below — Cloud Shell
     already has an SSH key; add its public key to the instance:
     ```bash
     cat ~/.ssh/id_rsa.pub
     ```
     Copy that line. Then in the Console: **Instance → Resources → ... →** (if your
     image supports it, use **Cloud Shell connection**). If your tenancy offers the
     **"Connect with OCI Cloud Shell"** button on the instance page, just click it
     and skip the manual key step.
3. **SSH from Cloud Shell to the instance** (replace the IP; user is `ubuntu` for
   Ubuntu, `opc` for Oracle Linux):
   ```bash
   ssh ubuntu@YOUR_PUBLIC_IP
   ```
   Type `yes` to accept the host key.

   > If this refuses with "Permission denied (publickey)", it means the instance
   > doesn't have Cloud Shell's key. Re-create the instance and either paste the
   > `~/.ssh/id_rsa.pub` from step 2 into the **"Add SSH keys → Paste public keys"**
   > box, or use **Path B** with a downloaded key.

4. **Run the one-shot setup** (installs Docker, clones the repo, opens the OS
   firewall, generates a write key, builds, and starts):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/jaideeppyne/market-pulse/main/deploy/oracle-setup.sh -o oracle-setup.sh
   chmod +x oracle-setup.sh
   ./oracle-setup.sh
   ```
   First build takes a few minutes. When it finishes it prints your write key
   location (`deploy/.env`) and the public URL.

5. **Open the port in the OCI cloud firewall** — see **§5** (required; the script
   only opens the OS firewall).

6. **Verify** — see **§7**.

---

## 4. Path B — Deploy via your local terminal (SSH) — fallback

1. Make the downloaded key private:
   ```bash
   chmod 400 ~/Downloads/ssh-key-*.key
   ```
2. SSH in (`ubuntu` for Ubuntu, `opc` for Oracle Linux):
   ```bash
   ssh -i ~/Downloads/ssh-key-*.key ubuntu@YOUR_PUBLIC_IP
   ```
3. Run the same one-shot setup as Path A step 4:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/jaideeppyne/market-pulse/main/deploy/oracle-setup.sh -o oracle-setup.sh
   chmod +x oracle-setup.sh
   ./oracle-setup.sh
   ```
4. Open the OCI ingress rule (**§5**), then verify (**§7**).

---

## 5. Open port 8765 — TWO firewalls (critical)

Traffic is blocked by **two independent** firewalls. The setup script opens the
**OS firewall** for you; you must still open the **OCI cloud firewall** by hand.

### 5.1 OCI Security List ingress rule (cloud firewall — manual, one-time)
1. Console → your **Instance** → under *Primary VNIC*, click the **Subnet** link.
2. Click the **Security List** (e.g. "Default Security List for ...").
3. **Add Ingress Rules** →
   - **Stateless:** unchecked
   - **Source Type:** CIDR
   - **Source CIDR:** `0.0.0.0/0` (public) — or your home IP `x.x.x.x/32` to lock
     it to just you
   - **IP Protocol:** TCP
   - **Destination Port Range:** `8765`
4. **Add Ingress Rules** (save).

> Alternative: if your instance uses an **NSG** instead of a Security List, add the
> same rule under **Network Security Groups** and attach it to the VNIC.

### 5.2 OS firewall (handled by the script; manual fallback)
The setup script already does this. If you ever need to redo it:

- **Oracle Linux / firewalld:**
  ```bash
  sudo firewall-cmd --permanent --add-port=8765/tcp && sudo firewall-cmd --reload
  ```
- **Minimal image with raw iptables:**
  ```bash
  sudo iptables -I INPUT -p tcp --dport 8765 -m state --state NEW,ESTABLISHED -j ACCEPT
  sudo netfilter-persistent save 2>/dev/null || sudo bash -c 'iptables-save > /etc/iptables/rules.v4'
  ```
  > Oracle Linux images ship with a **restrictive iptables ruleset** that rejects
  > everything except SSH — this is the #1 reason "the security list is right but
  > the site still won't load". You must open the port at the OS level too.

---

## 6. Environment variables a PUBLIC instance MUST set

These are baked into `deploy/docker-compose.oracle.yml` and `deploy/.env`. The
setup script generates the write key automatically; the rest are pre-tuned.

| Env var | Value to use | Why |
|---|---|---|
| `MARKET_PULSE_WRITE_KEY` | a long random secret (script auto-generates into `deploy/.env`) | **Required.** All write/mutating API calls then need header `X-API-Key: <this>`. Without it, public writes are blocked anyway, but with it *you* can still administer remotely. |
| `DB_PATH` | `/app/data/market_pulse.db` | Pins the DB onto the persistent volume so history survives reboots/rebuilds. |
| `PORT` | `8765` | App listen port (also the published port). |
| `PRICE_SCAN_INTERVAL_SEC` | `180` | Full-universe price scan every 3 min (vs 90s) — respects yfinance rate limits and keeps CPU low. |
| `HOT_SCORE_THRESHOLD` | `42` | Slightly higher hot-list bar → less work/noise. |
| `TZ` | `UTC` | Consistent timestamps. |
| `MARKET_PULSE_CORS_ORIGINS` | *(unset)* | Leave unset — the SPA is same-origin. Only set it (comma-separated exact origins) if a different frontend domain must call the API from a browser. **Never** `*` with credentials. |

> Other scanner intervals (`news_scan_interval_sec`, `quick_price_interval_sec`,
> earnings `scan_interval_sec`, etc.) live in **`config.yaml`**, which the compose
> mounts **read-only**. To slow scanning further, edit `config.yaml` on the VM and
> `docker compose ... restart`.

**Generate a write key manually (if needed):**
```bash
head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; echo
# put it in deploy/.env as: MARKET_PULSE_WRITE_KEY=<value>
```

**Calling a write endpoint from outside afterwards:**
```bash
curl -X POST http://YOUR_PUBLIC_IP:8765/api/<write-endpoint> \
  -H "X-API-Key: <your MARKET_PULSE_WRITE_KEY>" -H "Content-Type: application/json" -d '{...}'
```

---

## 7. Verify it's live

On the VM:
```bash
curl -f http://localhost:8765/api/health && echo "  <- healthy"
docker ps --filter name=market-pulse        # STATUS should say "healthy"
docker logs -f market-pulse                 # watch scanners boot (Ctrl-C to stop)
```

From your laptop / phone (after the §5 ingress rule):
```
http://YOUR_PUBLIC_IP:8765
```
You should see the full dashboard with live updates.

---

## 8. Update the app later

```bash
cd ~/market-pulse
git pull
docker compose -f deploy/docker-compose.oracle.yml --env-file deploy/.env up -d --build
```
Your DB volume (`market_pulse_data`) and `deploy/.env` are untouched, so history
and your write key persist.

Useful ops:
```bash
# restart            (e.g. after editing config.yaml)
docker compose -f deploy/docker-compose.oracle.yml --env-file deploy/.env restart
# stop
docker compose -f deploy/docker-compose.oracle.yml --env-file deploy/.env down
# disk / resource check
df -h ; docker stats --no-stream
```

---

## 9. Cost-avoidance checklist (how you could ever be charged, and how not to)

Everything below stays at **$0** if you follow it. The dangers are about
*exceeding Always Free limits*, which silently spills into paid usage on a PAYG
account.

- ✅ **Shape:** stay on `VM.Standard.A1.Flex` at **≤2 OCPU / ≤12 GB**, or the AMD
  micro. Anything bigger is paid.
- ✅ **Boot volume:** keep ~50 GB. **Never** size a single boot volume near 200 GB
  — that consumes your entire free block-storage allotment; a second instance or
  block volume then becomes paid.
- ✅ **Block storage total ≤ 200 GB** across all boot + block volumes combined.
- ✅ **Outbound data < 10 TB/month.** A scanner + dashboard is far below this; only
  a concern if you proxy big downloads through the box.
- ✅ **Region:** create all resources in your **home region** — block volumes
  created outside the home region are **not** free.
- ✅ **Don't add** a second public IP / extra VNIC / a second load balancer / a
  paid OS image (only "Always Free-eligible" Linux images are free).
- ✅ **Volume backups:** max **5** free; deleting old ones avoids errors (not
  charges, but keeps you tidy).
- ⚠️ **Port 25 / outbound email** is blocked by default on OCI — don't rely on it.
- ⚠️ If you convert to **PAYG** for capacity/anti-reclaim, set a **Budget + alert**
  (Console → Billing → Budgets) at e.g. $1 so any accidental paid usage pings you.

---

## 10. Security posture for a public box (summary)

- **Two firewalls:** OCI Security List/NSG **and** the OS firewall both must allow
  8765. Oracle Linux's restrictive iptables is the common gotcha (§5.2).
- **Write auth:** `MARKET_PULSE_WRITE_KEY` is the auth mechanism — set it (the
  script does). Mutating endpoints reject non-local callers without the matching
  `X-API-Key`. Do **not** set `MARKET_PULSE_ALLOW_UNAUTH_WRITES=1` in production.
- **CORS:** locked to same-origin by default (correct, since this app serves its
  own SPA). Only open `MARKET_PULSE_CORS_ORIGINS` for a real external frontend.
- **Rate limiting:** the app rate-limits expensive endpoints per client IP
  (discover/full-scan/analyze/edge) out of the box; defaults are sane for one free
  instance. Tunable via `MARKET_PULSE_RATE_LIMIT_*` env vars.
- **Lock the source CIDR** to your home IP in the ingress rule if you don't need
  the world to reach it.
- **Optional nicer URL + HTTPS:** put a **Cloudflare Tunnel** in front pointing at
  `http://localhost:8765` — free TLS + DDoS protection, and you can then close the
  8765 ingress entirely (tunnel egresses outbound only).

---

## Sources

- Oracle, *Always Free Resources* (official docs, updated 2026-06-12):
  <https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm>
  — A1 Flex 2 OCPU/12 GB; 1,500 OCPU-hrs + 9,000 GB-hrs/mo; 200 GB block (47 GB min
  boot, 50 GB default); E2.1.Micro 1/8 OCPU/1 GB; 10 TB/mo outbound; idle-reclaim
  thresholds; "out of host capacity" guidance; port-25 block.
- Oracle Cloud free-tier ARM limit reduction to 2 OCPU/12 GB (June 2026):
  <https://blog.easecloud.io/ai-cloud/launch-oracle-cloud-llms-in/>
- Idle reclamation + PAYG exemption discussion:
  <https://community.oracle.com/customerconnect/discussion/671904/reclamation-of-idle-compute-instances>
- Opening ports on Oracle Linux (firewalld/iptables) + OCI ingress:
  <https://oracle-base.com/articles/vm/oracle-cloud-infrastructure-oci-amend-firewall-rules>,
  <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm>
