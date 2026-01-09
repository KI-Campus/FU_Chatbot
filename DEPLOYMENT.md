# 🚀 Arena Production Deployment Guide

Complete guide for deploying Arena to production VM with public internet access.

## 📋 Prerequisites

### VM Requirements
- **OS**: Ubuntu 22.04 LTS (recommended) or Ubuntu 20.04
- **CPU**: 2 vCPUs minimum
- **RAM**: 4 GB minimum
- **Storage**: 20 GB SSD minimum
- **Public IP**: Required for internet access
- **Ports**: 22 (SSH, admin only), 80 (HTTP), 443 (HTTPS) open to internet

### Software Requirements
- Docker 24.x or later
- Docker Compose v2.x or later
- OpenSSL (for SSL certificates)
- Git (for deployment)

### Access Requirements
- SSH access to production VM
- Azure Key Vault access (Managed Identity on VM)
- Domain name (recommended) OR accept IP-only access

---

## 🎯 Quick Start (30-minute deployment)

### Step 1: Prepare .env.production

```bash
# Copy template
cp .env.production.template .env.production

# Edit with your values
nano .env.production
```

**Required variables:**
```env
# With domain
DOMAIN_NAME=arena.ki-campus.org
CERTBOT_EMAIL=admin@ki-campus.org

# OR with IP only
DOMAIN_NAME=147.213.45.102

# Azure Key Vault (RECOMMENDED)
USE_KEY_VAULT=true
KEY_VAULT_NAME=kicwa-keyvault-prod

# CORS (match your domain/IP)
CORS_ORIGINS=https://arena.ki-campus.org

# Arena API Key (generate with: openssl rand -hex 32)
ARENA_API_KEY=your-secret-key-here
```

### Step 2: Deploy to VM

```bash
# SSH into VM
ssh user@your-vm-ip

# Clone repository
git clone <your-repo-url> /opt/arena
cd /opt/arena

# Copy .env.production to VM (or create directly on VM)
# scp .env.production user@your-vm-ip:/opt/arena/

# Run deployment
./scripts/deploy-production.sh deploy
```

### Step 3: Initialize SSL Certificates

```bash
# For domain-based deployment (Let's Encrypt)
./scripts/init-ssl.sh

# For IP-based deployment (self-signed certificates)
# Script will detect IP and generate self-signed certs automatically
```

### Step 4: Verify Deployment

```bash
# Check service status
./scripts/deploy-production.sh status

# Run health checks
./scripts/health-check.sh

# View logs
./scripts/deploy-production.sh logs
```

### Step 5: Access Arena

**With domain:**
```
https://arena.ki-campus.org
```

**With IP:**
```
https://147.213.45.102
```
(Browser will show SSL warning with self-signed cert - click "Advanced" → "Proceed")

---

## 🔐 Azure Key Vault Setup

### Option A: Managed Identity (Recommended for Production)

```bash
# 1. Enable Managed Identity on VM (Azure Portal)
# VM → Identity → System Assigned → On

# 2. Grant Key Vault access
# Key Vault → Access Policies → Add Access Policy
#   Secret Permissions: Get, List
#   Select Principal: <Your VM Managed Identity>

# 3. Set environment variables
USE_KEY_VAULT=true
KEY_VAULT_NAME=kicwa-keyvault-prod
```

### Option B: .env file (Testing/Staging only)

```bash
# Fill all secrets in .env.production
USE_KEY_VAULT=false
ARENA_API_KEY=...
AZURE_OPENAI_API_KEY=...
QDRANT_API_KEY=...
# etc.
```

### Required Key Vault Secrets

Create these secrets in Azure Key Vault:

```
ARENA-API-KEY
AZURE-OPENAI-ENDPOINT
AZURE-OPENAI-API-KEY
AZURE-OPENAI-GPT4O-DEPLOYMENT-ID
AZURE-OPENAI-GPT35-DEPLOYMENT-ID
QDRANT-URL
QDRANT-API-KEY
DATA-SOURCE-PRODUCTION-MOODLE-URL
DATA-SOURCE-PRODUCTION-MOODLE-TOKEN
```

---

## 📝 Deployment Scripts Reference

### deploy-production.sh

Main deployment script with multiple commands:

```bash
# Full deployment (build + deploy + health check)
./scripts/deploy-production.sh deploy

# Build Docker images only
./scripts/deploy-production.sh build

# Restart services
./scripts/deploy-production.sh restart

# Stop all services
./scripts/deploy-production.sh stop

# Check service status
./scripts/deploy-production.sh status

# View logs (follow mode)
./scripts/deploy-production.sh logs

# Create backup
./scripts/deploy-production.sh backup

# Show rollback instructions
./scripts/deploy-production.sh rollback
```

### init-ssl.sh

SSL certificate initialization:

```bash
# Run once after deployment
./scripts/init-ssl.sh

# Supports:
#   - Let's Encrypt for domains (automatic renewal)
#   - Self-signed certificates for IPs
```

### health-check.sh

Comprehensive health checks:

