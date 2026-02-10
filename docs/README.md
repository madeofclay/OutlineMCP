# Outline MCP Proxy Server

A production-ready proxy server for managing per-user Outline MCP containers with automatic resource optimization and auto-sleep functionality.

**Key Features:**
- 🔐 Per-user Docker container isolation
- 💾 Auto-sleep after 15 minutes idle (saves RAM)
- ⚡ Fast request routing with WebSocket support
- 🔄 Automatic container restart on reactivation
- 📊 Health checks and detailed statistics
- 🛡️ HTTPS with rate limiting
- 🐳 Docker-based deployment with resource limits

## Table of Contents

1. [Overview & Architecture](#overview--architecture)
2. [For Users: Claude Desktop Configuration](#for-users-claude-desktop-configuration)
3. [For Administrators: Installation & Setup](#for-administrators-installation--setup)
4. [Monitoring & Management](#monitoring--management)
5. [Troubleshooting](#troubleshooting)
6. [Maintenance](#maintenance)
7. [Technical Architecture](#technical-architecture)

---

## Overview & Architecture

### What is the Outline MCP Proxy?

This service allows multiple users to connect to a shared Outline MCP server through their own API keys, while maintaining isolated Docker containers for each user. The proxy:

1. **Authenticates** each request using the Outline API
2. **Creates or reuses** a per-user Docker container
3. **Routes** requests to the appropriate container
4. **Auto-stops** idle containers to save memory

### Request Flow Diagram

```
User Request
    ↓
HTTPS (Nginx) → Rate Limiting
    ↓
FastAPI Proxy (port 8000)
    ↓
API Key Validation → Outline API
    ↓
Container Manager (Docker)
    ├─ Running? → Route request
    └─ Stopped? → Restart (2s) → Route request
    └─ Missing? → Create (5-10s) → Route request
    ↓
Container Response
    ↓
Response to User
```

### Resource Model

**Active User (running container):**
- RAM: ~256MB per container
- CPU: 0.3 cores (30%)
- Timeout: 15 minutes idle

**Inactive User (stopped container):**
- RAM: 0MB (container stopped)
- Disk: ~2GB (container image cached)
- Startup: ~2 seconds

**Capacity:** t3.small (2GB RAM) supports ~5-6 active users simultaneously

---

## For Users: Claude Desktop Configuration

### Step 1: Get Your Outline API Key

1. Log in to your Outline workspace at https://app.getoutline.com
2. Click your profile → Settings → API tokens
3. Create a new API token (copy the full token)
4. Keep this token **secret** - it's like a password

### Step 2: Configure Claude Desktop

Edit your Claude Desktop configuration:

**macOS/Linux:**
```bash
~/.config/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Add this configuration:**

```json
{
  "mcpServers": {
    "outline": {
      "url": "https://your-domain.com",
      "transport": {
        "type": "streamableHttp"
      },
      "headers": {
        "X-Outline-API-Key": "outline_api_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

**Replace:**
- `your-domain.com` with the actual proxy server domain
- `outline_api_YOUR_TOKEN_HERE` with your actual API token

### Step 3: Verify Connection

1. Restart Claude
2. Click the ⟨⟩ icon in Claude's toolbar
3. You should see "outline" in the MCP list
4. First request will take 5-10 seconds (creating container)
5. Subsequent requests will be instant

### Expected Behavior

| Scenario | Time | Notes |
|----------|------|-------|
| First request | 5-10s | Container creation + image pull |
| Running container request | Instant | Direct proxy |
| Restarting stopped container | 2-3s | Container restart |
| After 15 min idle | Next request takes 2s | Auto-restart |
| After 7+ days idle | Next request takes 5-10s | Container removed, recreated |

---

## For Administrators: Installation & Setup

### Prerequisites

**AWS EC2 Instance:**
- **Instance Type:** t3.small or larger (minimum 2GB RAM)
- **OS:** Amazon Linux 2023
- **Storage:** 20GB+ (for Docker images)

**Security Groups:**
- Port 22 (SSH): Your IP only
- Port 80 (HTTP): Anywhere (for certbot validation)
- Port 443 (HTTPS): Anywhere (for users)
- Port 8000 (FastAPI): localhost only (internal)

**Domain Name:**
- DNS A record pointing to EC2 instance
- Required for SSL certificate

### Installation

**Step 1: SSH into EC2 instance**

```bash
ssh -i your-key.pem ec2-user@your-instance-ip
```

**Step 2: Clone/navigate to project**

```bash
cd /home/ec2-user/repos/OutlineMCP
```

**Step 3: Run installation script**

```bash
sudo bash install.sh
```

This script will:
- ✓ Install Docker
- ✓ Configure Docker group
- ✓ Create Python virtual environment
- ✓ Install dependencies
- ✓ Create systemd service
- ✓ Configure Nginx
- ✓ Generate self-signed SSL certificate

**Step 4: Configure domain name**

Edit `/etc/nginx/conf.d/mcp.conf`:

```bash
sudo sed -i 's/DOMAIN_PLACEHOLDER/your-domain.com/g' /etc/nginx/conf.d/mcp.conf
sudo nginx -t  # Verify syntax
sudo systemctl reload nginx
```

**Step 5: Install SSL certificate**

Using Let's Encrypt (recommended):

```bash
sudo certbot --nginx -d your-domain.com
```

Or manually:

```bash
sudo certbot certonly --standalone -d your-domain.com
# Then update paths in /etc/nginx/conf.d/mcp.conf
```

**Step 6: Verify installation**

```bash
bash verify.sh
```

Expected output:
```
✓ Docker service is running
✓ MCP Proxy service is running
✓ Nginx service is running
✓ Proxy health endpoint responsive
...
All checks passed! ✓
```

### Post-Installation

**Update htpasswd credentials** (for /stats endpoint):

```bash
sudo htpasswd /etc/nginx/.htpasswd admin
# Enter secure password when prompted
```

**Check service status:**

```bash
systemctl status mcp-proxy
journalctl -u mcp-proxy -f
```

**Test the proxy:**

```bash
# Test health endpoint (no auth)
curl https://your-domain.com/health

# Test stats endpoint (requires auth)
curl -u admin:password https://your-domain.com/stats

# Test with valid API key
curl -H "X-Outline-API-Key: outline_api_..." https://your-domain.com/health
```

---

## Monitoring & Management

### View Service Status

**Service health:**
```bash
systemctl status mcp-proxy
sudo systemctl restart mcp-proxy  # Restart if needed
```

**Real-time logs:**
```bash
journalctl -u mcp-proxy -f
```

**Last 50 log lines:**
```bash
journalctl -u mcp-proxy -n 50
```

### Monitor Containers

**List all containers:**
```bash
docker ps -a --filter "name=mcp-"
```

**Get detailed stats:**
```bash
docker stats --filter "name=mcp-"
```

**Check memory usage:**
```bash
free -h
docker stats --no-stream --filter "name=mcp-"
```

### Health Checks

**Proxy health:**
```bash
curl -s https://your-domain.com/health | jq
```

**Container statistics:**
```bash
curl -s -u admin:password https://your-domain.com/stats | jq
```

**Docker connectivity:**
```bash
docker ps
```

---

## Troubleshooting

### Problem: Container won't start

**Symptoms:** Request returns 503, container exits immediately

**Solution:**
```bash
# Check container logs
docker logs mcp-abc123def456

# Check Docker resources
docker stats

# Verify Outline API key is valid
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://app.getoutline.com/api/auth.info
```

### Problem: Request timeout (>90 seconds)

**Symptoms:** Requests hang or timeout

**Causes:**
- Container creation taking too long
- Insufficient server memory (container evicted)
- Network issues

**Solution:**
```bash
# Check available memory
free -h

# Check system load
top -bn1 | head -20

# Verify container started
docker ps -a | grep mcp-

# Restart service
sudo systemctl restart mcp-proxy
```

### Problem: 502 Bad Gateway

**Symptoms:** "502 Bad Gateway" error from Nginx

**Causes:**
- FastAPI service not running
- Port 8000 not listening
- Nginx configuration error

**Solution:**
```bash
# Check if proxy is running
systemctl is-active mcp-proxy

# Verify port 8000 is listening
netstat -tuln | grep 8000

# Test Nginx configuration
sudo nginx -t

# Restart both services
sudo systemctl restart mcp-proxy nginx
```

### Problem: SSL certificate errors

**Symptoms:** Browser warns "untrusted certificate"

**Causes:**
- Self-signed certificate (normal before certbot)
- Certificate expired
- Wrong domain in certificate

**Solution:**
```bash
# Check certificate validity
openssl x509 -in /etc/ssl/certs/self-signed.crt -noout -dates

# Update with Let's Encrypt
sudo certbot renew
sudo systemctl reload nginx
```

### Problem: Docker image pull fails

**Symptoms:** Container creation fails, "image not found"

**Causes:**
- Network connectivity issue
- Image doesn't exist in registry
- Authentication required

**Solution:**
```bash
# Test Docker network
docker run --rm alpine:latest ping -c 3 8.8.8.8

# Manually pull image
docker pull ghcr.io/vortiago/mcp-outline:latest

# Check image availability
docker images | grep mcp-outline
```

### Problem: Rate limiting blocks requests

**Symptoms:** HTTP 429 Too Many Requests

**Causes:**
- User making >20 requests/second
- Upstream proxy also rate limiting

**Solution:**
```bash
# Check Nginx error log
sudo tail -f /var/log/nginx/error.log

# Temporarily increase limit (test only)
# Edit /etc/nginx/conf.d/mcp.conf:
# Change "limit_req_zone" rate from 20r/s to 50r/s
# Then: sudo systemctl reload nginx
```

---

## Maintenance

### Weekly Cleanup

Remove stopped containers older than 7 days:

```bash
bash cleanup-docker.sh
```

**Automate with cron:**
```bash
sudo crontab -e
# Add this line:
0 3 * * 0 /home/ec2-user/repos/OutlineMCP/cleanup-docker.sh >> /var/log/mcp-cleanup.log 2>&1
```

### Update Container Image

```bash
# Pull latest image
docker pull ghcr.io/vortiago/mcp-outline:latest

# Cleanup old containers and restart
bash cleanup-docker.sh
sudo systemctl restart mcp-proxy
```

### Manual Container Management

```bash
# Stop a specific user's container (if needed)
docker stop mcp-abc123def456

# Remove a specific user's container (for troubleshooting)
docker rm mcp-abc123def456

# Force restart all containers
sudo systemctl restart mcp-proxy
```

### Backup & Restore

**Backup container data:**
```bash
# Containers are stopped and recreated automatically
# No persistent state to backup
# Only Docker volumes would need backup (if used)
```

**Log rotation:**
```bash
# Systemd journal is managed automatically
# Check size:
journalctl --disk-usage

# Vacuum old logs (keep 30 days):
sudo journalctl --vacuum=time=30d
```

### SSL Certificate Renewal

Let's Encrypt certificates auto-renew via certbot:

```bash
# Manual renewal (if needed)
sudo certbot renew --dry-run  # Test
sudo certbot renew            # Actually renew
sudo systemctl reload nginx
```

---

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────┐
│  Claude Desktop (User's Machine)        │
│  • Loads MCP configuration              │
│  • Sends HTTPS requests with API key    │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  Nginx (Reverse Proxy)                  │
│  • HTTPS/TLS termination                │
│  • Rate limiting (20 req/s)             │
│  • Route to /stats (with auth)          │
│  • Route others to FastAPI              │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  FastAPI Proxy (port 8000)              │
│  • Authenticate API key vs Outline      │
│  • Manage container lifecycle           │
│  • Route requests to containers         │
│  • Background cleanup task              │
└─────────────┬──────────┬────────────────┘
              │          │
     ┌────────▼─┐  ┌─────▼────────┐
     │ Docker   │  │ In-Memory    │
     │ Engine   │  │ Registry     │
     └────┬─────┘  └──────────────┘
          │
    ┌─────▴──────────────┬─────────────────┐
    │                    │                 │
┌───▼──┐  ┌───┬──┐  ┌───▼──┐
│mcp-  │  │mcp-   │  │mcp-  │
│abc123│  │def456 │  │xyz789│  ... (per-user containers)
└──────┘  └───┬──┘  └──────┘
              │
        ┌─────▼──────────┐
        │ Outline API    │
        │ app.getoutline │
        └────────────────┘
```

### Container Lifecycle

1. **First Request (5-10s)**
   - Authenticate API key with Outline
   - Calculate container hash from API key
   - Pull image from registry
   - Create Docker container with limits
   - Start container
   - Wait for readiness (2s)
   - Route request

2. **Subsequent Request - Running Container (<100ms)**
   - Authenticate API key
   - Container found in registry + running
   - Update last_used timestamp
   - Route request directly

3. **Request After Idle - Stopped Container (2-3s)**
   - Authenticate API key
   - Container found in registry but stopped
   - Start container
   - Wait for readiness (1s)
   - Route request

4. **Idle Timeout (after 15 min)**
   - Background cleanup task runs every 60s
   - Checks all containers' last_used timestamp
   - Stops containers idle > 15 minutes
   - Container marked as "stopped" in memory
   - Disk space not freed (kept for fast restart)

5. **Auto-Cleanup (after 7+ days)**
   - Weekly cleanup script runs
   - Removes stopped containers > 7 days old
   - Frees disk space
   - Registry entry kept in memory
   - Next request will recreate container

### Resource Limits Per Container

```
Memory: 256MB max
CPU: 0.3 cores (30%)
Restart: unless-stopped (auto-restart on crash)
Idle Timeout: 15 minutes
```

### Network Architecture

- **Port 22:** SSH (admin only)
- **Port 80:** HTTP redirect to HTTPS
- **Port 443:** HTTPS with Nginx reverse proxy
- **Port 8000:** FastAPI (localhost only, internal)
- **Port 3000→4000+:** Container internal ports (mapped externally)

### API Endpoints

**Health Check (no auth):**
```bash
GET /health
Response: {
  "status": "healthy",
  "containers_tracked": 5,
  "containers_running": 2
}
```

**Statistics (requires basic auth):**
```bash
GET /stats
Auth: admin:password
Response: {
  "total_containers": 5,
  "running_count": 2,
  "containers": [...]
}
```

**Main Proxy (authenticated with API key):**
```bash
ANY /{path}
Header: X-Outline-API-Key: outline_api_...
Response: Proxied to container
```

### Auto-Sleep Logic

**Background Task (runs every 60 seconds):**

```python
for each container in registry:
    if (now - last_used) > 15_minutes:
        docker stop container
        mark as "stopped" in registry
```

**Startup Logic:**

```python
if container_exists:
    if container_running:
        route_request()
    elif container_stopped:
        docker start container
        wait(1 second)
        route_request()
else:
    create_container()
    wait(2 seconds)
    route_request()
```

---

## Security Considerations

### API Key Security

- ✓ Keys validated against Outline API on each request
- ✓ Keys NOT stored on server
- ✓ Keys only in-memory for active sessions
- ✓ HTTPS required (plaintext blocked at Nginx level)

### Container Isolation

- ✓ Each user gets isolated container
- ✓ Containers run with unprivileged user
- ✓ Memory limits (256MB max)
- ✓ CPU limits (0.3 cores max)
- ✓ No host network access

### Network Security

- ✓ HTTPS/TLS encryption
- ✓ Rate limiting (20 req/s)
- ✓ Stats endpoint protected (basic auth)
- ✓ Internal FastAPI not exposed

### Best Practices

1. **Keep SSL certificate updated**
   ```bash
   sudo certbot renew
   ```

2. **Update htpasswd regularly**
   ```bash
   sudo htpasswd /etc/nginx/.htpasswd admin
   ```

3. **Monitor resource usage**
   ```bash
   watch -n 5 'docker stats --no-stream | grep mcp-'
   ```

4. **Review logs for suspicious activity**
   ```bash
   journalctl -u mcp-proxy --since "1 hour ago" | grep -i error
   ```

---

## Support & Troubleshooting

### Getting Help

1. **Check logs first:**
   ```bash
   journalctl -u mcp-proxy -n 100
   ```

2. **Verify system health:**
   ```bash
   bash verify.sh
   ```

3. **Common issues:**
   - See [Troubleshooting](#troubleshooting) section above

### Performance Optimization

**t3.micro (1GB RAM):**
- Can support 1-2 active users
- Suitable for testing/development
- Not recommended for production

**t3.small (2GB RAM):**
- Can support 5-6 active users
- Recommended for small teams
- 256MB per container × 6 = 1.5GB max

**t3.medium (4GB RAM):**
- Can support 10-12 active users
- Recommended for larger teams
- Comfortable overhead for system

To increase capacity:
1. Stop the service: `sudo systemctl stop mcp-proxy`
2. Modify container memory in `proxy.py`: Change `CONTAINER_MEMORY = "256m"` to desired value
3. Update EC2 instance type
4. Restart: `sudo systemctl start mcp-proxy`

---

## License & Attribution

Outline MCP Proxy Server
- Proxy implementation: FastAPI + Docker
- Based on Outline API: https://app.getoutline.com
- Container image: ghcr.io/vortiago/mcp-outline:latest

---

**Last Updated:** 2026-02-10
**Version:** 1.0.0
