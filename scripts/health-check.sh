#!/bin/bash
# ============================================================================
# Arena Health Check Script
# ============================================================================
# 
# This script checks the health of all Arena services.
# Can be run manually or via cron for monitoring.
#
# Usage:
#   ./scripts/health-check.sh
#
# Exit codes:
#   0 - All services healthy
#   1 - One or more services unhealthy
#
# Recommended cron (hourly checks):
#   0 * * * * /path/to/arena/scripts/health-check.sh >> /var/log/arena-health.log 2>&1
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Starting health check..."

# Load environment
if [ -f ".env.production" ]; then
    source .env.production
fi

DOMAIN=${DOMAIN_NAME:-localhost}
ALL_HEALTHY=true

# Check Docker daemon
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker daemon not running${NC}"
    exit 1
fi

# Check Arena API
echo -n "Checking Arena API... "
if curl -sf -m 5 "http://localhost:8001/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    ALL_HEALTHY=false
fi

# Check Arena UI
echo -n "Checking Arena UI... "
if curl -sf -m 5 "http://localhost:8002/" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    ALL_HEALTHY=false
fi

# Check Nginx
echo -n "Checking Nginx... "
if docker ps | grep -q fu-arena-nginx; then
    if curl -sfk -m 5 "https://localhost/" > /dev/null 2>&1 || curl -sf -m 5 "http://localhost/" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ALL_HEALTHY=false
    fi
else
    echo -e "${YELLOW}Not running${NC}"
fi

# Check Certbot (if domain is configured)
if [[ ! $DOMAIN =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -n "Checking SSL Certificate... "
    CERT_PATH="./certbot/conf/live/$DOMAIN/fullchain.pem"
    if [ -f "$CERT_PATH" ]; then
        EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_PATH" | cut -d= -f2)
        EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$EXPIRY" +%s 2>/dev/null)
        NOW_EPOCH=$(date +%s)
        DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))
        
        if [ $DAYS_LEFT -lt 30 ]; then
            echo -e "${YELLOW}⚠️  Expires in $DAYS_LEFT days${NC}"
        else
            echo -e "${GREEN}✓ ($DAYS_LEFT days remaining)${NC}"
        fi
    else
        echo -e "${YELLOW}Not found${NC}"
    fi
fi

# Check disk space
echo -n "Checking disk space... "
DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 90 ]; then
    echo -e "${RED}✗ ${DISK_USAGE}% used${NC}"
    ALL_HEALTHY=false
elif [ $DISK_USAGE -gt 80 ]; then
    echo -e "${YELLOW}⚠️  ${DISK_USAGE}% used${NC}"
else
    echo -e "${GREEN}✓ ${DISK_USAGE}% used${NC}"
fi

# Check container resource usage
echo ""
echo "Container resource usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
    $(docker ps --filter name=fu-arena --format "{{.ID}}")

echo ""
if [ "$ALL_HEALTHY" = true ]; then
    echo -e "${GREEN}✓ All services healthy${NC}"
    exit 0
else
    echo -e "${RED}✗ Some services unhealthy${NC}"
    exit 1
fi
