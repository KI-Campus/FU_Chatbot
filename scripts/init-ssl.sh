#!/bin/bash
# ============================================================================
# Arena Production SSL Certificate Initialization Script
# ============================================================================
# 
# This script initializes Let's Encrypt SSL certificates for Arena.
# Works for both domain-based and IP-based deployments.
#
# Usage:
#   ./scripts/init-ssl.sh
#
# Prerequisites:
#   - Docker and docker-compose installed
#   - DOMAIN_NAME set in .env.production
#   - CERTBOT_EMAIL set in .env.production
#   - Ports 80 and 443 accessible from internet
#
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Arena SSL Certificate Initialization Script         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]] && ! groups | grep -q docker; then
   echo -e "${RED}⚠️  This script must be run as root or with docker group access${NC}"
   exit 1
fi

# Load environment variables
if [ ! -f ".env.production" ]; then
    echo -e "${RED}❌ Error: .env.production file not found${NC}"
    echo -e "${YELLOW}   Please create .env.production from .env.production.template${NC}"
    exit 1
fi

source .env.production

# Validate required variables
if [ -z "$DOMAIN_NAME" ]; then
    echo -e "${RED}❌ Error: DOMAIN_NAME not set in .env.production${NC}"
    exit 1
fi

if [ -z "$CERTBOT_EMAIL" ]; then
    echo -e "${RED}❌ Error: CERTBOT_EMAIL not set in .env.production${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Environment loaded${NC}"
echo -e "  Domain: ${YELLOW}$DOMAIN_NAME${NC}"
echo -e "  Email:  ${YELLOW}$CERTBOT_EMAIL${NC}"
echo ""

# Check if domain is an IP address
if [[ $DOMAIN_NAME =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${YELLOW}⚠️  DOMAIN_NAME appears to be an IP address${NC}"
    echo -e "${YELLOW}   Let's Encrypt does not support IP-based certificates${NC}"
    echo -e "${YELLOW}   Falling back to self-signed certificate...${NC}"
    echo ""
    
    # Generate self-signed certificate
    mkdir -p ./nginx/ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ./nginx/ssl/privkey.pem \
        -out ./nginx/ssl/fullchain.pem \
        -subj "/C=DE/ST=Berlin/L=Berlin/O=KI-Campus/CN=$DOMAIN_NAME"
    
    # Create directories for certbot structure
    mkdir -p ./certbot/conf/live/arena
    
    # Create symlinks
    ln -sf $(pwd)/nginx/ssl/fullchain.pem ./certbot/conf/live/arena/fullchain.pem
    ln -sf $(pwd)/nginx/ssl/privkey.pem ./certbot/conf/live/arena/privkey.pem
    
    echo -e "${GREEN}✓ Self-signed certificate generated${NC}"
    echo -e "${YELLOW}⚠️  Warning: Browsers will show security warnings${NC}"
    echo ""
else
    echo -e "${BLUE}📡 Checking DNS resolution...${NC}"
    if ! host $DOMAIN_NAME > /dev/null 2>&1; then
        echo -e "${RED}❌ Error: Domain $DOMAIN_NAME does not resolve${NC}"
        echo -e "${YELLOW}   Please ensure DNS A record is configured${NC}"
        exit 1
    fi
    
    RESOLVED_IP=$(host $DOMAIN_NAME | grep "has address" | awk '{print $4}' | head -1)
    echo -e "${GREEN}✓ Domain resolves to: $RESOLVED_IP${NC}"
    echo ""
    
    # Check if nginx is running
    if docker ps | grep -q fu-arena-nginx; then
        echo -e "${YELLOW}⚠️  Nginx is already running, will restart for certificate challenge${NC}"
        docker compose -f docker-compose.prod.yml stop nginx
    fi
    
    # Generate DH parameters if not exists
    if [ ! -f "./nginx/dhparam.pem" ]; then
        echo -e "${BLUE}🔐 Generating Diffie-Hellman parameters (this may take a few minutes)...${NC}"
        openssl dhparam -out ./nginx/dhparam.pem 2048
        echo -e "${GREEN}✓ DH parameters generated${NC}"
    fi
    
    # Start nginx for ACME challenge
    echo -e "${BLUE}🚀 Starting nginx for Let's Encrypt ACME challenge...${NC}"
    docker compose -f docker-compose.prod.yml up -d nginx
    
    # Wait for nginx to be ready
    sleep 5
    
    # Obtain certificate
    echo -e "${BLUE}📜 Requesting SSL certificate from Let's Encrypt...${NC}"
    docker compose -f docker-compose.prod.yml run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email $CERTBOT_EMAIL \
        --agree-tos \
        --no-eff-email \
        --force-renewal \
        -d $DOMAIN_NAME
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ SSL certificate obtained successfully${NC}"
        
        # Create symlink for nginx config
        mkdir -p ./certbot/conf/live/arena
        ln -sf ../$(basename $(ls -dt ./certbot/conf/live/* | head -1))/fullchain.pem ./certbot/conf/live/arena/fullchain.pem
        ln -sf ../$(basename $(ls -dt ./certbot/conf/live/* | head -1))/privkey.pem ./certbot/conf/live/arena/privkey.pem
    else
        echo -e "${RED}❌ Failed to obtain SSL certificate${NC}"
        exit 1
    fi
fi

# Reload nginx
echo -e "${BLUE}🔄 Reloading nginx with new certificate...${NC}"
docker compose -f docker-compose.prod.yml restart nginx

# Wait and test
sleep 3
if docker ps | grep -q fu-arena-nginx; then
    echo -e "${GREEN}✓ Nginx reloaded successfully${NC}"
else
    echo -e "${RED}❌ Nginx failed to start${NC}"
    docker compose -f docker-compose.prod.yml logs nginx
    exit 1
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ SSL Certificate Setup Complete!                   ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Arena is now accessible at:${NC}"
echo -e "  ${GREEN}https://$DOMAIN_NAME${NC}"
echo ""
echo -e "${YELLOW}Note: Certificate will auto-renew every 12 hours via certbot container${NC}"
