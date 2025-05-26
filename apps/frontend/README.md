# cf0 Frontend

## Deployment Issues

### Vercel Preview vs Production Issue

If your deployments are going to preview instead of production, follow these steps:

1. **Check Vercel Dashboard**
   - Go to your project settings in Vercel
   - Under "Git", ensure the production branch is set to `main` (not `master`)
   - Verify the repository is correctly connected

2. **Domain Configuration**
   - In "Domains" section, ensure `cf0.ai` is set as the production domain
   - Remove any conflicting domain configurations

3. **Environment Variables**
   - Ensure all production environment variables are set
   - Check that `NODE_ENV` is automatically set to `production` for production deployments

4. **Force Production Deployment**
   ```bash
   # From the Vercel CLI
   vercel --prod
   ```

5. **Branch Protection**
   - Ensure the main branch is set as the production branch in both GitHub and Vercel
   - Check if there are any branch protection rules affecting deployment

## Development

```bash
npm run dev
```

## Build

```bash
npm run build
```

## Environment Variables

- `NEXT_PUBLIC_SUPABASE_URL`: Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`: Supabase anonymous key  
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key (for admin functions)
- `NEXT_PUBLIC_SITE_URL`: Site URL for development (auto-detected in production)

## Known Issues Fixed

1. **Waitlist rejected users** - Can now re-join the waitlist
2. **Auth invite conflicts** - Better cleanup of existing auth users
3. **Favicon not showing** - Updated with proper 64x64 size and cache busting
4. **Production URLs** - Fixed all routes to use correct production URL (cf0.ai) 