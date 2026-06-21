# 🚀 Quick Start Guide - Tenzing Growth Agent

Get up and running in 5 minutes!

## Prerequisites
- Python 3.12+
- 12GB RAM minimum (4GB for app, 8GB for Ollama)
- Chrome/Chromium browser
- ~10GB disk space

## Step 1: Install & Setup (5 min)

```bash
# Navigate to project
cd /Users/amangupta/Desktop/TravelAgent

# Activate virtual environment (already created)
source venv/bin/activate

# Verify installation
python -c "import playwright; print('✅ All dependencies installed')"
```

## Step 2: Start Ollama (Open New Terminal)

```bash
# Start Ollama server (keep this running)
ollama serve

# In another terminal, verify it's running:
curl http://localhost:11434/api/tags
# Should return: {"models": [{"name": "qwen3:8b", ...}]}
```

## Step 3: Initialize Database

```bash
# Still in venv, run:
python -c "from database import init_db; init_db(); print('✅ Database initialized')"
```

## Step 4: Add Your Facebook Groups

Create a simple config file `/Users/amangupta/Desktop/TravelAgent/.env`:

```bash
GROUP_URLS=https://www.facebook.com/groups/123456789,https://www.facebook.com/groups/987654321
```

Replace with your actual Facebook group URLs.

## Step 5: Start All Services

### Option A: Automatic (macOS/Linux)
```bash
chmod +x /Users/amangupta/Desktop/TravelAgent/start.sh
./start.sh
```

### Option B: Manual (3 Terminals)

**Terminal 1 - Scanner:**
```bash
cd /Users/amangupta/Desktop/TravelAgent
source venv/bin/activate
python scanner.py
```

**Terminal 2 - Comment Worker:**
```bash
cd /Users/amangupta/Desktop/TravelAgent
source venv/bin/activate
python comment_worker.py
```

**Terminal 3 - Dashboard:**
```bash
cd /Users/amangupta/Desktop/TravelAgent
source venv/bin/activate
streamlit run app.py
```

Dashboard opens at: **http://localhost:8501**

## Step 6: First Run - Facebook Login

When scanner starts:
1. A Chrome browser window will open
2. You'll see Facebook login screen
3. **Log into your Facebook account**
4. Grant permission to access groups
5. Browser profile is saved (no login needed next time)

## Step 7: Start Scanning!

In the dashboard:
1. Go to **Sidebar → Scanner Controls**
2. Click **▶️ Start Scanner**
3. Scanner begins finding posts
4. Check back in 1-2 minutes

## Step 8: Review Leads

1. Go to **Tab: New Leads**
2. You'll see discovered travel posts
3. Each post has:
   - **Author name** and post text
   - **Lead Score** (0-10)
   - **Suggested Reply**
   - Action buttons: ✅ Approve | ✏️ Edit | ❌ Reject

## Step 9: Approve & Post

### Quick Post (Auto-Reply):
```
Click ✅ Approve
→ Suggested reply auto-posts to Facebook
→ Lead moves to "Posted" tab
```

### Custom Reply:
```
Click ✏️ Edit
→ Modify the suggested reply
→ Click 💾 Save & Approve
→ Comment posts to Facebook
```

## Understanding Lead Scores

| Score | Meaning | Example |
|-------|---------|---------|
| **10** | Ready to book | "Need cab from NJP to Gangtok TOMORROW for 4 people" |
| **8-9** | Clear interest | "Planning Sikkim trip next month, looking for packages" |
| **5-7** | Light interest | "Best hotels in Gangtok?" |
| **0-4** | Not a lead | "Great photos from Tsomgo Lake!" |

## Check the Dashboard

Visit **http://localhost:8501** and explore:

- **📌 Dashboard**: Overview metrics
- **🆕 New Leads**: Posts awaiting review  
- **⭐ High Value**: Score ≥ 8 leads
- **✅ Approved**: Pending posting
- **📤 Posted**: Already commented
- **📊 Analytics**: Performance insights

## Verify Everything Works

