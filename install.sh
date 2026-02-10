#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Outline MCP Proxy Server Installation ===${NC}\n"

# Check if running with sudo
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

PROJECT_DIR="/home/ec2-user/repos/OutlineMCP"
VENV_DIR="$PROJECT_DIR/.venv"

# Step 1: Install Docker
echo -e "${YELLOW}[1/9] Installing Docker...${NC}"
if ! command -v docker &> /dev/null; then
    yum update -y > /dev/null 2>&1
    yum install -y docker > /dev/null 2>&1
    echo -e "${GREEN}✓ Docker installed${NC}"
else
    echo -e "${GREEN}✓ Docker already installed${NC}"
fi

# Step 2: Start Docker service
echo -e "${YELLOW}[2/9] Starting Docker service...${NC}"
systemctl start docker
systemctl enable docker > /dev/null 2>&1
echo -e "${GREEN}✓ Docker service started and enabled${NC}"

# Step 3: Configure Docker group
echo -e "${YELLOW}[3/9] Configuring Docker group for ec2-user...${NC}"
if ! getent group docker > /dev/null; then
    groupadd docker
fi
usermod -aG docker ec2-user
echo -e "${GREEN}✓ Docker group configured${NC}"

# Step 4: Install/verify uv
echo -e "${YELLOW}[4/9] Verifying uv package manager...${NC}"
if ! command -v /home/ec2-user/.local/bin/uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1
    echo -e "${GREEN}✓ uv installed${NC}"
else
    echo -e "${GREEN}✓ uv already installed${NC}"
fi

# Step 5: Create virtual environment
echo -e "${YELLOW}[5/9] Creating Python virtual environment...${NC}"
cd "$PROJECT_DIR"
if [ ! -d "$VENV_DIR" ]; then
    /home/ec2-user/.local/bin/uv venv "$VENV_DIR" > /dev/null 2>&1
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Step 6: Install Python dependencies with uv
echo -e "${YELLOW}[6/9] Installing Python dependencies with uv sync...${NC}"
chown -R ec2-user:ec2-user "$PROJECT_DIR"
cd "$PROJECT_DIR"
sudo -u ec2-user /home/ec2-user/.local/bin/uv lock > /dev/null 2>&1
sudo -u ec2-user /home/ec2-user/.local/bin/uv sync --python "$VENV_DIR/bin/python" > /dev/null 2>&1
echo -e "${GREEN}✓ Dependencies installed with uv sync${NC}"

# Step 7: Create systemd service
echo -e "${YELLOW}[7/9] Creating systemd service...${NC}"
cat > /etc/systemd/system/mcp-proxy.service << 'EOF'
[Unit]
Description=Outline MCP Proxy Server
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/repos/OutlineMCP
ExecStart=/home/ec2-user/repos/OutlineMCP/.venv/bin/uvicorn proxy:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3
Environment="PYTHONUNBUFFERED=1"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable mcp-proxy > /dev/null 2>&1
echo -e "${GREEN}✓ Systemd service created and enabled${NC}"

# Step 8: Create Nginx configuration template (user must integrate manually)
echo -e "${YELLOW}[8/9] Creating Nginx configuration template...${NC}"
cat > /home/ec2-user/repos/OutlineMCP/nginx-location.conf << 'EOF'
# Add this location block to your existing Nginx server configuration
# (inside the HTTPS server block for data-dev.clay.cl)

location /outline/ {
    # Proxy to FastAPI Outline MCP proxy
    proxy_pass http://localhost:8000/;

    # Headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # WebSocket support (required for MCP)
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    # Timeouts for container creation (90 seconds)
    proxy_connect_timeout 90s;
    proxy_send_timeout 90s;
    proxy_read_timeout 90s;

    # Optional: Enable authentication if needed
    # auth_basic "Clay Restricted Content";
    # auth_basic_user_file /etc/nginx/.htpasswd;
}

# Optional: Add stats endpoint with auth
# location /outline/stats {
#     auth_basic "Clay Restricted Content";
#     auth_basic_user_file /etc/nginx/.htpasswd;
#
#     proxy_pass http://localhost:8000/stats;
#     proxy_set_header Host $host;
#     proxy_set_header X-Real-IP $remote_addr;
#     proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#     proxy_set_header X-Forwarded-Proto $scheme;
# }
EOF
chmod 644 /home/ec2-user/repos/OutlineMCP/nginx-location.conf
echo -e "${GREEN}✓ Nginx location template created${NC}"
echo -e "${YELLOW}  Location: /home/ec2-user/repos/OutlineMCP/nginx-location.conf${NC}"
echo -e "${YELLOW}  You must manually add this to /etc/nginx/nginx.conf${NC}"

echo -e "\n${GREEN}=== Installation Complete ===${NC}\n"
echo -e "${YELLOW}Post-installation steps:${NC}"
echo ""
echo "1. READ INTEGRATION GUIDE:"
echo "   cat $PROJECT_DIR/docs/NGINX_INTEGRATION.md"
echo ""
echo "2. CONFIGURE NGINX:"
echo "   ⚠️  IMPORTANT: You MUST manually add the Nginx location block"
echo "   Template: $PROJECT_DIR/nginx-location.conf"
echo ""
echo "   Steps:"
echo "   a) View the template:"
echo "      cat $PROJECT_DIR/nginx-location.conf"
echo ""
echo "   b) Add to /etc/nginx/nginx.conf (in HTTPS server block)"
echo "      sudo nano /etc/nginx/nginx.conf"
echo ""
echo "   c) Test configuration:"
echo "      sudo nginx -t"
echo ""
echo "   d) Reload Nginx:"
echo "      sudo systemctl reload nginx"
echo ""
echo "3. Verify installation:"
echo "   bash verify.sh"
echo ""
echo "4. Test the proxy:"
echo "   curl https://data-dev.clay.cl/outline/health"
echo ""
echo -e "${YELLOW}URL: https://data-dev.clay.cl/outline/${NC}"
echo ""
