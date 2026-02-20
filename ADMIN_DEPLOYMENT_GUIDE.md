# 🚀 Admin Frontend Deployment Guide (Netlify)

## 📋 Overview
This guide helps you safely deploy the Knowledge Base Admin Panel to Netlify while keeping your backend API secure.

---

## 🔒 Security Analysis

### ✅ Safe to Deploy (Frontend)
- `admin/index.html` - Static HTML
- `admin/app.js` - Client-side JavaScript
- `admin/style.css` - Styling
- `admin/netlify.toml` - Netlify config

### ⚠️ NOT Deployed (Backend - Stays on Railway/Render)
- `api/main.py` - FastAPI backend
- `api/admin_kb.py` - Admin API endpoints
- `.env` - Environment variables (NEVER deploy this)

### 🔐 Authentication Flow
- Admin panel uses **HTTP Basic Auth**
- Credentials: `ADMIN_USERNAME` and `ADMIN_PASSWORD` from backend `.env`
- Authentication happens on the **backend API**, not frontend
- Frontend only stores credentials in memory during session

---

## 📝 Pre-Deployment Checklist

### 1. Update API URL in `admin/app.js`

**Current configuration:**
```javascript
const API_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000/admin/api'
    : 'https://enatega-website-chatbot-production.up.railway.app/admin/api';
```

**Action Required:**
Replace the production URL with your actual backend URL:

```javascript
const API_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000/admin/api'
    : 'https://YOUR-BACKEND-URL.up.railway.app/admin/api';
```

**Where to find your backend URL:**
- Railway: Dashboard → Your Service → Settings → Domains
- Render: Dashboard → Your Service → URL at the top

---

## 🚀 Deployment Steps

### Step 1: Prepare Repository
```bash
# Make sure admin folder is committed
git add admin/
git commit -m "Prepare admin panel for Netlify deployment"
git push origin main
```

### Step 2: Deploy to Netlify