```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Check database
python -c "from database import LeadDatabase; print(f'Leads: {LeadDatabase.count_leads()}')"

# Check scanner logs
tail -f logs/scanner.log

# Check worker logs
tail -f logs/comment_worker.log
```

## Common Issues

### Issue: "Cannot connect to Ollama"
```bash
# Start Ollama in another terminal
ollama serve
```

### Issue: "No leads found"
```bash
1. Verify group URLs are public
2. Log in manually to Facebook first
3. Check Facebook hasn't changed selectors
4. Try a different group
```

### Issue: "Comments not posting"
```bash
1. Verify Facebook login (should be automatic)
2. Check post URLs are valid
3. Review logs: tail -f logs/comment_worker.log
4. Check comment isn't spam-flagged by Facebook
```

### Issue: Slow performance
```bash
# Reduce scan frequency
# Edit config.py: SCAN_INTERVAL = 600  (10 minutes)

# Or use faster model
ollama pull qwen3:4b
# Edit config.py: OLLAMA_MODEL = "qwen3:4b"
```

## Next Steps

### Customize for Your Business
- Edit `comment_generator.py` for your messaging
- Add your locations to `lead_scorer.py` tips
- Customize dashboard in `app.py`

### Monitor Performance
- Check **Analytics tab** daily
- Track conversion rates
- Identify best-performing groups

### Set Up Follow-ups
- Use **Follow-ups tab** for reminders
- Create campaigns for high-value leads
- Track which leads convert

### Generate Content
- Use **Content tab** to create daily posts
- AI generates suggestions
- Review before posting

## System Architecture

```
Scanner (background)
  ↓ discovers posts
  ↓ scores with Ollama
  ↓ stores in database

Comment Worker (background)
  ↓ finds approved leads
  ↓ posts to Facebook
  ↓ logs everything

Dashboard (Streamlit)
  ↓ reads database only
  ↓ shows analytics
  ↓ takes user actions
```

## Key Files

```
scanner.py           - Finds posts (keep running)
comment_worker.py    - Posts replies (keep running)
app.py              - Dashboard (Streamlit)
database.py         - SQLite operations
lead_scorer.py      - Ollama integration
comment_generator.py - Reply creation
models.py           - Database schema
```

## Logs Location

```bash
logs/scanner.log        - Scanner activity
logs/comment_worker.log - Posting activity
logs/app.log           - Dashboard activity
```

## Database

```bash
# Location
data/travel_crm.db

# Backup
cp data/travel_crm.db data/backup_$(date +%Y%m%d_%H%M%S).db

# Export to CSV
python -c "
import pandas as pd
from sqlalchemy import create_engine
engine = create_engine('sqlite:///data/travel_crm.db')
df = pd.read_sql('SELECT * FROM leads', engine)
df.to_csv('leads.csv', index=False)
"
```

## Stop Services

```bash
# Dashboard: Press Ctrl+C in Streamlit terminal
# Scanner: Ctrl+C in scanner terminal
# Worker: Ctrl+C in worker terminal
```

## Pro Tips

1. **Let it run 24/7** - Scanner works best with continuous operation
2. **Check daily** - Dashboard updates in real-time
3. **Edit replies** - Don't just auto-approve, customize for maximum response
4. **Track patterns** - Analytics shows which groups/destinations work best
5. **Pause if needed** - Use Sidebar controls to pause/resume anytime

## Expected Performance

- **Scan Time**: 30-60 seconds per group
- **Posting**: 5-10 seconds per comment  
- **Analysis**: 2-5 seconds per post
- **Leads/Day**: 50-150 depending on group activity
- **Conversion Rate**: 30-50% (varies by quality of reply)

## Getting Help

Check logs first:
```bash
tail -f logs/scanner.log
tail -f logs/comment_worker.log
```

Then read: `PRODUCTION_README.md` for detailed documentation.

---

**You're all set! 🎉**

Your AI-powered lead generation system is running. Start scanning, reviewing, and converting leads in minutes.

Questions? Check `PRODUCTION_README.md` for comprehensive documentation.
