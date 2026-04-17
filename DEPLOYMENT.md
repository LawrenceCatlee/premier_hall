# Vercel Deploy Guide

## Project Architecture

This is a **static React application** with data generated from Python backend scripts.

### Structure
- **Frontend**: React + Vite + TailwindCSS (in `frontend/` directory)
- **Backend**: Python data processing scripts (in `backend/` directory)
- **Data**: Static JSON files generated for frontend consumption

## Deployment Steps

### 1. Prepare Data (Run Once)

```bash
cd backend
python simple_generate.py
```

This generates `frontend/public/data/players.json` with all player data.

### 2. Deploy to Vercel

#### Option A: Via Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy from project root
vercel --prod
```

#### Option B: Via GitHub Integration

1. Push code to GitHub repository
2. Connect repository to Vercel
3. Vercel will automatically build and deploy

### 3. Vercel Configuration

The `vercel.json` file handles:
- Build command: `cd frontend && npm run build`
- Output directory: `frontend/dist`
- Static file serving

## Environment Variables (Optional)

No environment variables required for basic deployment.

## Custom Domain (Optional)

Add custom domain in Vercel dashboard after deployment.

## Data Updates

To update player data:
1. Run backend scripts to generate new data
2. Commit updated `frontend/public/data/players.json`
3. Redeploy (automatic if using GitHub integration)

## Troubleshooting

### Build Issues
- Ensure `frontend/public/data/players.json` exists
- Run `npm install` in frontend directory
- Check Vercel build logs

### Data Issues
- Regenerate data with `python backend/simple_generate.py`
- Verify JSON file format and content

### Performance
- Data is static and cached efficiently
- No server-side processing required
- Fast load times worldwide via Vercel CDN

## Features

- **Static Site**: No server costs, instant scaling
- **Global CDN**: Fast loading worldwide
- **Auto HTTPS**: SSL certificate included
- **Custom Domain**: Easy domain setup
- **Preview Deployments**: Automatic previews for PRs
