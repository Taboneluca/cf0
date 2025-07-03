# CF0 Deployment Guide

This guide covers deploying the CF0 AI Spreadsheet Assistant to production environments.

## Architecture Overview

- **Frontend**: Next.js app → Deploy to Vercel
- **API Gateway**: FastAPI app → Deploy to Railway  
- **Workers**: Python background tasks → Deploy to Railway
- **Database**: PostgreSQL → Supabase (hosted)

## Deployment Status ✅

### Frontend (Vercel)
- ✅ **Configured**: `apps/frontend/vercel.json`
- ✅ **Build Command**: `next build`
- ✅ **Dependencies**: Up-to-date Next.js 15.2.4
- ✅ **Environment**: Production-ready

### API Gateway (Railway)
- ✅ **Configured**: `apps/api-gateway/railway.toml`
- ✅ **Start Command**: `./start.sh` (uvicorn with production settings)
- ✅ **Health Check**: `/health` endpoint available
- ✅ **Dependencies**: Cleaned up - no deprecated packages
- ✅ **Streaming**: Native FastAPI SSE (no LangServe dependency)

### Workers (Railway)
- ✅ **Configured**: `apps/workers/railway.toml`
- ✅ **Start Command**: `python worker.py`
- ✅ **Dependencies**: Minimal, production-ready

### Database (Supabase)
- ✅ **Status**: Active and healthy
- ✅ **Tables**: All schemas properly configured
- ✅ **Auth**: Complete authentication system
- ✅ **RLS**: Row-level security policies in place

## Environment Variables Required

### API Gateway
```bash
# Required
DATABASE_URL=postgresql://...  # From Supabase
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-api03-...
GROQ_API_KEY=gsk_...

# Optional
SENTRY_DSN=https://...
DEBUG_STREAMING=0
DEFAULT_MODEL=openai:gpt-4o-mini
```

### Frontend
```bash
# Required  
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=https://your-api-gateway.railway.app

# Optional
NEXT_PUBLIC_SENTRY_DSN=https://...
```

### Workers
```bash
# Required
DATABASE_URL=postgresql://...  # Same as API Gateway
SENTRY_DSN=https://...  # Optional
```

## Deployment Steps

### 1. Vercel (Frontend)
1. Connect your GitHub repo to Vercel
2. Set root directory to `apps/frontend`
3. Add environment variables in Vercel dashboard
4. Deploy automatically triggers on push to main

### 2. Railway (API Gateway)
1. Create new Railway project
2. Connect GitHub repo 
3. Set root directory to `apps/api-gateway`
4. Add environment variables in Railway dashboard
5. Railway will use `railway.toml` configuration
6. Deploy automatically triggers on push to main

### 3. Railway (Workers)
1. Create another Railway project
2. Connect same GitHub repo
3. Set root directory to `apps/workers`  
4. Add environment variables in Railway dashboard
5. Deploy automatically triggers on push to main

## Recent Cleanup ✨

The codebase has been cleaned up and is production-ready:

- ❌ **Removed**: Deprecated LangServe/LangChain dependencies
- ❌ **Removed**: Complex debug utilities and test scripts
- ❌ **Removed**: Obsolete migration documentation
- ✅ **Updated**: Native FastAPI streaming (more reliable)
- ✅ **Updated**: Clean dependency management
- ✅ **Updated**: Proper Railway configuration files

## Troubleshooting

### Railway Deployment Issues
- Ensure `railway.toml` is in the correct directory
- Check that all environment variables are set
- Verify `/health` endpoint responds with 200 OK
- Check Railway logs for specific error messages

### Health Checks
- API Gateway: `GET /health` should return `{"status": "healthy"}`
- Frontend: Should serve homepage without errors
- Database: Check Supabase dashboard for connection status

### Performance Monitoring
- Use Supabase dashboard for database performance
- Check Railway metrics for API response times
- Monitor Sentry for error tracking (if configured)

## Security Notes

The Supabase database has some minor security recommendations:
- Consider enabling leaked password protection
- Review RLS policies for optimal performance
- Add indexes for frequently queried columns

These are low-priority improvements and don't block production deployment. 