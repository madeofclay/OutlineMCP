# Deployment Checklist - Outline MCP Proxy Server

## ✅ Implementation Complete

**All 6 phases have been successfully implemented and validated.**

### What's Ready

- ✅ **proxy.py** (535 lines) - Core FastAPI proxy server
- ✅ **install.sh** (224 lines) - Automated installation script
- ✅ **verify.sh** (157 lines) - System verification script
- ✅ **cleanup-docker.sh** (75 lines) - Docker maintenance
- ✅ **requirements.txt** - Python dependencies
- ✅ **README.md** (776 lines) - Complete documentation
- ✅ **IMPLEMENTATION_SUMMARY.md** - Technical summary

**Total:** 2,273 lines of production-ready code

---

## Pre-Deployment Checklist

### AWS EC2 Setup

- [ ] EC2 instance running (t3.small recommended)
- [ ] Amazon Linux 2023 OS
- [ ] Security Groups configured:
  - [ ] Port 22 (SSH) - your IP only
  - [ ] Port 80 (HTTP) - anywhere (for certbot)
  - [ ] Port 443 (HTTPS) - anywhere
- [ ] Domain name with DNS A record pointing to instance IP
- [ ] ~20GB disk space available

### Pre-Installation

```bash
# Connect to instance
ssh -i your-key.pem ec2-user@your-instance-ip

# Navigate to project
cd /home/ec2-user/repos/OutlineMCP

# Verify all files are present
ls -la *.{py,sh,txt,md}
# Should show: proxy.py, install.sh, verify.sh, cleanup-docker.sh,
#              requirements.txt, README.md, IMPLEMENTATION_SUMMARY.md
```

---

## Installation Steps (Detailed)

### Step 1: Run Installation Script

```bash
sudo bash install.sh
```

**This script will:**
- ✓ Install Docker
- ✓ Configure Docker group
- ✓ Create Python virtual environment (uv)
- ✓ Install Python dependencies
- ✓ Create systemd service
- ✓ Configure Nginx
- ✓ Generate self-signed SSL certificate
- ✓ Create basic auth (.htpasswd)

**Estimated time:** 3-5 minutes

**Expected output:** Green checkmarks and completion message

### Step 2: Configure Your Domain

Replace `DOMAIN_PLACEHOLDER` with your actual domain:

```bash
sudo sed -i 's/DOMAIN_PLACEHOLDER/your-domain.com/g' /etc/nginx/conf.d/mcp.conf

# Verify Nginx configuration
sudo nginx -t
# Should say: successful

# Reload Nginx
sudo systemctl reload nginx
```

### Step 3: Install SSL Certificate

Using Let's Encrypt (recommended and free):

```bash
sudo certbot --nginx -d your-domain.com
```

**Follow the prompts:**
- Enter email address
- Accept terms
- Choose whether to share email (optional)
- Certbot will automatically configure HTTPS

**What happens:**
- Certificate installed
- Auto-renewal configured
- Nginx reloaded automatically

**Verify:**
```bash
curl -I https://your-domain.com/health
# Should return HTTP/2 200
```

### Step 4: Verify Installation

```bash
bash verify.sh
```

**Should see:**
```
✓ Docker service is running
✓ MCP Proxy service is running
✓ Nginx service is running
✓ Proxy listening on port 8000
✓ Proxy health endpoint responsive
✓ Docker daemon is accessible
✓ Proxy health endpoint responsive
... (additional checks)
All checks passed! ✓
```

### Step 5: Update Authentication Credentials

Set secure password for `/stats` endpoint:

```bash
sudo htpasswd /etc/nginx/.htpasswd admin
# Enter new secure password (you will use this for monitoring)
```

---

## Post-Installation Configuration

### Optional: Adjust Container Limits

Edit `/home/ec2-user/repos/OutlineMCP/proxy.py`:

```python
# Line ~125 (adjust as needed)
CONTAINER_MEMORY = "256m"     # Change to "512m" for more RAM per user
CONTAINER_CPU = "0.3"         # Change to "0.5" for more CPU
IDLE_TIMEOUT_SECONDS = 15 * 60  # Change to 30*60 for 30 min idle timeout
```