#### Option A: Netlify UI (Recommended)
1. Go to [Netlify](https://app.netlify.com/)
2. Click **"Add new site"** → **"Import an existing project"**
3. Connect your GitHub repository
4. Configure build settings:
   - **Base directory:** `admin`
   - **Build command:** (leave empty - it's static HTML)
   - **Publish directory:** `.` (current directory)
5. Click **"Deploy site"**

#### Option B: Netlify CLI
```bash
# Install Netlify CLI
npm install -g netlify-cli

# Login to Netlify
netlify login

# Deploy from admin folder
cd admin
netlify deploy --prod
```

### Step 3: Configure Custom Domain (Optional)
1. In Netlify Dashboard → **Domain settings**
2. Add custom domain: `admin.yourdomain.com`
3. Update DNS records as instructed

---

## 🔧 Backend CORS Configuration

Your backend **already has CORS configured** in `api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ✅ Allows Netlify domain
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**For production security (optional):**
Update to whitelist only your domains:
```python
allow_origins=[
    "https://your-admin.netlify.app",
    "https://admin.yourdomain.com",
    "http://localhost:8080"  # for local testing
],
```

---

## 🧪 Testing Deployment

### 1. Test Login
- Open your Netlify URL: `https://your-site.netlify.app`
- Login with credentials from backend `.env`:
  - Username: `admin`
  - Password: `SecurePassword123!`

### 2. Test Features
- ✅ List files
- ✅ Create new file
- ✅ Edit existing file
- ✅ Delete file
- ✅ Re-ingest to Qdrant
- ✅ View status

### 3. Check Browser Console
- Open DevTools (F12)
- Look for any CORS errors
- Verify API calls go to correct backend URL

---

## 🔐 Security Best Practices

### 1. Change Default Credentials
In your backend `.env`:
```env
ADMIN_USERNAME=your_secure_username
ADMIN_PASSWORD=YourVerySecurePassword123!@#
```

### 2. Use Strong Passwords
- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, symbols
- Don't reuse passwords

### 3. Enable HTTPS Only
- Netlify provides free SSL automatically
- Never access admin panel over HTTP

### 4. Restrict Backend CORS (Production)
Update `api/main.py`:
```python
allow_origins=[
    "https://your-admin.netlify.app",
    "https://yourdomain.com"
]
```

### 5. Monitor Access
Check Railway/Render logs for suspicious activity:
```bash
# Railway CLI
railway logs

# Render Dashboard
# Go to Logs tab
```

---

## 🐛 Troubleshooting

### Issue: "Connection error" on login
**Cause:** Backend URL incorrect or backend not running
**Fix:**
1. Verify backend is running (check Railway/Render dashboard)
2. Check API_URL in `admin/app.js` matches your backend
3. Test backend directly: `https://YOUR-BACKEND/admin/api/status`

### Issue: CORS errors in browser console
**Cause:** Backend CORS not configured for Netlify domain
**Fix:**
1. Add Netlify domain to `allow_origins` in `api/main.py`
2. Redeploy backend

### Issue: 401 Unauthorized
**Cause:** Wrong credentials
**Fix:**
1. Check `ADMIN_USERNAME` and `ADMIN_PASSWORD` in backend `.env`
2. Restart backend after changing credentials

### Issue: Files not loading
**Cause:** Backend `data/clean/` directory missing or empty
**Fix:**
1. Verify files exist in backend: `ls data/clean/`
2. Run pipeline: `./run_pipeline.sh`

---

## 📊 Architecture Diagram

```
┌─────────────────┐
│   User Browser  │
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────┐
│  Netlify CDN    │  ← Admin Frontend (Static HTML/JS/CSS)
│  (Frontend)     │
└────────┬────────┘
         │ HTTPS API Calls
         │ /admin/api/*
         ▼
┌─────────────────┐
│ Railway/Render  │  ← FastAPI Backend
│  (Backend API)  │  ← Authentication (Basic Auth)
└────────┬────────┘  ← File Management
         │           ← Qdrant Integration
         ▼
┌─────────────────┐
│  Qdrant Cloud   │  ← Vector Database
└─────────────────┘
```

---

## 🎯 Post-Deployment

### Update README
Add admin panel URL to your main README:
```markdown
## Admin Panel
Manage knowledge base: https://your-admin.netlify.app
```

### Share with Team
- URL: `https://your-admin.netlify.app`
- Username: (from backend .env)
- Password: (from backend .env)

### Monitor Usage
- Netlify Analytics: Track visits
- Backend Logs: Monitor API calls
- Qdrant Dashboard: Check vector updates

---

## 🔄 Updating Admin Panel

### Method 1: Auto-deploy (Recommended)
Netlify auto-deploys on git push:
```bash
# Make changes to admin files
git add admin/
git commit -m "Update admin panel"
git push origin main
# Netlify deploys automatically
```

### Method 2: Manual deploy
```bash
cd admin
netlify deploy --prod
```

---

## 📞 Support

If you encounter issues:
1. Check browser console (F12)
2. Check backend logs (Railway/Render)
3. Verify all URLs are correct
4. Test backend API directly with curl:
   ```bash
   curl -u admin:SecurePassword123! \
     https://YOUR-BACKEND/admin/api/status
   ```

---

## ✅ Deployment Checklist

- [ ] Updated API_URL in `admin/app.js` with production backend URL
- [ ] Changed default admin credentials in backend `.env`
- [ ] Committed admin folder to git
- [ ] Created Netlify site with correct base directory (`admin`)
- [ ] Tested login with correct credentials
- [ ] Verified all features work (create, edit, delete, re-ingest)
- [ ] Checked browser console for errors
- [ ] Configured custom domain (optional)
- [ ] Updated CORS in backend for production (optional)
- [ ] Documented admin URL for team

---

**🎉 Your admin panel is now live and secure!**
