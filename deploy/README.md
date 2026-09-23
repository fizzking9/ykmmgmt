# Deployment — Public Access via Alibaba Cloud

The whole application (backend, frontend, PostgreSQL, MCP server) runs in
Docker on the **LAN prod host** (`srx@192.168.10.25`, Ubuntu 24.04). The
Alibaba Cloud ECS server is a **stateless public entry point only**: its
Nginx reverse-proxies traffic through an frp tunnel back to the prod host.

> The cloud server is configured **once** — it never changes with app
> releases. Releasing a new version is purely a pull + restart on the prod
> host, driven over SSH by `scripts/deploy.ps1` from the dev machine.

```
Browser ──HTTP──> Alibaba Cloud ECS
                    │ Nginx :80  ──> 127.0.0.1:7001 (frp tunnel)
                    │           └─> /mcp ──> 127.0.0.1:7002 (frp tunnel, MCP)
                    │ frps :7000  <── tunnel ── frpc (prod host compose stack)
                    ▼
                 Prod host 192.168.10.25 (Docker Compose, Ubuntu)
                    │ frontend (Nginx :80, published on host as :8080)
                    │   └─ proxies /api ──> backend :8000
                    │ backend ──> db (postgres:16)
                    │ mcp_server :8001 (streamable HTTP for AI agents)
```

LAN users can also reach the app directly at `http://192.168.10.25:8080`
(only port 8080 is published on the prod host; everything else stays inside
the compose network).

## Prerequisites

- The prod host (`192.168.10.25`) with Ubuntu 24.04 and the `srx` account
- SSH key auth from the dev machine (no password prompts during deploys)
- One-time: `deploy/.env.prod` and `deploy/frpc.toml` created from their
  `.example` files on the dev machine (they are pushed to the host by the
  deploy script)

## Step 1 — Prod host: install Docker

SSH into the host, then install Docker Engine + the Compose plugin from the
Ubuntu repos, and allow the deploy user to talk to the daemon:

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker srx   # log out/in once for the group to apply
```

Docker Hub is unreachable from this network, so route Hub pulls (e.g.
`postgres:16`) through a mirror in `/etc/docker/daemon.json`:

```json
{ "registry-mirrors": ["https://docker.m.daocloud.io"] }
```

GHCR images (`ghcr.io/fizzking9/...`) are public — no registry login needed on
the host. They do **not** pull reliably from this network, though: the Hub
mirror only covers `docker.io`, so GHCR is reached directly, where this host
(wireless, no proxy) measured 12–109 KB/s and hit `TLS handshake timeout` part
way through a layer. The backend image is now ~900 MB compressed (torch plus the
baked encoder weights), so a plain `compose pull` can take hours or never
finish — see Step 6 for `-LoadLocally`, which relays the same CI-built digests
over the LAN instead.

```bash
sudo systemctl enable --now docker
```

## Step 2 — Dev machine: SSH key access

```powershell
# If you have no key yet:
ssh-keygen -t ed25519
# Install it on the prod host (one-time, password prompt):
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh srx@192.168.10.25 "cat >> ~/.ssh/authorized_keys"
ssh srx@192.168.10.25 "echo ok"   # should print "ok" without a prompt
```

## Step 3 — Cloud server: install frps

SSH into the server, then:

```bash
# Download the latest frp release (amd64; use arm64 for ARM instances)
FRP_VERSION=0.61.2   # check https://github.com/fatedier/frp/releases
curl -LO "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz"
tar xzf "frp_${FRP_VERSION}_linux_amd64.tar.gz"
sudo install -m 755 "frp_${FRP_VERSION}_linux_amd64/frps" /usr/local/bin/frps
```

Create `/etc/frp/frps.toml`:

```toml
bindAddr = "0.0.0.0"
bindPort = 7000
auth.token = "<FRP_TOKEN>"   # same strong random string as deploy/frpc.toml
```

Create `/etc/systemd/system/frps.service`:

```ini
[Unit]
Description=frp server (YKMMgmt tunnel)
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/frps -c /etc/frp/frps.toml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now frps
sudo systemctl status frps   # should be active (running)
```

## Step 4 — Cloud server: Nginx reverse proxy

```bash
sudo apt update && sudo apt install -y nginx   # (or yum install -y nginx)
```

Create `/etc/nginx/conf.d/ykmmgmt.conf`:

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:7001;   # frp tunnel port
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;   # large CSV/Excel imports
        proxy_send_timeout 300s;
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Also add an MCP location to the same server block (one-time — external AI
agents reach the MCP server at `http://<CLOUD_SERVER_IP>/mcp`):

```nginx
    location /mcp {
        proxy_pass http://127.0.0.1:7002;   # frp tunnel port for the MCP server
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_buffering off;                # stream responses straight through
        proxy_read_timeout 300s;            # long-running chart exports
        proxy_send_timeout 300s;
    }
```

## Step 5 — Alibaba Cloud console: security group