```bash
# Manual health check
./scripts/health-check.sh

# Setup cron (hourly checks)
crontab -e
# Add: 0 * * * * /opt/arena/scripts/health-check.sh >> /var/log/arena-health.log 2>&1
```

---

## 🔄 Maintenance

### Daily Backups

Backups are created automatically before each deployment in `./backups/`.

Manual backup:
```bash
./scripts/deploy-production.sh backup
```

Restore from backup:
```bash
# List backups
ls -lh ./backups/arena_votes_*.jsonl

# Restore specific backup
docker cp ./backups/arena_votes_20260109_143022.jsonl fu-arena-api:/data/arena_votes.jsonl
docker compose -f docker-compose.prod.yml restart arena-api
```

### Certificate Renewal

**Domain-based (Let's Encrypt):**
- Auto-renewal every 12 hours via certbot container
- No manual intervention needed
- Expires after 90 days if auto-renewal fails

**IP-based (Self-signed):**
- Expires after 365 days
- Re-run `./scripts/init-ssl.sh` to regenerate

### Updating Arena

```bash
# Pull latest code
git pull origin main

# Rebuild and deploy
./scripts/deploy-production.sh deploy

# Previous data is preserved in volumes
```

### Monitoring

Setup cron for automated health checks:

```bash
# Edit crontab
crontab -e

# Add hourly health checks
0 * * * * /opt/arena/scripts/health-check.sh >> /var/log/arena-health.log 2>&1

# Add daily backups (2 AM)
0 2 * * * /opt/arena/scripts/deploy-production.sh backup >> /var/log/arena-backup.log 2>&1
```

View logs:
```bash
# Recent logs
tail -f /var/log/arena-health.log

# Docker logs
docker compose -f docker-compose.prod.yml logs -f arena-api
docker compose -f docker-compose.prod.yml logs -f arena-ui
docker compose -f docker-compose.prod.yml logs -f nginx
```

---

## 🐛 Troubleshooting

### Services won't start

```bash
# Check Docker daemon
systemctl status docker

# Check logs
docker compose -f docker-compose.prod.yml logs

# Check disk space
df -h

# Check ports
netstat -tlnp | grep -E '80|443|8001|8002'
```

### SSL Certificate issues

```bash
# For domain-based deployment
# Check DNS resolution
host arena.ki-campus.org

# Check certbot logs
docker compose -f docker-compose.prod.yml logs certbot

# Re-initialize SSL
./scripts/init-ssl.sh

# For IP-based deployment
# Regenerate self-signed certificate
rm -rf ./nginx/ssl ./certbot/conf/live/arena
./scripts/init-ssl.sh
```

### API health check fails

```bash
# Check API logs
docker logs fu-arena-api

# Check environment variables
docker exec fu-arena-api env | grep -E 'ENVIRONMENT|KEY_VAULT|AZURE|QDRANT'

# Test API directly
curl http://localhost:8001/health

# Test from nginx
curl -k https://localhost/arena/comparisons
```

### Key Vault access issues

```bash
# Check Managed Identity
# Azure Portal → VM → Identity → should show "System assigned: On"

# Check Key Vault access policy
# Azure Portal → Key Vault → Access Policies → check VM identity is listed

# Test from VM
docker exec fu-arena-api python3 -c "
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
cred = DefaultAzureCredential()
client = SecretClient('https://kicwa-keyvault-prod.vault.azure.net/', cred)
print(client.get_secret('ARENA-API-KEY').value[:10] + '...')
"
```

### High resource usage

```bash
# Check container stats
docker stats

# Check logs for errors
docker compose -f docker-compose.prod.yml logs --tail=100

# Restart specific service
docker compose -f docker-compose.prod.yml restart arena-api
```

---

## 📊 Production Checklist

Before going live:

- [ ] VM provisioned with public IP
- [ ] Ports 80, 443 open to internet
- [ ] Port 22 restricted to admin IPs only
- [ ] Domain DNS configured (if using domain)
- [ ] Azure Key Vault secrets created
- [ ] VM Managed Identity configured
- [ ] VM granted Key Vault access
- [ ] `.env.production` created and verified
- [ ] Docker and Docker Compose installed
- [ ] Deployment script executed successfully
- [ ] SSL certificates initialized
- [ ] Health checks passing
- [ ] Arena accessible via HTTPS
- [ ] Voting workflow tested end-to-end
- [ ] Results page accessible
- [ ] CSV export working
- [ ] Cron jobs configured (health checks, backups)
- [ ] Monitoring/alerting setup (optional)

---

## 🆘 Support

For issues:
1. Check logs: `docker compose -f docker-compose.prod.yml logs`
2. Run health check: `./scripts/health-check.sh`
3. Review troubleshooting section above
4. Contact Arena team

---

## 📈 Next Steps

After successful deployment:

1. **Testing**: Invite small group for beta testing
2. **Monitoring**: Setup alerts for downtime/errors
3. **Analytics**: Track usage via results dashboard
4. **Scaling**: Monitor resource usage, scale if needed
5. **Migration**: Consider PostgreSQL migration for 500+ users

---

**Version**: 1.0  
**Last Updated**: January 2026  
**Maintained by**: KI-Campus Arena Team
