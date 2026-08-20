# Network Error During Registration - Troubleshooting Guide

## ✅ What We Fixed

- Enhanced error messages to clearly show network issues
- Added timeout configuration (10 seconds)
- Improved error logging for debugging
- Better error handling for different error types

## 🔴 Common Causes of "Network Error"

### 1. **Backend Server Not Running** (Most Common)

**Check:** Is Django running on port 8000?

```bash
# Terminal 1: Start the backend server
cd backend
python manage.py runserver
```

You should see:

```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### 2. **Frontend Server Not Running**

**Check:** Is React/Vite running?

```bash
# Terminal 2: Start the frontend server
cd frontend
npm run dev
```

You should see output showing the frontend URL (usually http://localhost:5173 or similar)

### 3. **Wrong Port Configuration**

**Check:** Verify `api.js` baseURL matches backend port

File: `frontend/src/api.js`

```javascript
const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api", // ✅ Correct
});
```

### 4. **CORS Not Working**

**Check:** Django CORS is enabled (it is in your settings)

File: `backend/config/settings.py` (lines ~126-145)

- `CORS_ALLOW_ALL_ORIGINS = True` ✅
- `corsheaders` in INSTALLED_APPS ✅
- `CorsMiddleware` in MIDDLEWARE ✅

---

## 🛠️ Step-by-Step Troubleshooting

### Step 1: Verify Backend is Healthy

```bash
cd backend
python manage.py check
```

Expected output: `System check identified no issues (0 silenced).`

### Step 2: Start Backend Server

```bash
cd backend
python manage.py runserver
```

Server should start on `http://127.0.0.1:8000`

### Step 3: Test Backend Endpoint Directly

Open browser and go to:

- `http://127.0.0.1:8000/api/auth/register/`

You should see a DRF form or JSON response (not a 404 error)

### Step 4: Start Frontend Server

```bash
cd frontend
npm run dev
```

### Step 5: Check Browser Console

1. Open Chrome DevTools (F12)
2. Go to Console tab
3. Look for error messages starting with "Registration error"
4. Screenshot and share the console error

---

## 📋 Checklist Before Registering

- [ ] Backend server running (`python manage.py runserver`)
- [ ] Django shows "Starting development server at http://127.0.0.1:8000/"
- [ ] Frontend server running (`npm run dev`)
- [ ] No terminal errors in either console
- [ ] Browser console (F12) is open to see detailed errors
- [ ] File `backend/db.sqlite3` exists (database file)

---

## 🔍 If You Still Get Network Error

### Check What the Error Message Says:

**Error: "Backend server is not running on http://127.0.0.1:8000"**

- ❌ Django server is not running
- ✅ Solution: Run `python manage.py runserver` in backend folder

**Error: "Server error (500)"**

- ❌ Backend has a code error
- ✅ Solution: Check Django terminal for error traceback

**Error: "Server error (400)"**

- ❌ Your registration data is invalid
- ✅ Solution: Check form fields, ensure password is 8+ characters

**Error: "A user with this username already exists"**

- ❌ Username is taken
- ✅ Solution: Try a different username

---

## 🎯 Expected Flow

1. Fill registration form:
   - Username (required)
   - Email (required)
   - First Name (optional)
   - Last Name (optional)
   - Password 8+ chars (required)
   - Confirm Password (required)

2. Click "Register"

3. Backend validates data ✅

4. User created in database ✅

5. JWT tokens returned ✅

6. Tokens saved to localStorage ✅

7. Redirected to `/dashboard` ✅

---

## 📝 Debug Command

Open browser console (F12) and manually test:

```javascript
// Check API endpoint
fetch("http://127.0.0.1:8000/api/auth/register/", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    username: "testuser",
    email: "test@example.com",
    password: "testpass123",
    password2: "testpass123",
  }),
})
  .then((r) => r.json())
  .then((d) => console.log(d))
  .catch((e) => console.error(e));
```

---

## 🆘 Still Not Working?

1. **Screenshot the error** from console (F12)
2. **Check Django terminal** for error messages
3. **Verify ports:**
   - Backend: http://127.0.0.1:8000 ✅
   - Frontend: usually http://localhost:5173 ✅
4. **Check for Pillow** (image library): Already installed ✅
5. **Restart both servers** after any code changes

---

## ✅ Success Indicators

When registration works:

- ✅ No error message displayed
- ✅ Redirected to `/dashboard`
- ✅ Can see user data in dashboard
- ✅ Logout works
- ✅ Can log back in with credentials
