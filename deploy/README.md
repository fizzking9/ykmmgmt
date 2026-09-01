# Deployment — Public Access via Alibaba Cloud

The whole application (backend, frontend, PostgreSQL) runs in Docker on the
local machine. The Alibaba Cloud ECS server is a **stateless public entry
point only**: its Nginx reverse-proxies traffic through an frp tunnel back
to the local machine.

> The cloud server is configured **once** — it never changes with app
> releases. Releasing a new version is purely a local pull + restart
> (see `scripts/deploy.ps1` in the repo root README).

```
Browser ──HTTP──> Alibaba Cloud ECS
                    │ Nginx :80  ──> 127.0.0.1:7001 (frp tunnel)
                    │ frps :7000  <── tunnel ── frpc (local compose stack)
                    ▼
                 Local machine (Docker Compose)
                    │ frontend (Nginx :80, published on host as :8080)
                    │   └─ proxies /api ──> backend :8000
                    │ backend ──> db (postgres:16)
```

## Prerequisites

- An Alibaba Cloud ECS instance (any lightweight Linux, e.g. Ubuntu 22.04 / Alibaba Cloud Linux 3) with a public IP
- SSH access to the server
- One-time on the local machine: `deploy/.env.prod` and `deploy/frpc.toml` created from their `.example` files

## Step 1 — Cloud server: install frps

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

## Step 2 — Cloud server: Nginx reverse proxy

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

## Step 3 — Alibaba Cloud console: security group

Open **only** these inbound ports on the ECS instance's security group:

| Port | Purpose | Source |
|------|---------|--------|
| 22   | SSH administration | your IP / restricted |
| 80   | HTTP public entry | 0.0.0.0/0 |
| 7000 | frps bind (tunnel control) | your IP / restricted if possible |

Do **not** open 7001 — it only needs to be reachable from the server itself
(Nginx proxies to 127.0.0.1:7001). frp's `remotePort` traffic arrives over the
7000 control connection.

## Step 4 — Local machine: start the stack

```powershell
# One-time: copy and fill in the configs
copy deploy\.env.prod.example deploy\.env.prod     # then edit
copy deploy\frpc.toml.example deploy\frpc.toml     # then edit (server IP + token)

# Start (frpc is part of the compose stack)
docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod up -d
```

Verify the tunnel:

```powershell
docker logs ykmmgmt-prod-frpc    # expect: "login to server success"
                                 #         "start proxy success"
```

## Step 5 — End-to-end check

Browse to `http://<CLOUD_SERVER_IP>/` — you should see the YKMMgmt login page.
Log in, upload a small CSV, and confirm it appears in the Data Browser.

## Troubleshooting

- **frpc logs "connect to server error"** — check the security group allows
  port 7000 inbound, and that `<FRP_TOKEN>` matches on both sides.
- **Browser gets 502 from the cloud Nginx** — the tunnel is down: check
  `docker logs ykmmgmt-prod-frpc` locally and `sudo journalctl -u frps` on
  the server.
- **App unreachable after a local reboot** — the compose stack uses
  `restart: unless-stopped`; make sure Docker Desktop is configured to start
  on boot (Settings → General → Start Docker Desktop when you sign in).
- **Long uploads fail with 413** — `client_max_body_size` is set to 50m in
  both Nginx configs; raise it in both places if larger files are needed.

## Later: domain + HTTPS

When a domain is ready: point it at the ECS IP, replace the port-80 server
block with an HTTPS one (`listen 443 ssl` + Let's Encrypt / Alibaba SSL cert),
and set `COOKIE_SECURE=true` in `deploy/.env.prod` so auth cookies are only
sent over HTTPS. Nothing else changes — the tunnel and the local stack stay
exactly as they are.
