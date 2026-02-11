# Solution Summary - Claude Code HTTP MCP Integration

## ✅ Problem Solved

**Issue:** Claude Code CLI could not connect to the MCP server with `claude mcp add --transport http`
- Error: `MCPOutline: https://data-dev.clay.cl/outline/mcp (HTTP) - ✗ Failed to connect`

**Root Cause:** The Outline MCP server uses stateful HTTP MCP protocol, requiring clients to reuse the same `mcp-session-id` across multiple requests. Claude Code CLI was creating a new session for each request, causing the server to reject subsequent requests with "Missing session ID" errors.

**Date Fixed:** 2026-02-11

## ✨ Solution Implemented: Session Pooling

The proxy now implements **MCP HTTP Session Pooling** to handle session state transparently.

### Architecture

```
Claude Code on External Machine
    ↓ HTTPS POST with X-Outline-API-Key
data-dev.clay.cl:443 (Nginx reverse proxy)
    ↓ HTTP forward
localhost:8000 (FastAPI proxy with Session Pooling)
    ↓ HTTP + session management
localhost:4000 (Docker container - per user)
    ↓ HTTP (internal)
localhost:3000 (MCP Outline server inside container)
```

### How Session Pooling Works

**1. First Request (initialize)**
```
Claude Code → POST /mcp (initialize request)
    ↓
Proxy validates API key
    ↓
Proxy forwards to container
    ↓
Container responds with mcp-session-id header
    ↓
Proxy SAVES session ID → mcp_sessions[api_key_hash]
    ↓
Proxy returns response to Claude Code
```

**2. Subsequent Requests (resources/list, etc.)**
```
Claude Code → POST /mcp (any request)
    ↓
Proxy RETRIEVES saved session ID
    ↓
Proxy adds header: mcp-session-id: <saved-id>
    ↓
Proxy forwards to container WITH session ID
    ↓
Container accepts request (valid session)
    ↓
Proxy returns response to Claude Code
```

### Code Changes

Modified `/home/ec2-user/repos/OutlineMCP/proxy.py`:

1. **Added SessionInfo dataclass** (lines ~52-60)
   - Stores session_id, api_key_hash, created_at, last_used
   - Includes is_expired() method (1-hour timeout)

2. **Added mcp_sessions registry** (line ~70)
   - Global dict: `api_key_hash → SessionInfo`

3. **Added session management functions** (lines ~100-135)
   - `save_mcp_session()` - Save session ID
   - `get_mcp_session()` - Retrieve if not expired
   - `cleanup_expired_sessions()` - Remove old sessions

4. **Modified proxy_request() function** (lines ~436-530)
   - **On request:** Get and include stored session ID in headers
   - **On response:** Extract and save new session ID from response

5. **Enhanced cleanup task** (lines ~536-580)
   - Now also cleans up expired MCP sessions (every 60 seconds)

### Session Lifecycle

| Event | Timeout | Action |
|-------|---------|--------|
| Session created | - | Saved with timestamp |
| Request received | - | Session marked as last_used |
| Session idle | 1 hour | Automatically removed |
| Container idle | 15 min | Container stopped (auto-restart) |

### Benefits

✅ Claude Code doesn't need to handle sessions - proxy does it transparently
✅ No client-side changes required
✅ Works with existing Claude Code CLI (v0.6.0+)
✅ Automatic session cleanup prevents memory leaks
✅ Per-user isolation (each API key gets own session + container)
✅ Maintains MCP HTTP protocol compliance

## Usage

### Add MCP Server

```bash
claude mcp add --transport http MCPOutline \
  https://data-dev.clay.cl/outline/mcp \
  --header "X-Outline-API-Key: ol_api_YOUR_TOKEN_HERE"
```

### Verify Connection

```bash
# Check if MCP server is listed
claude mcp list

# MCP server should show as "Connected"
```

### How It Appears in Claude Code

```
MCPOutline: https://data-dev.clay.cl/outline/mcp (HTTP) - ✓ Connected
```

## Technical Details

### Configuration

```python
# Session timeout (auto-expire after idle)
MCP_SESSION_TIMEOUT = 60 * 60  # 1 hour

# Container idle timeout
IDLE_TIMEOUT_SECONDS = 15 * 60  # 15 minutes
```

### Session Registry

Sessions are stored per API key hash:
```python
mcp_sessions: Dict[str, SessionInfo] = {
    "mcp-abc123def456": SessionInfo(
        session_id="7db423e0c0bb4e079a8a965a53a0b428",
        api_key_hash="mcp-abc123def456",
        created_at=1707581520.0,
        last_used=1707581530.0
    )
}
```

### Log Examples

```
2026-02-11 01:58:40,795 - proxy - INFO - Pooled new MCP session for mcp-919325da3b4a: e3e17d7590c3430b940b2532630dada8
2026-02-11 01:58:41,939 - proxy - INFO - Pooled new MCP session for mcp-919325da3b4a: e3e17d7590c3430b940b2532630dada8
```

When a new session is extracted from server response, it's saved and reused for subsequent requests from the same API key.

## Testing

### Local Test

```bash
# Request 1: Initialize (creates session)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-Outline-API-Key: ol_api_..." \
  -d '{"jsonrpc":"2.0","method":"initialize",...}'

# Request 2: resources/list (reuses session)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-Outline-API-Key: ol_api_..." \
  -d '{"jsonrpc":"2.0","method":"resources/list",...}'
```

Both requests succeed because proxy manages the session transparently.

## Deployment Verification

✅ **Verified Working (2026-02-11):**
- Claude Code CLI can execute `claude mcp add --transport http`
- Server shows as "Connected"
- Multiple requests from Claude Code work correctly
- Session pooling logs confirm sessions are being saved and reused
- No "Missing session ID" errors

## Files Modified

- `proxy.py` - Session pooling implementation (600+ lines)

## Memory Usage

**Per Session:**
- SessionInfo object: ~200 bytes
- Max sessions: Limited by available memory
- Typical: 1-5 sessions (one per active user)
- Cleanup: Automatic every 60 seconds

**Example:**
- 100 active sessions = ~20KB memory
- Negligible impact on t3.small EC2 instance

## Future Improvements

Potential enhancements (not needed for current functionality):

- WebSocket support for persistent connections
- Session persistence to disk/Redis
- Real-time session monitoring dashboard
- Per-session rate limiting
- Session analytics logging

## Support

For issues:
1. Check logs: `journalctl -u mcp-proxy -f`
2. Verify health: `curl https://data-dev.clay.cl/outline/health`
3. Test MCP: `curl -X POST https://data-dev.clay.cl/outline/mcp ...`

## References

- MCP Outline: https://github.com/Vortiago/mcp-outline
- Claude Code: https://claude.com/claude-code
- MCP Specification: https://modelcontextprotocol.io
