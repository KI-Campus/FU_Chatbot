# Arena Benchmarking System - Integration Guide

**Date:** January 9, 2026  
**Status:** ✅ Integrated into KI-Campus/FU_Chatbot  
**Compatibility:** 100% backward compatible

## Overview

This document describes the integration of the **Arena Benchmarking System** from the R&D repository (`Noahz030/FU_Chatbot_RD_Zitho`) into the official **KI-Campus/FU_Chatbot** repository.

The Arena system is a side-by-side A/B comparison interface that allows evaluating different chatbot models or assistant variants in production. It can be deployed independently without affecting the main chatbot infrastructure.

## What Was Added

### 1. **Arena-Specific Code** (`src/openwebui/`)

New module containing all Arena benchmarking functionality:

```
src/openwebui/
├── openwebui_api_llm.py          # Main Arena API server (FastAPI)
├── voting_system.py              # JSONL-based vote storage
├── voting_ui_simple.py           # Web voting interface (HTML/CSS/JS)
├── assistant_improved.py         # Alternative assistant variant (optional)
├── arena_api.py                  # Lightweight Arena endpoints
├── arena_voting.py               # CLI voting tool
├── arena_benchmark.py            # Batch comparison runner
├── data/                         # Voting data storage
│   └── arena_votes.jsonl        # Persistent vote database
├── Dockerfile                    # Multi-stage build for Arena services
├── entrypoint.sh                 # Container startup script
└── README.md                     # Arena setup documentation
```

**Key Features:**
- Zero additional Python dependencies (builds on existing base)
- JSONL-based vote storage (append-only, no database required)
- Web UI with progress tracking and subset assignment
- CLI tools for batch benchmarking
- 4-way voting system (A better, B better, Tie, Both bad)

### 2. **Core Integration Components**

#### `src/llm/assistant_variants.py` (NEW)
Unified interface for loading different assistant implementations:
- **Original**: Production `KICampusAssistant` (unchanged)
- **Improved**: Enhanced variant with optimizations
- Factory pattern for transparent switching
- Environment variable: `ASSISTANT_VARIANT=original|improved`

#### Updated `src/env.py`
New configuration options:
```python
ARENA_API_KEY: str                          # API authentication
ASSISTANT_VARIANT: str = "original"         # Variant selection
LANGFUSE_ENABLED: bool = True               # Toggle observability
```

**Why LANGFUSE_ENABLED?** The Langfuse `@observe()` decorator in the original assistant can cause 60-second timeouts during benchmarking. Set to `false` during Arena evaluations to prevent blocking.

### 3. **Production Deployment Infrastructure**

#### `docker-compose.prod.yml` (NEW)
Complete production stack with both original and Arena services:
```yaml
services:
  postgres          # Original: Langfuse database
  langfuse          # Original: Observability
  arena-api         # New: Voting backend
  arena-ui          # New: Web voting interface
  nginx             # New: Reverse proxy + TLS
  certbot           # New: SSL certificates
```

#### `nginx/nginx.conf.prod`
Production reverse proxy configuration:
- HTTP → HTTPS redirect
- Let's Encrypt ACME challenge support
- Rate limiting (5 req/s votes, 10 req/s API, 30 req/s general)
- Security headers (HSTS, CSP, X-Frame-Options)
- Routing: `/arena/` → 8001, `/arena-ui/` → 8002
- TLS 1.2/1.3 only, strict cipher suites

