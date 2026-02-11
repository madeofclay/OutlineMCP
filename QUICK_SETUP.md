# Quick Setup - Claude Code HTTP MCP

## Step 1: Get Your API Key

Go to https://app.getoutline.com/settings/tokens and get an API key. It looks like:
```
ol_api_i3bEwWghaMxrE9FV78wNDNrgF3of9cEgJGFwsk
```

## Step 2: Add to Claude Code CLI

Run this command on your local machine:

```bash
claude mcp add --transport http OutlineMCP \
  https://data-dev.clay.cl/outline/mcp \
  --header "X-Outline-API-Key: ol_api_YOUR_TOKEN_HERE"
```

Replace `ol_api_YOUR_TOKEN_HERE` with your actual API key.

## Step 3: Or Add to Claude Desktop

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

Replace `ol_api_YOUR_TOKEN_HERE` with your actual API key.

## Step 4: Test Connection

```bash
# Test health check
curl -k https://data-dev.clay.cl/outline/health

# Test MCP endpoint
curl -X POST https://data-dev.clay.cl/outline/mcp \
  -H "Content-Type: application/json" \
  -H "X-Outline-API-Key: ol_api_YOUR_TOKEN_HERE" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

Expected response: Server-Sent Events with JSON data

## Issues?

- **Can't reach server**: Check `curl -k https://data-dev.clay.cl/outline/health`
- **Invalid API key**: Generate new one at https://app.getoutline.com/settings/tokens
- **Connection timeout**: Service might be starting, wait 2-3 seconds and retry
- **See logs**: `journalctl -u mcp-proxy -f` on EC2

## Architecture

```
Your Local Machine (Claude)
         ↓ HTTPS
    data-dev.clay.cl:443
    (Nginx proxy)
         ↓ HTTP
    EC2 FastAPI (localhost:8000)
         ↓ HTTP
    Docker Container (user-specific)
         ↓ HTTP
    MCP Outline Server (port 3000)
```

Each API key gets its own isolated Docker container. Containers auto-sleep after 15 minutes of inactivity to save resources.
