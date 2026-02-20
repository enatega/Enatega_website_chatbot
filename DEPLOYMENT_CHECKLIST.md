# ✅ Deployment Checklist

## Pre-Deployment
- [x] Backend is running on Railway
- [x] Backend URL configured in `admin/app.js`
- [x] Admin credentials set in backend `.env`
- [x] CORS enabled in backend
- [x] Admin folder has all files (index.html, app.js, style.css, netlify.toml)

## Deployment
- [ ] Go to https://app.netlify.com/
- [ ] Click "Add new site" → "Import an existing project"
- [ ] Select GitHub repo: `Enatega_website_chatbot`
- [ ] Set base directory: `admin`
- [ ] Leave build command empty
- [ ] Set publish directory: `.`
- [ ] Click "Deploy site"
- [ ] Wait for deployment (1-2 minutes)

## Testing
- [ ] Open Netlify URL
- [ ] Login with credentials from backend `.env`
- [ ] Verify files list loads
- [ ] Create a test file
- [ ] Edit the test file
- [ ] Delete the test file
- [ ] Check status bar shows correct data
- [ ] Open browser console (F12) - no errors

## Security (Do This!)
- [ ] Change `ADMIN_PASSWORD` in backend `.env`
- [ ] Restart Railway service
- [ ] Test login with new password
- [ ] (Optional) Restrict CORS to Netlify domain only

## Post-Deployment
- [ ] Save Netlify URL
- [ ] Share credentials with team
- [ ] Update project README with admin URL
- [ ] Set up custom domain (optional)
- [ ] Enable Netlify analytics (optional)

## Troubleshooting (If Needed)
- [ ] Check Railway dashboard - service running?
- [ ] Test backend: `curl https://enatega-website-chatbot-production.up.railway.app/healthz`
- [ ] Check browser console for errors
- [ ] Verify API_URL in `admin/app.js` matches Railway URL
- [ ] Check Railway logs for API errors

---

## Quick Commands

**Test backend:**
```bash
curl https://enatega-website-chatbot-production.up.railway.app/healthz
```

**Deploy via CLI:**
```bash
cd admin
netlify deploy --prod
```

**Check Railway logs:**
```bash
railway logs --tail
```

---

## Important URLs

- **Backend API:** https://enatega-website-chatbot-production.up.railway.app
- **Admin API:** https://enatega-website-chatbot-production.up.railway.app/admin/api
- **Netlify Dashboard:** https://app.netlify.com/
- **Railway Dashboard:** https://railway.app/

---

## Default Credentials

**Username:** `admin`
**Password:** `SecurePassword123!`

⚠️ **CHANGE THESE AFTER DEPLOYMENT!**

---

## Support

If you get stuck:
1. Check `DEPLOYMENT_SUMMARY.md` for detailed troubleshooting
2. Check `ADMIN_DEPLOYMENT_GUIDE.md` for full guide
3. Check browser console (F12) for errors
4. Check Railway logs for backend errors

---

**🎯 Goal: Get admin panel live on Netlify in under 5 minutes!**