Then restart:
```bash
sudo systemctl restart mcp-proxy
```

### Optional: Schedule Weekly Cleanup

Add to crontab for automatic cleanup (recommended):

```bash
sudo crontab -e
```

Add this line (runs Sundays at 3am):
```
0 3 * * 0 /home/ec2-user/repos/OutlineMCP/cleanup-docker.sh >> /var/log/mcp-cleanup.log 2>&1
```

### Optional: Configure Log Rotation

Create `/etc/logrotate.d/mcp-proxy`:

```bash
sudo bash -c 'cat > /etc/logrotate.d/mcp-proxy << EOF
/var/log/mcp-cleanup.log {
    weekly
    rotate 4
    compress
    delaycompress
    notifempty
    create 0644 root root
}
EOF'
```

---

## Testing After Installation

### Health Check

```bash
# No authentication required
curl -s https://your-domain.com/health | jq

# Expected response:
{
  "status": "healthy",
  "timestamp": "2026-02-10T19:00:00.000000",
  "containers_tracked": 0,
  "containers_running": 0
}
```

### Monitor Endpoint

```bash
# Requires basic auth (admin / password you set)
curl -s -u admin:password https://your-domain.com/stats | jq

# Expected response:
{
  "timestamp": "2026-02-10T19:00:00.000000",
  "total_containers": 0,
  "running_count": 0,
  "stopped_count": 0,
  "containers": []
}
```

### View Logs

```bash
# Real-time logs
journalctl -u mcp-proxy -f

# Last 50 lines
journalctl -u mcp-proxy -n 50

# Errors only
journalctl -u mcp-proxy -p err
```

### Docker Status

```bash
# List all MCP containers
docker ps -a --filter "name=mcp-"

# Container stats
docker stats --filter "name=mcp-"

# Memory usage
free -h
```

---

## User Configuration

### For Each User

Share these instructions with users who will connect:

**1. Get Outline API Key:**
   - Go to https://app.getoutline.com
   - Click profile → Settings → API tokens
   - Create new API token
   - Copy the full token

**2. Configure Claude Desktop:**

   **macOS/Linux:** `~/.config/Claude/claude_desktop_config.json`

   **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

   Add this block:
   ```json
   {
     "mcpServers": {
       "outline": {
         "url": "https://your-domain.com",
         "transport": {
           "type": "streamableHttp"
         },
         "headers": {
           "X-Outline-API-Key": "outline_api_YOUR_ACTUAL_TOKEN"
         }
       }
     }
   }
   ```

**3. Test Connection:**
   - Restart Claude
   - First request takes 5-10 seconds
   - Subsequent requests are instant

---

## Monitoring (Ongoing)

### Daily Checks

```bash
# Service is running
systemctl is-active mcp-proxy

# Check for errors
journalctl -u mcp-proxy -p err --since "1 hour ago"

# Memory usage
free -h && docker stats --no-stream
```

### Weekly Checks

```bash
# Run verification script
bash verify.sh

# Run cleanup
bash cleanup-docker.sh

# Review stats
curl -s -u admin:password https://your-domain.com/stats | jq
```

### Monthly Tasks

```bash
# Update container image
docker pull ghcr.io/vortiago/mcp-outline:latest
bash cleanup-docker.sh

# Check SSL certificate expiry
sudo certbot certificates

# Review resource usage
du -sh /var/lib/docker/
```

---

## Common Issues & Quick Fixes

| Problem | Solution |
|---------|----------|
| Service won't start | `journalctl -u mcp-proxy -n 50 \| grep -i error` |
| 502 Bad Gateway | `sudo systemctl restart mcp-proxy nginx` |
| SSL certificate error | `sudo certbot renew --dry-run` then `sudo certbot renew` |
| Containers not created | Check API key validation, check Docker daemon |
| Memory full | Run `bash cleanup-docker.sh` or increase instance size |
| Request timeout | Check container resources: `docker stats` |