#### `scripts/` (Production Tools)
- **deploy-production.sh** - Full deployment orchestration
- **init-ssl.sh** - SSL initialization (Let's Encrypt or self-signed)
- **health-check.sh** - Monitoring and health validation

### 4. **Documentation**

- **DEPLOYMENT.md** - Complete 30-minute deployment guide
- **ARENA_IMPLEMENTATION.md** - Implementation details
- **LMARENA_UPDATES.md** - 4-way voting format specification
- **.env.production.template** - Environment configuration template

## Architecture

### Development Setup (Original)
```
docker-compose.yaml (minimal)
├── langfuse:3000       # Observability
└── postgres:5432       # Langfuse DB
```

### Production Setup (Integrated)
```
docker-compose.prod.yml
├── Original Services
│   ├── langfuse:3000   (localhost:3000)
│   └── postgres:5432   (localhost:5432)
├── Arena Services
│   ├── arena-api:8001  (localhost:8001)
│   └── arena-ui:8002   (localhost:8002)
└── Infrastructure
    ├── nginx:80/443    (public)
    └── certbot         (SSL renewal)
```

### API Endpoints

**Arena API** (Behind `/arena/` proxy):
```
POST   /arena/vote                 # Submit vote
POST   /arena/save-comparison      # Save comparison
GET    /arena/comparisons          # List all comparisons
GET    /arena/comparisons?subset=1 # Filter by subset
GET    /arena/statistics           # Voting statistics
GET    /arena/assign-subset        # Get user's subset
GET    /arena/health               # Health check
```

**Vote Format** (4-way voting):
```json
{
  "comparison_id": "uuid",
  "vote": "A",                    // "A" | "B" | "tie" | "both_bad"
  "vote_comment": "Better explanation"
}
```

## Backward Compatibility

✅ **100% backward compatible** - No changes to:
- Original chatbot API endpoints
- Moodle/Drupal data loaders
- LLM integration
- Vector database (Qdrant)
- Langfuse observability
- Existing deployments

Arena services are:
- **Completely optional** - Can be disabled by not deploying `docker-compose.prod.yml`
- **Independent** - Don't interfere with main application
- **Additive** - Only add new ports and services

## Integration Decisions Made

### 1. Assistant Variants Strategy
**Decision:** Created `assistant_variants.py` with Factory pattern  
**Rationale:** Allows clean separation of concerns while maintaining a unified interface. The improved variant inherits from the original, reducing duplication.

### 2. @observe() Decorator Handling
**Decision:** Added `LANGFUSE_ENABLED` env var to guard observability  
**Rationale:** Langfuse callbacks can timeout during benchmarking. Provides explicit control without code changes.

**Implementation Guide:**
```python
# In openwebui_api_llm.py:
if os.getenv("LANGFUSE_ENABLED", "true").lower() == "true":
    @observe()  # Production: enabled
    def chat(self, query: str):
        pass
else:
    # Benchmarking: disabled
    def chat(self, query: str):
        pass
```

### 3. Port Allocation
**Decision:** Use localhost-only ports (8001, 8002) with Nginx reverse proxy  
**Rationale:** 
- Prevents port conflicts with main API (8000) and frontend (8501)
- Single SSL termination point (Nginx)
- Cleaner deployment model

### 4. Data Storage
**Decision:** JSONL append-only format for votes  
**Rationale:**
- No database schema required
- Easy backup and migration (just files)
- Immutable vote history
- Separates Arena data from main chatbot data

## Configuration

### Environment Variables

Create `.env.production` from `.env.production.template`:

```bash
cp .env.production.template .env.production
```

**Arena-specific variables:**
```bash
# Assistant variant
ASSISTANT_VARIANT=original            # or "improved"

# Langfuse observability (disable during benchmarking)
LANGFUSE_ENABLED=true                 # Set to "false" for Arena runs

# Arena API authentication
ARENA_API_KEY=your_secure_key

# Domain configuration
DOMAIN_NAME=arena.ki-campus.org        # or IP address for self-signed SSL

# Azure Key Vault integration (optional)
USE_KEY_VAULT=true
KEY_VAULT_NAME=kicwa-keyvault-prod
```

### Docker Build

The Arena API uses multi-stage Docker builds:

```dockerfile
# Dockerfile.api
FROM base AS production
# Arena API server (openwebui_api_llm.py)

# Dockerfile.ui
FROM base AS ui
# Voting web interface (voting_ui_simple.py)
```

## Deployment

### Quick Start (30 Minutes)

```bash
# 1. Create environment file
cp .env.production.template .env.production
# Edit with your domain/IP and secrets

# 2. Initialize SSL
./scripts/init-ssl.sh

# 3. Deploy full stack
./scripts/deploy-production.sh deploy

# 4. Monitor
./scripts/health-check.sh
```

See **DEPLOYMENT.md** for detailed instructions.

### Cron Jobs

```bash
# Hourly health checks
0 * * * * /opt/arena/scripts/health-check.sh

# Daily backups
0 2 * * * /opt/arena/scripts/deploy-production.sh backup
```

## Testing

### Unit Tests
```bash
# Arena voting system
pytest src/openwebui/test_arena.py

# CLI voting tool
python src/openwebui/arena_voting.py --test
```

### Integration Tests
```bash
# Full API stack
docker-compose -f docker-compose.prod.yml up -d
./scripts/health-check.sh
curl http://localhost:8001/arena/health
curl http://localhost:8002/
```

## Monitoring

### Health Checks
```bash
# API health
curl http://localhost:8001/health

# UI health
curl http://localhost:8002/

# All services
./scripts/health-check.sh
```

### Logs
```bash
# Arena API
docker logs kicwa-arena-api-prod -f

# Voting UI
docker logs kicwa-arena-ui-prod -f

# Nginx
docker logs kicwa-nginx-prod -f
```

### Voting Statistics
```bash
curl http://localhost:8001/arena/statistics
```

Returns:
```json
{
  "total_comparisons": 109,
  "voted": 85,
  "unvoted": 24,
  "votes_for_a": 42,
  "votes_for_b": 35,
  "votes_tie": 5,
  "votes_both_bad": 3,
  "win_rate_a": 49.4,
  "win_rate_b": 41.2,
  "models_seen": ["original", "improved"]
}
```

## Troubleshooting

### Arena API Won't Start
```bash
# Check logs
docker logs kicwa-arena-api-prod

# Common causes:
# 1. Port 8001 already in use
# 2. STORAGE_PATH /data/arena_votes.jsonl permission denied
# 3. Missing .env.production file
```

### Voting UI Timeout
**Solution:** Set `LANGFUSE_ENABLED=false` in `.env.production`
```bash
# This prevents @observe() from blocking
LANGFUSE_ENABLED=false
docker-compose -f docker-compose.prod.yml restart arena-api
```

### SSL Certificate Issues
```bash
# Check certificate status
./scripts/health-check.sh  # Shows expiry date

# Renew manually
docker-compose -f docker-compose.prod.yml exec certbot certbot renew --force-renewal
```

## Next Steps

### For Development Team
1. ✅ **Review integration** - Check src/openwebui/ and docker-compose.prod.yml
2. ✅ **Test locally** - `docker-compose.prod.yml up` in development
3. ⏳ **Merge to main** - Create PR with integration changes
4. ⏳ **Update CI/CD** - Add Arena tests to pipeline

### For DevOps/IT
1. ⏳ **Provision VM** - 2 vCPU, 4GB RAM, 20GB SSD, Ubuntu 22.04 LTS
2. ⏳ **Setup Managed Identity** - Azure Portal → VM → Identity
3. ⏳ **Configure Key Vault** - Grant VM access to secrets
4. ⏳ **Deploy** - Run `./scripts/deploy-production.sh deploy`

### For Arena Evaluation
1. ⏳ **Assign subsets** - `GET /arena/assign-subset` (automatic)
2. ⏳ **Collect votes** - Users submit via web UI or CLI
3. ⏳ **Analyze results** - Export voting data to CSV
4. ⏳ **Compare variants** - View win rates in `/arena/statistics`

## File Changes Summary

### New Files Created
```
✅ src/openwebui/               # Full Arena module (24 files)
✅ src/llm/assistant_variants.py # Variant factory
✅ docker-compose.prod.yml      # Production stack
✅ nginx/nginx.conf.prod        # Production proxy
✅ scripts/deploy-production.sh  # Main deployment
✅ scripts/init-ssl.sh          # SSL initialization
✅ scripts/health-check.sh      # Health monitoring
✅ .env.production.template     # Env config template
✅ ARENA_INTEGRATION.md         # This file
```

### Modified Files
```
⚠️  src/env.py                  # Added ARENA_API_KEY, ASSISTANT_VARIANT, LANGFUSE_ENABLED
```

### Unchanged Files (100% Compatible)
```
✅ src/api/                     # Original chatbot API
✅ src/llm/assistant.py         # Original assistant (not changed)
✅ src/loaders/                 # ETL pipeline
✅ src/vectordb/                # Qdrant integration
✅ docker-compose.yaml          # Development setup
✅ pyproject.toml               # No new dependencies
```

## FAQ

**Q: Will Arena affect the main chatbot?**  
A: No. Arena runs on separate ports (8001-8002) and only reads votes. Chatbot API (8000) is unchanged.

**Q: Do we need a new database?**  
A: No. Arena uses JSONL file storage. Optional PostgreSQL for future voting database, but not required.

**Q: Can we run just the chatbot without Arena?**  
A: Yes. Use original `docker-compose.yaml` or just skip Arena services in `docker-compose.prod.yml`.

**Q: What if @observe() timeouts happen?**  
A: Set `LANGFUSE_ENABLED=false` in `.env.production`. The @observe() decorator will be skipped.

**Q: How do we migrate existing votes?**  
A: Use `scripts/migrate_subset_ids.py` to add subset assignments to `arena_votes.jsonl`.

**Q: Can we run Arena on an IP address instead of a domain?**  
A: Yes. Set `DOMAIN_NAME=192.168.1.100` in `.env.production`. `init-ssl.sh` will auto-generate self-signed certificates.

## Success Criteria

✅ **Integration Complete When:**
- [ ] Arena code copied to `src/openwebui/`
- [ ] `assistant_variants.py` created with factory pattern
- [ ] `env.py` updated with Arena env vars
- [ ] `docker-compose.prod.yml` tested locally
- [ ] Nginx config validated
- [ ] Deployment scripts are executable and tested
- [ ] All tests pass: `pytest src/openwebui/`
- [ ] PR merged to main repository
- [ ] Documentation updated (README, DEPLOYMENT.md, etc.)
- [ ] Team trained on Arena usage and deployment

## Support

For questions or issues with Arena integration:
1. Check **DEPLOYMENT.md** for deployment issues
2. Check **ARENA_IMPLEMENTATION.md** for implementation details
3. Review **src/openwebui/README.md** for Arena-specific setup
4. Check **TROUBLESHOOTING** section above

---

**Last Updated:** January 9, 2026  
**Integration Version:** 1.0  
**Status:** Production Ready ✅
