#!/bin/bash
# ============================================================================
# Arena Production Deployment Script
# ============================================================================
# 
# This script handles deployment to production VM.
# 
# Usage:
#   ./scripts/deploy-production.sh [command]
#
# Commands:
#   build      - Build Docker images
#   deploy     - Full deployment (build + deploy + health check)
#   restart    - Restart services
#   stop       - Stop all services
#   status     - Check service status
#   logs       - View logs
#   backup     - Backup arena_votes.jsonl
#   rollback   - Rollback to previous version
#
# Prerequisites:
#   - SSH access to production VM
#   - Docker and docker-compose on VM
#   - .env.production configured
#
# ============================================================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
BACKUP_DIR="./backups"

# Functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Arena Production Deployment                          ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  build      - Build Docker images"
    echo "  deploy     - Full deployment (build + deploy + health check)"
    echo "  restart    - Restart services"
    echo "  stop       - Stop all services"
    echo "  status     - Check service status"
    echo "  logs       - View logs"
    echo "  backup     - Backup arena_votes.jsonl"
    echo "  rollback   - Rollback to previous version"
    echo ""
}

check_prerequisites() {
    echo -e "${BLUE}📋 Checking prerequisites...${NC}"
    
    # Check docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found${NC}"
        exit 1
    fi
    
    # Check docker-compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose not found${NC}"
        exit 1
    fi
    
    # Check env file
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}❌ $ENV_FILE not found${NC}"
        echo -e "${YELLOW}   Create it from .env.production.template${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Prerequisites OK${NC}"
    echo ""
}

build_images() {
    echo -e "${BLUE}🏗️  Building Docker images...${NC}"
    docker compose -f $COMPOSE_FILE build --no-cache
    echo -e "${GREEN}✓ Build complete${NC}"
    echo ""
}

backup_data() {
    echo -e "${BLUE}💾 Creating backup...${NC}"
    
    mkdir -p $BACKUP_DIR
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/arena_votes_$TIMESTAMP.jsonl"
    
    # Backup from running container or volume
    if docker ps | grep -q fu-arena-api; then
        docker cp fu-arena-api:/data/arena_votes.jsonl $BACKUP_FILE 2>/dev/null || true
    else
        # Try to copy from volume
        docker run --rm -v fu_chatbot_rd_zitho_arena_data:/data -v $(pwd)/$BACKUP_DIR:/backup \
            alpine cp /data/arena_votes.jsonl /backup/arena_votes_$TIMESTAMP.jsonl 2>/dev/null || true
    fi
    
    if [ -f "$BACKUP_FILE" ]; then
        echo -e "${GREEN}✓ Backup created: $BACKUP_FILE${NC}"
        
        # Keep only last 7 backups
        ls -t $BACKUP_DIR/arena_votes_*.jsonl | tail -n +8 | xargs -r rm
    else
        echo -e "${YELLOW}⚠️  No data to backup (first deployment?)${NC}"
    fi
    echo ""
}

deploy() {
    print_header
    check_prerequisites
    
    # Backup before deployment
    backup_data
    
    # Build images
    build_images
    
    # Pull any missing base images
    echo -e "${BLUE}📥 Pulling base images...${NC}"
    docker compose -f $COMPOSE_FILE pull --quiet
    echo ""
    
    # Stop existing containers
    echo -e "${BLUE}🛑 Stopping existing containers...${NC}"
    docker compose -f $COMPOSE_FILE down
    echo ""
    
    # Start services
    echo -e "${BLUE}🚀 Starting services...${NC}"
    docker compose -f $COMPOSE_FILE up -d
    echo ""
    
    # Wait for services to be healthy
    echo -e "${BLUE}⏳ Waiting for services to be healthy...${NC}"
    sleep 10
    
    # Health check
    health_check
    
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✅ Deployment Complete!                              ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Show access URL
    source $ENV_FILE
    echo -e "${BLUE}🌐 Arena is now accessible at:${NC}"
    echo -e "   ${GREEN}https://$DOMAIN_NAME${NC}"
    echo ""
}

health_check() {
    echo -e "${BLUE}🏥 Running health checks...${NC}"
    
    source $ENV_FILE
    DOMAIN=${DOMAIN_NAME:-localhost}
    
    # Check API
    if curl -k -sf "http://localhost:8001/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API health check passed${NC}"
    else
        echo -e "${RED}✗ API health check failed${NC}"
        docker compose -f $COMPOSE_FILE logs --tail=20 arena-api
        exit 1
    fi
    
    # Check UI
    if curl -k -sf "http://localhost:8002/" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ UI health check passed${NC}"
    else
        echo -e "${RED}✗ UI health check failed${NC}"
        docker compose -f $COMPOSE_FILE logs --tail=20 arena-ui
        exit 1
    fi
    
    # Check Nginx (if running)
    if docker ps | grep -q fu-arena-nginx; then
        if curl -k -sf "https://localhost/" > /dev/null 2>&1 || curl -k -sf "http://localhost/" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Nginx health check passed${NC}"
        else
            echo -e "${YELLOW}⚠️  Nginx check failed (SSL might not be configured yet)${NC}"
        fi
    fi
    
    echo ""
}

show_status() {
    echo -e "${BLUE}📊 Service Status:${NC}"
    echo ""
    docker compose -f $COMPOSE_FILE ps
    echo ""
    
    echo -e "${BLUE}💾 Volume Status:${NC}"
    docker volume ls | grep arena
    echo ""
}

show_logs() {
    echo -e "${BLUE}📜 Recent logs (last 50 lines):${NC}"
    echo ""
    docker compose -f $COMPOSE_FILE logs --tail=50 --follow
}

restart_services() {
    echo -e "${BLUE}🔄 Restarting services...${NC}"
    docker compose -f $COMPOSE_FILE restart
    sleep 5
    health_check
    echo -e "${GREEN}✓ Services restarted${NC}"
}

stop_services() {
    echo -e "${BLUE}🛑 Stopping services...${NC}"
    docker compose -f $COMPOSE_FILE down
    echo -e "${GREEN}✓ Services stopped${NC}"
}

rollback() {
    echo -e "${YELLOW}⚠️  Rollback functionality${NC}"
    echo ""
    echo "Available backups:"
    ls -lh $BACKUP_DIR/arena_votes_*.jsonl 2>/dev/null || echo "No backups found"
    echo ""
    echo "To rollback, restore a backup file manually:"
    echo "  docker cp BACKUP_FILE fu-arena-api:/data/arena_votes.jsonl"
    echo "  docker compose -f $COMPOSE_FILE restart arena-api"
}

# Main
case "${1:-}" in
    build)
        build_images
        ;;
    deploy)
        deploy
        ;;
    restart)
        restart_services
        ;;
    stop)
        stop_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    backup)
        backup_data
        ;;
    rollback)
        rollback
        ;;
    *)
        print_usage
        exit 1
        ;;
esac
