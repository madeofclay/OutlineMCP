#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Docker Cleanup and Maintenance ===${NC}\n"

# Get initial disk usage
INITIAL_SIZE=$(docker system df --format "{{json .}}" 2>/dev/null | grep -o '"Reclaimable"[^,]*' | cut -d':' -f2 | tr -d ' "B')

echo -e "${YELLOW}[1/3] Removing stopped containers older than 7 days...${NC}"
# Find and remove stopped MCP containers older than 7 days
CUTOFF_TIME=$(date -d "7 days ago" +%s 2>/dev/null || date -v-7d +%s)
REMOVED_COUNT=0

for container in $(docker ps -a --filter "name=mcp-" --filter "status=exited" --quiet 2>/dev/null); do
    CREATED=$(docker inspect "$container" --format='{{.Created}}' 2>/dev/null | xargs -I {} date -d {} +%s 2>/dev/null || date -d "$(docker inspect "$container" --format='{{.Created}}' 2>/dev/null)" +%s 2>/dev/null)

    if [ -n "$CREATED" ] && [ "$CREATED" -lt "$CUTOFF_TIME" ]; then
        echo "  Removing: $container"
        docker rm "$container" 2>/dev/null || true
        ((REMOVED_COUNT++))
    fi
done

if [ $REMOVED_COUNT -eq 0 ]; then
    echo -e "${GREEN}  No old stopped containers found${NC}"
else
    echo -e "${GREEN}  Removed $REMOVED_COUNT container(s)${NC}"
fi

echo ""
echo -e "${YELLOW}[2/3] Removing dangling images...${NC}"
DANGLING_COUNT=$(docker images -f "dangling=true" -q 2>/dev/null | wc -l)

if [ "$DANGLING_COUNT" -gt 0 ]; then
    docker image prune -f > /dev/null 2>&1
    echo -e "${GREEN}  Removed $DANGLING_COUNT dangling image(s)${NC}"
else
    echo -e "${GREEN}  No dangling images found${NC}"
fi

echo ""
echo -e "${YELLOW}[3/3] Cleaning up unused Docker system data...${NC}"
docker system prune -f --filter "label!=keep" > /dev/null 2>&1
echo -e "${GREEN}  System cleanup complete${NC}"

echo ""
echo -e "${BLUE}=== Cleanup Summary ===${NC}"
echo ""
echo "Docker system usage:"
docker system df --format "table {{.Type}}\t{{.Active}}\t{{.Size}}\t{{.Reclaimable}}" 2>/dev/null || echo "  (Unable to retrieve stats)"

echo ""
echo -e "${YELLOW}Current MCP containers:${NC}"
RUNNING=$(docker ps --filter "name=mcp-" --quiet 2>/dev/null | wc -l)
STOPPED=$(docker ps -a --filter "name=mcp-" --filter "status=exited" --quiet 2>/dev/null | wc -l)
echo "  Running: $RUNNING"
echo "  Stopped: $STOPPED"

if [ $((RUNNING + STOPPED)) -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}Container details:${NC}"
    docker ps -a --filter "name=mcp-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
fi

echo ""
echo -e "${GREEN}Cleanup complete! ✓${NC}"
echo ""
echo "To schedule weekly cleanup at 3am on Sundays, add this to crontab:"
echo "  0 3 * * 0 /home/ec2-user/repos/OutlineMCP/cleanup-docker.sh >> /var/log/mcp-cleanup.log 2>&1"
