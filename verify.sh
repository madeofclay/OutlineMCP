#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Outline MCP Proxy System Verification ===${NC}\n"

CHECKS_PASSED=0
CHECKS_FAILED=0

check_service() {
    local service=$1
    local name=$2

    if systemctl is-active --quiet "$service"; then
        echo -e "${GREEN}✓${NC} $name is running"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}✗${NC} $name is NOT running"
        ((CHECKS_FAILED++))
    fi
}

check_command() {
    local cmd=$1
    local name=$2

    if command -v "$cmd" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $name is installed"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}✗${NC} $name is NOT installed"
        ((CHECKS_FAILED++))
    fi
}

check_file() {
    local file=$1
    local name=$2

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $name exists"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}✗${NC} $name does NOT exist"
        ((CHECKS_FAILED++))
    fi
}

# Service checks
echo -e "${BLUE}Service Status:${NC}"
check_service docker "Docker service"
check_service mcp-proxy "MCP Proxy service"
check_service nginx "Nginx service"

echo ""
echo -e "${BLUE}System Tools:${NC}"
check_command docker "Docker CLI"
check_command nginx "Nginx"
check_command python3 "Python 3"
check_command curl "curl"

echo ""
echo -e "${BLUE}Configuration Files:${NC}"
check_file /etc/nginx/conf.d/mcp.conf "Nginx MCP config"
check_file /etc/nginx/.htpasswd "Nginx auth file"
check_file /etc/systemd/system/mcp-proxy.service "Systemd service file"

echo ""
echo -e "${BLUE}Project Files:${NC}"
check_file /home/ec2-user/repos/OutlineMCP/proxy.py "proxy.py"
check_file /home/ec2-user/repos/OutlineMCP/requirements.txt "requirements.txt"
check_file /home/ec2-user/repos/OutlineMCP/.venv "Virtual environment"

# Network checks
echo ""
echo -e "${BLUE}Network Connectivity:${NC}"

# Check if proxy is listening
if netstat -tuln 2>/dev/null | grep -q ":8000 "; then
    echo -e "${GREEN}✓${NC} Proxy listening on port 8000"
    ((CHECKS_PASSED++))
else
    echo -e "${YELLOW}⚠${NC} Proxy not listening on port 8000 (may be starting)"
fi

# Try health check
if timeout 2 curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Proxy health endpoint responsive"
    ((CHECKS_PASSED++))
else
    echo -e "${YELLOW}⚠${NC} Proxy health endpoint not responding (service may be initializing)"
fi

# Check Docker daemon
if docker ps > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Docker daemon is accessible"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}✗${NC} Docker daemon not accessible"
    ((CHECKS_FAILED++))
fi

# Container statistics
echo ""
echo -e "${BLUE}Docker Containers:${NC}"
RUNNING=$(docker ps --filter "name=mcp-" --quiet | wc -l)
TOTAL=$(docker ps -a --filter "name=mcp-" --quiet | wc -l)
echo "  Running: $RUNNING"
echo "  Total (including stopped): $TOTAL"

if [ $TOTAL -gt 0 ]; then
    echo ""
    echo -e "${BLUE}Detailed Container List:${NC}"
    docker ps -a --filter "name=mcp-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
fi

# Memory usage
echo ""
echo -e "${BLUE}System Memory:${NC}"
TOTAL_MEM=$(free -h | awk '/^Mem:/ {print $2}')
USED_MEM=$(free -h | awk '/^Mem:/ {print $3}')
AVAILABLE_MEM=$(free -h | awk '/^Mem:/ {print $7}')
echo "  Total: $TOTAL_MEM | Used: $USED_MEM | Available: $AVAILABLE_MEM"

if command -v docker &> /dev/null; then
    CONTAINER_MEM=$(docker stats --no-stream --filter "name=mcp-" --format "{{.MemUsage}}" 2>/dev/null | awk '{sum+=$1} END {print sum}' RS=" / " || echo "0M")
    echo "  Containers total: $CONTAINER_MEM"
fi

# Summary
echo ""
echo -e "${BLUE}=== Summary ===${NC}"
TOTAL=$((CHECKS_PASSED + CHECKS_FAILED))
echo -e "Checks passed: ${GREEN}$CHECKS_PASSED${NC}/$TOTAL"

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}All checks passed! ✓${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure your domain in /etc/nginx/conf.d/mcp.conf"
    echo "2. Install SSL with: sudo certbot --nginx -d your-domain.com"
    echo "3. View logs: journalctl -u mcp-proxy -f"
    exit 0
else
    echo -e "\n${RED}$CHECKS_FAILED check(s) failed${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "- Service not running: sudo systemctl restart mcp-proxy"
    echo "- Check logs: journalctl -u mcp-proxy -n 50"
    echo "- Nginx config: sudo nginx -t"
    exit 1
fi
