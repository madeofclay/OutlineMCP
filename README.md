# Outline MCP Proxy Server

A production-ready HTTP MCP (Model Context Protocol) proxy server for [Outline](https://www.getoutline.com/) running on AWS EC2 with Docker container isolation, automatic session management, and multi-tenancy support.

## 🌟 Features

- **✅ Claude Code Integration**: Native support for `claude mcp add --transport http`
- **✅ Multi-Tenancy**: Each API key gets its own isolated Docker container
- **✅ Session Pooling**: Automatic MCP HTTP session management (transparent to client)
- **✅ Per-User Isolation**: Complete resource isolation between users
- **✅ Auto-Sleep**: Containers automatically stop after 15 minutes of inactivity to save resources
- **✅ HTTPS Support**: Secure communication via Nginx reverse proxy
- **✅ Auto-Cleanup**: Expired sessions removed automatically (every 60 seconds)
- **✅ Health Checks**: Built-in monitoring and diagnostics endpoints
- **✅ Production-Ready**: Systemd integration, comprehensive logging, resource limits

## 🚀 Quick Start

### 1. Get Your API Key

Go to https://app.getoutline.com/settings/tokens and create an API key.

### 2. Add to Claude Code CLI

**Option A: Using Claude Code CLI (Recommended)**

Run this command on your local machine:

```bash
claude mcp add --transport http MCPOutline \
  https://data-dev.clay.cl/outline/mcp \
  --header "X-Outline-API-Key: ol_api_YOUR_TOKEN_HERE"
```

Replace `ol_api_YOUR_TOKEN_HERE` with your actual Outline API key (from step 1).

**What this command does:**
- `claude mcp add` - Registers a new MCP server with Claude Code
- `--transport http` - Uses HTTP/HTTPS for communication (MCP streamable-http protocol)
- `MCPOutline` - Name of the server (you'll see this in `claude mcp list`)
- `https://data-dev.clay.cl/outline/mcp` - URL of the proxy server
- `--header "X-Outline-API-Key: ..."` - Includes your API key in request headers

**Verify it worked:**
```bash
claude mcp list
```

You should see `MCPOutline` listed as **✓ Connected**.

### 3. Option B: Add to Claude Desktop

**For Claude Desktop (manual configuration)**

Edit `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "outline-mcp": {
      "url": "https://data-dev.clay.cl/outline/mcp",
      "transport": {
        "type": "streamableHttp"
      },
      "headers": {
        "X-Outline-API-Key": "ol_api_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

### 3. Option C: Add to Cursor

**For Cursor IDE (manual configuration)**

Cursor uses two configuration options:

**Global Configuration** - Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "outline-mcp": {
      "url": "https://data-dev.clay.cl/outline/mcp",
      "headers": {
        "X-Outline-API-Key": "ol_api_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

**Project-Level Configuration** - Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "outline-mcp": {
      "url": "https://data-dev.clay.cl/outline/mcp",
      "headers": {
        "X-Outline-API-Key": "ol_api_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

**Find Your Configuration:**
```bash
# Open MCP Settings UI in Cursor
# Use the command palette: "View: Open MCP Settings"
```

After adding the configuration, restart Cursor for changes to take effect.

### 4. Verify Connection

**For Claude Code CLI:**
```bash
# List registered MCP servers
claude mcp list

# Should output something like:
# MCPOutline
#   ✓ Connected
#   Type: http
#   URL: https://data-dev.clay.cl/outline/mcp
```

**Health check (from terminal):**
```bash
# Test the proxy server health endpoint
curl -k https://data-dev.clay.cl/outline/health

# Should return:
# {"status":"healthy","version":"1.0.0"}
```

**For Claude Desktop or Cursor:**
Restart the application to apply the configuration changes. Open a conversation and the Outline MCP should be available in the MCP menu.

## 🏗️ Architecture

```
Claude Code (your machine)
    ↓ HTTPS POST
data-dev.clay.cl/outline/mcp
(Nginx reverse proxy)
    ↓ HTTP
localhost:8000
(FastAPI proxy with Session Pooling)
    ↓ HTTP
localhost:4000+ (Docker container - per API key)
    ↓ HTTP
localhost:3000 (MCP Outline server)
```

### What Happens Behind the Scenes

1. **First Request**: Claude Code sends `initialize` request
   - Proxy validates your API key against Outline
   - Proxy creates isolated Docker container for you
   - Container returns a `mcp-session-id`
   - Proxy saves this session ID

2. **Subsequent Requests**: Claude Code sends any MCP request
   - Proxy automatically includes your saved session ID
   - Container accepts the request (valid session)
   - You never need to think about session management

3. **Idle Time**: After 15 minutes without activity
   - Container automatically stops (but isn't deleted)
   - Next request automatically restarts it (2-3 seconds)
   - Saves EC2 resources

## 🔧 Installation

### Prerequisites
- AWS EC2 instance (t3.small or larger recommended)
- Amazon Linux 2023 or Ubuntu 20.04+
- Nginx already configured with HTTPS

### Automated Installation

```bash
cd /home/ec2-user/repos/OutlineMCP
sudo bash install.sh
```

The script will:
- ✓ Install Docker
- ✓ Create Python virtual environment with uv
- ✓ Install dependencies
- ✓ Create systemd service (`mcp-proxy`)
- ✓ Configure Nginx
- ✓ Set up SSL certificate (if needed)

**Typical runtime: 3-5 minutes**

### Manual Setup

```bash
# Clone repository
git clone <repo-url>
cd OutlineMCP

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install uv
uv lock
uv sync

# Run the proxy
python proxy.py
```

## 📊 Performance

| Metric | Value |
|--------|-------|
| **First Request** | 5-10 seconds (pulls image + starts container) |
| **Subsequent Requests** | <100ms (container reuse) |
| **Container Startup** | 2-3 seconds (if stopped) |
| **Memory per Container** | 256MB allocated (auto-stops to 0MB when idle) |
| **Max Users on t3.small** | 5-6 simultaneous active users |

## 🔑 Authentication

Every request requires the `X-Outline-API-Key` header with a valid API key from https://app.getoutline.com/settings/tokens

```bash
curl -H "X-Outline-API-Key: ol_api_..." https://data-dev.clay.cl/outline/health
```

## 📁 Project Structure

```
.
├── proxy.py                 # Main FastAPI proxy server with session pooling
├── install.sh              # Automated installation script
├── verify.sh               # Health check and diagnostics
├── cleanup-docker.sh       # Weekly Docker maintenance
├── nginx-location.conf     # Nginx configuration
├── pyproject.toml          # Python dependencies (uv)
├── uv.lock                 # Dependency lock file
```

## 🔍 Monitoring & Diagnostics

### Check Service Status

```bash
systemctl status mcp-proxy
```

### View Logs

```bash
# Real-time logs
journalctl -u mcp-proxy -f

# Last 50 lines
journalctl -u mcp-proxy -n 50

# Search for errors
journalctl -u mcp-proxy | grep ERROR
```

### Health Check

```bash
# Direct health check
curl http://localhost:8000/health

# Through Nginx
curl https://data-dev.clay.cl/outline/health
```

### Check Containers

```bash
# List all MCP containers
docker ps | grep mcp

# View container logs
docker logs mcp-<container-id>

# Statistics
docker stats
```

### Run Verification Script

```bash
bash verify.sh
```

This will check:
- ✓ Docker is running
- ✓ Nginx is configured
- ✓ FastAPI proxy is responding
- ✓ Container statistics
- ✓ Memory usage

## 🚨 Troubleshooting

### "Failed to connect" Error

**Check 1**: Server is reachable
```bash
curl -k https://data-dev.clay.cl/outline/health
```
If fails → Network/firewall issue

**Check 2**: API key is valid
```bash
curl -X POST https://app.getoutline.com/api/auth.info \
  -H "Authorization: Bearer ol_api_YOUR_TOKEN"
```
If fails → API key expired/invalid

**Check 3**: Claude Code version
```bash
claude --version
# Requires v0.6.0 or newer for HTTP MCP
```

**Check 4**: Service is running
```bash
systemctl status mcp-proxy
journalctl -u mcp-proxy -f
```

### "Invalid API Key" Error

- Go to https://app.getoutline.com/settings/tokens
- Generate a new API key
- Make sure the key starts with `ol_api_`
- Update your Claude configuration

### Connection Timeout

- First request takes 5-10 seconds (pulling image)
- Wait and retry
- Check Docker is pulling: `docker ps`
- View proxy logs: `journalctl -u mcp-proxy -f`

### Container Won't Start

```bash
# View error logs
docker logs mcp-<hash>

# Check available space
docker system df

# Free up space
bash cleanup-docker.sh
```

## 🔐 Security

- **API Key Validation**: Every request validated against Outline API
- **Keys Not Stored**: API keys never written to disk
- **HTTPS Only**: All external communication encrypted
- **Per-User Isolation**: Each API key gets dedicated container
- **Resource Limits**: Each container limited to 256MB RAM, 0.3 CPU
- **No Credential Leakage**: Sessions are server-side only

## 📈 Session Pooling Technical Details

The proxy implements **MCP HTTP Session Pooling** to handle the stateful nature of the Outline MCP protocol:

### Session Lifecycle

1. **Create** (on initialize request)
   - Server returns `mcp-session-id` header
   - Proxy saves it in memory (per API key)

2. **Reuse** (on subsequent requests)
   - Proxy retrieves saved session ID
   - Automatically includes in request headers
   - Server processes request with valid session

3. **Expire** (after 1 hour of inactivity)
   - Automatic cleanup task removes expired sessions
   - Prevents memory leaks

4. **Clean** (every 60 seconds)
   - Background task runs cleanup
   - Removes sessions older than 1 hour

### Configuration

```python
# In proxy.py
MCP_SESSION_TIMEOUT = 60 * 60      # 1 hour
IDLE_TIMEOUT_SECONDS = 15 * 60     # 15 minutes for containers
REQUEST_TIMEOUT = 90               # HTTP request timeout
```

## 🐳 Docker Container Management

Each API key gets its own container:

```bash
# Container naming
mcp-<12-char-sha256-hash>

# Example
mcp-919325da3b4a
mcp-43fe49e38a89
```

### Container Lifecycle

- **Created**: On first request from new API key
- **Running**: Accepts MCP requests
- **Stopped**: After 15 minutes idle (auto-restarted on next request)
- **Removed**: Manually via `cleanup-docker.sh` (containers > 7 days old)

## 📚 Additional Resources

- **Outline MCP**: https://github.com/Vortiago/mcp-outline
- **Claude Code**: https://claude.com/claude-code
- **MCP Specification**: https://modelcontextprotocol.io
- **Outline**: https://www.getoutline.com/

## 📋 Common Commands

```bash
# Restart the proxy service
sudo systemctl restart mcp-proxy

# View service status
systemctl status mcp-proxy

# Real-time logs
journalctl -u mcp-proxy -f

# Check health
curl https://data-dev.clay.cl/outline/health

# List active containers
docker ps | grep mcp

# Run diagnostics
bash verify.sh

# Clean old containers
bash cleanup-docker.sh
```

## 🎯 Multi-Tenancy Example

Two users with different API keys:

| User | API Key Hash | Container | Port | Session ID | Status |
|------|--------------|-----------|------|-----------|--------|
| Alice | mcp-919325... | mcp-919325da3b4a | 4000 | 25acc082... | ✓ Running |
| Bob | mcp-43fe49... | mcp-43fe49e38a89 | 4001 | dbfeac06... | ✓ Running |

- Each user has isolated container
- Each user has independent session
- No cross-contamination of data
- Scales to N users (limited by EC2 instance size)

## 📝 Notes

- Session pooling is **transparent** - you don't need to do anything
- Containers **auto-sleep** after 15 minutes (saves money)
- Sessions **auto-expire** after 1 hour (prevents memory leaks)
- **No client-side code changes** needed for session management
- **Works with existing Claude Code CLI** (v0.6.0+)

## 🤝 Contributing

To update documentation or report issues:

1. Check existing documentation
2. Review `SOLUTION_SUMMARY.md` for technical details
3. Check logs: `journalctl -u mcp-proxy -f`
4. Run diagnostics: `bash verify.sh`

## 📄 License

This project provides a proxy wrapper for [Outline MCP](https://github.com/Vortiago/mcp-outline).

---

**Status**: ✅ Production Ready | **Version**: 1.0.0 | **Updated**: 2026-02-11
