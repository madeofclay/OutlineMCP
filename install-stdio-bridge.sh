#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Installing MCP Stdio Bridge ===${NC}\n"

# Check if running with sudo
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

PROJECT_DIR="/home/ec2-user/repos/OutlineMCP"
VENV_DIR="$PROJECT_DIR/.venv"

# Step 1: Create systemd service for stdio bridge
echo -e "${YELLOW}[1/2] Creating systemd service for stdio bridge...${NC}"
cat > /etc/systemd/system/mcp-stdio-bridge.service << 'EOF'
[Unit]
Description=Outline MCP Stdio Bridge Server
After=network.target mcp-proxy.service
Requires=mcp-proxy.service

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/repos/OutlineMCP
ExecStart=/home/ec2-user/repos/OutlineMCP/.venv/bin/python /home/ec2-user/repos/OutlineMCP/stdio_bridge.py
Restart=always
RestartSec=3
Environment="PYTHONUNBUFFERED=1"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mcp-stdio-bridge > /dev/null 2>&1
echo -e "${GREEN}✓ Systemd service created and enabled${NC}"

# Step 2: Start the service
echo -e "${YELLOW}[2/2] Starting stdio bridge service...${NC}"
systemctl start mcp-stdio-bridge
sleep 2
echo -e "${GREEN}✓ Service started${NC}"

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}\n"
echo -e "${YELLOW}The MCP Stdio Bridge is now running on port 9000${NC}"
echo ""
echo "Usage from another machine:"
echo "  nc data-dev.clay.cl 9000"
echo ""
echo "Claude Code configuration (.mcp.json):"
echo "{"
echo '  "mcpServers": {'
echo '    "MCPOutline": {'
echo '      "command": "nc",'
echo '      "args": ["data-dev.clay.cl", "9000"]'
echo '    }'
echo '  }'
echo "}"
echo ""
echo "View logs:"
echo "  journalctl -u mcp-stdio-bridge -f"
echo ""
