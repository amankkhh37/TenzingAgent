# 🔧 TROUBLESHOOTING: Scanner Not Finding Leads

## The Problem You Experienced

You saw one of these issues:
1. ❌ Dashboard loaded at :8503 instead of :8501
2. ❌ Adding FB group but scanner found "No group URLs configured"
3. ❌ Scanner timeout when trying to access Facebook

## What Was Wrong

### Issue 1: Port Mismatch (✅ FIXED)
**Cause:** Old Streamlit processes were still running  
**Fix:** Killed old processes, fresh start uses correct port

### Issue 2: Scanner Not Seeing Database Groups (✅ FIXED)
**Cause:** SQLAlchemy database session closed prematurely  
**Fixes Applied:**
- Fixed `_scan_single_group()` to extract `group_id` immediately
- Removed reference to `group` object after session closes
- Updated all references to use `group_id` variable instead

### Issue 3: Facebook Authentication Timeout (✅ FIXED)
**Cause:** You were never logged into Facebook  
**Fix:** Use the new `facebook_login.py` script to authenticate

## Quick Fix (Do This Now)

### Step 1: One-Time Facebook Login

```bash
cd /Users/amangupta/Desktop/TravelAgent
source venv/bin/activate
python facebook_login.py
```

**What happens:**
- Chrome browser opens
- You log in to Facebook
- Session is saved automatically
- Type "done" when finished

### Step 2: Kill Old Processes

```bash
# Kill any old scanner/worker/streamlit
pkill -f "scanner.py"
pkill -f "comment_worker.py"
pkill -f "streamlit"
```

### Step 3: Restart Everything

```bash
cd /Users/amangupta/Desktop/TravelAgent
source venv/bin/activate

# Terminal 1: Start Scanner
python scanner.py &

# Terminal 2: Start Comment Worker  
python comment_worker.py &

# Terminal 3: Start Dashboard
streamlit run app.py
```

### Step 4: Add Your Group in Dashboard

1. Open http://localhost:8501
2. Sidebar → "Add Group" section
3. Paste your Facebook group URL
4. Click "Add Facebook Group"
5. Scanner will automatically find it and start scanning!

---

## Common Facebook Group URLs

**Format:** `https://www.facebook.com/groups/YOUR_GROUP_ID/`

**Examples:**
- `https://www.facebook.com/groups/123456789/`
- `https://www.facebook.com/groups/travel.to.sikkim/`

**How to find:**
1. Go to your group on Facebook
2. Copy the URL from address bar
3. Paste into dashboard sidebar

---

## What the Fixed Code Does

### Before (Broken)
```python
group = GroupDatabase.create_or_update_group(name, url)
# ... later ...
for post in posts:
    post_data = extract(post, group.id)  # ❌ ERROR: group object invalid
```

### After (Fixed)
```python
group = GroupDatabase.create_or_update_group(name, url)
group_id = group.id  # ✅ Extract immediately while valid
# ... later ...
for post in posts:
    post_data = extract(post, group_id)  # ✅ Using saved ID, not object
```

---

## Expected Behavior After Fix

### First Run (After Login)
```
✅ Scanner starts
✅ Browser navigates to Facebook group
✅ Begins scrolling and finding posts
✅ Analyzes posts with Ollama LLM
✅ Stores leads in database
✅ Shows in dashboard in 2-3 minutes
```

### Subsequent Runs
```
✅ Reuses saved Facebook session
✅ No login needed
✅ Starts scanning immediately
✅ Finds new posts since last scan
```

---

## Verification Checklist

After restart, verify:

- [ ] `python facebook_login.py` completes successfully
- [ ] Browser profile exists: `ls .facebook_session/`
- [ ] Scanner starts: `python scanner.py` shows "Starting scan of X groups"
- [ ] Dashboard shows leads (refresh after 1-2 minutes)
- [ ] Comment worker running: `ps aux | grep comment_worker`

---

## If Still Not Working

### Check Scanner Logs
```bash
tail -20 logs/scanner.log
```

### Look for These Errors

| Error | Solution |
|-------|----------|
| `Page.goto: Timeout` | Run `facebook_login.py` to authenticate |
| `No group URLs` | Add group via sidebar "Add Group" input |
| `sqlite: database is locked` | Kill all processes and restart |
| `Ollama connection refused` | Start Ollama: `ollama serve` in new terminal |

### Debug Database

```bash
cd /Users/amangupta/Desktop/TravelAgent
source venv/bin/activate
python << 'EOF'
from database import GroupDatabase, LeadDatabase

# Check groups
groups = GroupDatabase.get_all_groups()
print(f"Groups in DB: {len(groups)}")
for g in groups:
    print(f"  - {g.group_name}: {g.group_url}")

# Check leads
leads = LeadDatabase.get_all_leads()
print(f"Leads in DB: {len(leads)}")
EOF
```

---

## Summary of Changes Made

### 1. Fixed SQLAlchemy Session Issue
**File:** `scanner.py`
- Extract `group_id` immediately after getting group object
- Use `group_id` variable instead of `group.id` reference

### 2. Created Facebook Login Helper
**File:** `facebook_login.py`
- Interactive script to authenticate with Facebook
- Saves session for future use
- One-time setup required

### 3. Increased Browser Timeout
**File:** `scanner.py`
- Increased from 30s to 60s for slow networks
- Gives Facebook more time to load

---

## Next Steps

✅ Run: `python facebook_login.py`  
✅ Wait for browser to open, log in  
✅ Type "done" when authenticated  
✅ Run: `python scanner.py`  
✅ Check dashboard in 2-3 minutes for leads!

---

**Questions? Check [QUICKSTART.md](QUICKSTART.md) or [PRODUCTION_README.md](PRODUCTION_README.md)**
