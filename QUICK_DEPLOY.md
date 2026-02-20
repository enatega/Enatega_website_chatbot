# ⚡ Quick Deployment Steps

## 1️⃣ Update Backend URL (CRITICAL)

Edit `admin/app.js` line 2-4:
```javascript
const API_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000/admin/api'
    : 'https://YOUR-ACTUAL-BACKEND-URL.up.railway.app/admin/api';
    //     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    //     REPLACE THIS WITH YOUR RAILWAY/RENDER URL
```

**Find your backend URL:**
- Railway: Dashboard → Service → Settings → Domains
- Render: Dashboard → Service → URL at top

---

## 2️⃣ Deploy to Netlify

### Via Netlify UI:
1. Go to https://app.netlify.com/
2. Click "Add new site" → "Import an existing project"
3. Select your GitHub repo
4. **Build settings:**
   - Base directory: `admin`
   - Build command: (leave empty)
   - Publish directory: `.`
5. Click "Deploy site"

### Via CLI:
```bash
npm install -g netlify-cli
netlify login
cd admin
netlify deploy --prod
```

---

## 3️⃣ Test It

1. Open Netlify URL
2. Login with:
   - Username: `admin` (from backend .env)
   - Password: `SecurePassword123!` (from backend .env)
3. Test: Create file, Edit file, Delete file, Re-ingest

---

## 🔒 Security (Do This!)

1. **Change admin password** in backend `.env`:
   ```env
   ADMIN_USERNAME=your_username
   ADMIN_PASSWORD=YourStrongPassword123!
   ```

2. **Restart backend** after changing credentials

---

## 🐛 If Something Breaks

**"Connection error":**
- Check backend is running (Railway/Render dashboard)
- Verify API_URL in `admin/app.js` is correct

**"Invalid credentials":**
- Check ADMIN_USERNAME and ADMIN_PASSWORD in backend `.env`

**CORS errors:**
- Backend CORS is already set to allow all origins
- If you restricted it, add your Netlify domain

---

## 📝 What Gets Deployed

✅ **Deployed to Netlify (Frontend):**
- `admin/index.html`
- `admin/app.js`
- `admin/style.css`
- `admin/netlify.toml`

❌ **NOT Deployed (Stays on Railway/Render):**
- `api/` folder (backend)
- `.env` file (secrets)
- `data/` folder (knowledge base)

---

## 🎯 Done!

Your admin panel is now live at: `https://your-site.netlify.app`

Share with team:
- URL: (your Netlify URL)
- Username: (from backend .env)
- Password: (from backend .env)