See README.md for detailed troubleshooting.

---

## Support Resources

### Documentation Files

- **README.md** - Complete user and admin guide (776 lines)
- **IMPLEMENTATION_SUMMARY.md** - Technical architecture (506 lines)
- **DEPLOYMENT_CHECKLIST.md** - This file

### Useful Commands

```bash
# Check everything
bash verify.sh

# View detailed stats
curl -s -u admin:password https://your-domain.com/stats | jq

# Watch logs
journalctl -u mcp-proxy -f

# List containers
docker ps -a --filter "name=mcp-"

# System resources
free -h && docker system df
```

### Troubleshooting

See README.md → Troubleshooting section (page 4-5)

---

## Capacity & Scaling

### Current Configuration (t3.small)

```
Total RAM: 2GB
System usage: ~500MB
Container overhead: 256MB × N
Maximum concurrent: 5-6 active users
```

### Scaling Options

| Instance | RAM | Capacity | Cost |
|----------|-----|----------|------|
| t3.micro | 1GB | 1-2 users | $7-10/mo |
| t3.small | 2GB | 5-6 users | $15-20/mo |
| t3.medium | 4GB | 10-12 users | $30-35/mo |
| t3.large | 8GB | 20-24 users | $60-70/mo |

To scale:
1. Stop instance: `sudo systemctl stop mcp-proxy`
2. Resize instance in AWS console
3. Start instance: `sudo systemctl start mcp-proxy`

---

## Next Steps

### Immediate (Today)

- [ ] Review README.md
- [ ] Run `sudo bash install.sh`
- [ ] Configure domain name
- [ ] Install SSL certificate with certbot
- [ ] Run `bash verify.sh`
- [ ] Test health endpoint

### Short-term (This Week)

- [ ] Update /stats endpoint password
- [ ] Configure user authentication
- [ ] Share configuration with users
- [ ] Test with first user
- [ ] Monitor logs for 24 hours

### Long-term (Ongoing)

- [ ] Monitor resource usage
- [ ] Schedule weekly cleanup
- [ ] Review logs for errors
- [ ] Plan for scaling if needed
- [ ] Keep SSL certificate renewed

---

## Important Notes

### Security

- ✓ API keys validated on every request
- ✓ Keys NOT stored on server
- ✓ HTTPS required (no plaintext)
- ✓ Containers isolated from each other
- ✓ Resource limits enforce container isolation

### Performance

- **First request:** 5-10 seconds (container creation)
- **Running container:** <100ms (direct proxy)
- **Stopped container:** 2-3 seconds (restart)
- **Idle timeout:** 15 minutes (auto-stop to save RAM)

### Maintenance

- **Weekly:** Run `bash cleanup-docker.sh`
- **Weekly:** Run `bash verify.sh`
- **Monthly:** Review `docker system df`
- **Automatic:** SSL certificate renewal via certbot

---

## Quick Reference

### Installation Command
```bash
sudo bash install.sh
```

### Verification Command
```bash
bash verify.sh
```

### View Logs
```bash
journalctl -u mcp-proxy -f
```

### View Stats
```bash
curl -u admin:password https://your-domain.com/stats
```

### Cleanup Command
```bash
bash cleanup-docker.sh
```

### Restart Service
```bash
sudo systemctl restart mcp-proxy
```

---

## Completion Timeline

**Phase 1:** Directory & Scripts - ✅ Complete
**Phase 2:** FastAPI Proxy - ✅ Complete
**Phase 3:** Systemd Service - ✅ Complete
**Phase 4:** Nginx Config - ✅ Complete
**Phase 5:** Documentation - ✅ Complete
**Phase 6:** Testing & Verification - ✅ Complete

**Overall:** ✅ READY FOR DEPLOYMENT

---

**For detailed documentation, refer to: README.md**
**For technical details, refer to: IMPLEMENTATION_SUMMARY.md**
**Questions? Check README.md → Troubleshooting section**

---

**Last Updated:** 2026-02-10
**Status:** Production Ready ✅