Open **only** these inbound ports on the ECS instance's security group:

| Port | Purpose | Source |
|------|---------|--------|
| 22   | SSH administration | your IP / restricted |
| 80   | HTTP public entry | 0.0.0.0/0 |
| 7000 | frps bind (tunnel control) | the prod host's IP / restricted if possible |

Do **not** open 7001 or 7002 — they only need to be reachable from the
server itself (Nginx proxies to 127.0.0.1:7001 / 127.0.0.1:7002). frp's
`remotePort` traffic arrives over the 7000 control connection.

## Step 6 — Deploy

Everything is driven from the dev machine — the deploy script syncs the
compose file and deploy configs to the prod host, pulls the latest images
there, restarts the stack, and health-checks it:

```powershell
.\scripts\deploy.ps1                # the host pulls from GHCR
.\scripts\deploy.ps1 -LoadLocally   # relay the images over the LAN instead
```

`-LoadLocally` exists for the GHCR throughput described in Step 1: this machine
pulls the CI images over its own (faster) link, then `docker save` → `scp` →
`docker load` ships them over the LAN at MB/s instead of KB/s, and compose is
started with `--pull never` so it uses exactly those digests. Either way a
failure in the image-transfer step stops the script before the stack is
restarted, so a stalled download cannot leave production on a half-shipped
image; the previous images keep serving.

Verify the tunnel (from the dev machine):

```powershell
ssh srx@192.168.10.25 "docker logs ykmmgmt-prod-frpc"   # expect: "login to server success"
                                                         #         "start proxy success"
```

Only one machine may hold the tunnel at a time — frps rejects duplicate
proxy names (`ykmmgmt-web` / `ykmmgmt-mcp`). If a second instance logs
`proxy name already used`, make sure no other frpc (e.g. an old stack
elsewhere) is still running.

## Step 7 — End-to-end check

Browse to `http://<CLOUD_SERVER_IP>/` — you should see the YKMMgmt login
page. Log in, upload a small CSV, and confirm it appears in the Data
Browser.

## Step 8 — MCP endpoint for external AI agents

1. Create a service account (a regular user, e.g. an admin named `svc-mcp`)
   via the app's user management UI.
2. Fill in the MCP section of `deploy/.env.prod`
   (`YKM_SERVICE_USERNAME`, `YKM_SERVICE_PASSWORD`, `YKM_MCP_API_KEY` —
   see `deploy/.env.prod.example`), then run `.\scripts\deploy.ps1` again
   so the `mcp_server` service picks up the credentials.
3. Point an MCP client (Claude Desktop / Inspector, streamable HTTP
   transport) at `http://<CLOUD_SERVER_IP>/mcp` with header
   `Authorization: Bearer <YKM_MCP_API_KEY>` and call `export_visualizations`.
   - The result is a compact summary with a **signed download URL per
     file** — hand the URLs to the user; they open in any browser, no
     extra headers needed. Links expire after `YKM_MCP_DOWNLOAD_TTL`
     seconds (default 24 h) and files are pruned afterwards.
   - Set `YKM_MCP_PUBLIC_URL` (e.g. `http://<CLOUD_SERVER_IP>/mcp`) so
     links are absolute; files wait in `YKM_MCP_FILES_DIR`
     (`/exports`, bind-mounted to `~/ykmmgmt/mcp_exports` on the prod host).

Without the API key every request to `/mcp` gets a 401.

## Troubleshooting

- **frpc logs "connect to server error"** — check the security group allows
  port 7000 inbound from the prod host, and that `<FRP_TOKEN>` matches on
  both sides.
- **frpc logs "proxy name already used"** — another frpc still holds the
  tunnel (e.g. an old stack on a different machine); stop it there first.
- **Browser gets 502 from the cloud Nginx** — the tunnel is down: check
  `ssh srx@192.168.10.25 "docker logs ykmmgmt-prod-frpc"` and
  `sudo journalctl -u frps` on the server.
- **App unreachable after a prod host reboot** — the compose stack uses
  `restart: unless-stopped` and Docker is enabled via systemd
  (`systemctl is-enabled docker`), so it comes back on its own.
- **postgres crash-loops with "could not open log file ... Permission
  denied"** — the bind-mounted `~/ykmmgmt/logs/db` must be writable by uid
  999 (the postgres user in the container):
  `sudo chown -R 999:999 ~/ykmmgmt/logs/db`.
- **Long uploads fail with 413** — `client_max_body_size` is set to 50m in
  both Nginx configs; raise it in both places if larger files are needed.

## Later: domain + HTTPS

When a domain is ready: point it at the ECS IP, replace the port-80 server
block with an HTTPS one (`listen 443 ssl` + Let's Encrypt / Alibaba SSL cert),
and set `COOKIE_SECURE=true` in `deploy/.env.prod` so auth cookies are only
sent over HTTPS. Nothing else changes — the tunnel and the prod host stack
stay exactly as they are.
