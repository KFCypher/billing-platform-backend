# Railway Backend Deployment Guide

## 🚀 Deploy to Railway

### Step 1: Push to GitHub (if not already done)

```bash
cd C:\Users\GH\Desktop\billing-platform\billing-platform-backend
git init
git add .
git commit -m "Initial backend setup with Neon database"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/billing-platform-backend.git
git push -u origin main
```

### Step 2: Deploy on Railway

1. Go to https://railway.app/
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your `billing-platform-backend` repository
5. Railway will auto-detect Django and start deploying

### Step 3: Set Environment Variables

In Railway dashboard, go to **Variables** tab and add:

```env
# Required
DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@YOUR_HOST.neon.tech/neondb?sslmode=require
SECRET_KEY=YOUR_64_CHAR_RANDOM_SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=YOUR_APP_NAME.railway.app
PAYSTACK_SECRET_KEY=sk_test_YOUR_KEY

# CORS - Update after frontend deployment
CORS_ALLOWED_ORIGINS=https://your-frontend.vercel.app
CSRF_TRUSTED_ORIGINS=https://your-frontend.vercel.app

# Security (Production)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Platform Settings
PLATFORM_FEE_PERCENTAGE=15.0
PLATFORM_NAME=BillingPlatform
```

### Step 4: Generate SECRET_KEY

Run this locally to generate a secure key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output and paste it as `SECRET_KEY` in Railway.

### Step 5: Get Your Backend URL

After deployment, Railway will give you a URL like:
- `https://YOUR_APP_NAME.railway.app`

Save this URL - you'll need it for the frontend!

### Step 6: Verify Deployment

1. Visit: `https://YOUR_APP_NAME.railway.app/admin/`
2. You should see the Django admin login page
3. Check API: `https://YOUR_APP_NAME.railway.app/api/v1/`

### Step 7: Create Superuser (Admin Access)

In Railway dashboard:
1. Go to your project
2. Click **"Shell"** or **"Terminal"**
3. Run:
   ```bash
   python manage.py createsuperuser
   ```
4. Enter email and password

---

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Railway project created
- [ ] Environment variables set
- [ ] SECRET_KEY generated and added
- [ ] DATABASE_URL from Neon added
- [ ] Deployment successful (check logs)
- [ ] Admin page accessible
- [ ] Superuser created
- [ ] Backend URL saved for frontend

---

## 🔧 Troubleshooting

### If deployment fails:

1. **Check Railway logs** - Look for error messages
2. **Verify DATABASE_URL** - Make sure Neon URL is correct
3. **Check requirements.txt** - All dependencies listed
4. **Migrations** - Railway runs them automatically

### Common Issues:

- **Static files not loading**: Railway runs `collectstatic` automatically
- **Database errors**: Verify Neon DATABASE_URL is correct
- **CORS errors**: Update CORS_ALLOWED_ORIGINS with frontend URL

---

## 📝 Next Steps

After backend is deployed:
1. Save your Railway backend URL
2. Deploy frontend to Vercel
3. Update CORS settings with frontend URL
4. Test the connection

Your backend URL will be:
`https://YOUR_APP_NAME.railway.app`
