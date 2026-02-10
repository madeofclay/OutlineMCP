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
echo -e "${YELLOW}[6/9] Installing Python dependencies with uv...${NC}"
chown -R ec2-user:ec2-user "$PROJECT_DIR"
cd "$PROJECT_DIR"
sudo -u ec2-user /home/ec2-user/.local/bin/uv sync --python "$VENV_DIR/bin/python" > /dev/null 2>&1
echo -e "${GREEN}✓ Dependencies installed with uv${NC}"

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

# Step 8: Configure Nginx
echo -e "${YELLOW}[8/9] Configuring Nginx...${NC}"
cat > /etc/nginx/conf.d/mcp.conf << 'EOF'
# Rate limiting zone
limit_req_zone $binary_remote_addr zone=mcp_limit:10m rate=20r/s;

# HTTP redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name _;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS server block
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name DOMAIN_PLACEHOLDER;

    # SSL certificate placeholder (replace with certbot)
    ssl_certificate /etc/ssl/certs/self-signed.crt;
    ssl_certificate_key /etc/ssl/private/self-signed.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Rate limiting
    limit_req zone=mcp_limit burst=40 nodelay;

    # Client timeout for container creation (90 seconds)
    client_body_timeout 90s;
    proxy_connect_timeout 90s;
    proxy_send_timeout 90s;
    proxy_read_timeout 90s;

    # Stats endpoint with basic auth
    location /stats {
        auth_basic "Restricted";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://localhost:8000/stats;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check endpoint (no auth)
    location /health {
        proxy_pass http://localhost:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Main proxy pass with WebSocket support
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Pass through original headers
        proxy_pass_request_headers on;
    }
}
EOF
echo -e "${GREEN}✓ Nginx configured${NC}"

# Step 9: Create self-signed certificate and htpasswd
echo -e "${YELLOW}[9/9] Creating self-signed SSL certificate and auth file...${NC}"

# Create self-signed certificate
mkdir -p /etc/ssl/certs /etc/ssl/private
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/self-signed.key \
    -out /etc/ssl/certs/self-signed.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
    2>/dev/null || true

# Create htpasswd for basic auth (default: admin / password123)
htpasswd -bc /etc/nginx/.htpasswd admin password123 2>/dev/null || \
    echo "admin:$(openssl passwd -apr1 password123)" > /etc/nginx/.htpasswd

chmod 644 /etc/nginx/.htpasswd
echo -e "${GREEN}✓ SSL certificate and auth file created${NC}"

# Verify Nginx configuration
nginx -t > /dev/null 2>&1 && systemctl restart nginx || echo -e "${YELLOW}⚠ Warning: Nginx test failed${NC}"

echo -e "\n${GREEN}=== Installation Complete ===${NC}\n"
echo -e "${YELLOW}Post-installation steps:${NC}"
echo "1. Configure your domain:"
echo "   sed -i 's/DOMAIN_PLACEHOLDER/your-domain.com/g' /etc/nginx/conf.d/mcp.conf"
echo ""
echo "2. Install SSL certificate with certbot:"
echo "   sudo certbot --nginx -d your-domain.com"
echo ""
echo "3. Verify installation:"
echo "   bash verify.sh"
echo ""
echo "4. Check service status:"
echo "   systemctl status mcp-proxy"
echo ""
echo "5. View logs:"
echo "   journalctl -u mcp-proxy -f"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- Update /etc/nginx/.htpasswd with secure credentials:"
echo "  sudo htpasswd /etc/nginx/.htpasswd admin"
echo ""
echo "- Ensure Security Groups allow ports 22, 80, 443"
echo ""
