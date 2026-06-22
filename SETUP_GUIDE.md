# Tenzing Growth Agent - Configuration Guide

## Initial Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install
```

### 2. Start Ollama (Optional)
```bash
# Terminal 1 - Start Ollama server
ollama serve

# Terminal 2 - Download Qwen3 model (first time only)
ollama pull qwen3:8b
### 2b. Configure Azure Foundry/OpenAI (Optional)

If Ollama is not available, configure Azure in `.env`:

```bash
LLM_PROVIDER=auto
AZURE_OPENAI_ENDPOINT=https://amanbyguptaaccenture.services.ai.azure.com
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

You can force Azure only mode by setting:

```bash
LLM_PROVIDER=azure
```
```

### 3. Run the Dashboard
```bash
# Terminal 3 - Start Streamlit app
streamlit run app.py
```

## First Run - Facebook Authentication

1. When you first click "🔍 Scan Groups", a browser window will open
2. Log into your Facebook account
3. The session is saved in `./.facebook_session` directory
4. Subsequent runs will reuse this session (no login needed)

## Dashboard Guide

### Sidebar
- **Scan Groups Tab**: Enter Facebook group URLs and scan
- **Settings Tab**: View Ollama configuration (read-only)

### Main Dashboard

**Columns:**
- **Post**: Shows author name, post text preview, and link to Facebook post
- **Lead Score**: Color-coded score (Hot: 75+, Warm: 50-74, Cold: <50)
- **Suggested Reply**: Preview of AI-generated comment
- **Action**: Approve, Edit, or Reject buttons

**Lead Status:**
- **pending**: Initial state - awaiting review
- **approved**: You approved the lead
- **rejected**: You rejected the lead
- **posted**: Comment was successfully posted on Facebook

### Workflow

#### Option 1: Quick Post
1. Click ✅ **Approve** to mark as approved
2. Automatically generates and posts the suggested reply

#### Option 2: Edit Before Posting
1. Click ✏️ **Edit**
2. Expander opens with full reply text
3. Modify the comment as needed
4. Click "📤 Post Comment" to post to Facebook
5. Click "Cancel" to close the editor

#### Option 3: Skip Lead
1. Click ❌ **Reject** to skip the lead

## Facebook Selectors

The scanner uses CSS selectors to extract posts. Facebook frequently changes their layout, so selectors may need updating.

### Current Selectors (as of 2024)
Located in `src/scanner.py`:

```python
# Post text
'div[data-ad-comet-preview="message"], div[dir="auto"]'

# Author name
'h3 span a, strong span, a[role="link"] span'

# Post URL
'span[id] a[role="link"], a[href*="/posts/"], a[href*="/groups/"]'

# Timestamp
'abbr, span[id] a[role="link"] span'
```

### If Scanner Not Finding Posts

1. Open Facebook group in browser
2. Right-click on a post → "Inspect"
3. Note the HTML structure
4. Update selectors in `src/scanner.py`

## Lead Scoring

The AI analyzes posts for:
- **Intent**: What the user wants (booking, recommendations, information)
- **Destination**: Where they want to go
- **Lead Score**: 0-100 ranking
- **Reason**: Why that score was given
- **Suggested Reply**: Professional travel agent response

### Customizing Analysis

Edit `src/lead_scorer.py` to modify the prompt:

```python
prompt = f"""
Analyze the following Facebook post...
[Your custom instructions here]
"""
```

## Database Management

### View Database Contents

```python
import sqlite3

conn = sqlite3.connect('tenzing_growth.db')
cursor = conn.cursor()

# View all posts
cursor.execute('SELECT * FROM posts')
for row in cursor.fetchall():
    print(row)

# View pending leads
cursor.execute('SELECT * FROM leads WHERE status = "pending"')
for row in cursor.fetchall():
    print(row)

# View posted comments
cursor.execute('SELECT * FROM comments')
for row in cursor.fetchall():
    print(row)

conn.close()
```

### Export Data

```python
import pandas as pd
import sqlite3

conn = sqlite3.connect('tenzing_growth.db')

# Export leads to CSV
df = pd.read_sql_query('SELECT * FROM leads', conn)
df.to_csv('leads.csv', index=False)

conn.close()
```

### Reset Database

```bash
rm tenzing_growth.db
# Database will be recreated on next run
```

## Logging

### View Logs

```bash
# Real-time logs
tail -f tenzing_growth.log

# Last 100 lines
tail -n 100 tenzing_growth.log

# Search for errors
grep ERROR tenzing_growth.log
```

### Log Levels

- **INFO**: Normal operations
- **WARNING**: Retries, non-critical issues
- **ERROR**: Failed operations
- **DEBUG**: Detailed parsing information

## Performance Optimization

### For Large-Scale Scanning

1. **Use multiple group URLs** in one scan session
2. **Increase scroll depth** in `src/scanner.py`:
   ```python
   for _ in range(5):  # Increase from 3
       page.mouse.wheel(0, 2000)
       time.sleep(2)
   ```

3. **Adjust retry settings** in `src/utils.py`:
   ```python
   @retry(max_attempts=2, delay=1)  # Fewer retries = faster
   ```

### For Faster AI Analysis

Use smaller model:
```bash
ollama pull qwen3:4b
```

Then update `app.py`:
```python
lead_scorer = LeadScorer(model="qwen3:4b")
```

## Troubleshooting

### Ollama Not Found
```
Error: Connection refused
Solution: 
1. Start Ollama: ollama serve
2. Verify: curl http://localhost:11434/api/tags
```

### No Posts Found
```
Solution:
1. Check group URL is public/accessible
2. Log in to Facebook manually
3. Verify selectors with browser DevTools
4. Try group with recent posts
```

### Comments Not Posting
```
Solution:
1. Verify browser is logged into Facebook
2. Test Facebook login: streamlit run test_facebook.py
3. Check post URL is still valid
4. Review browser console for JS errors
```

### Database Locked
```
Solution:
1. Close Streamlit: Ctrl+C
2. Close any database browser tools
3. Wait 10 seconds
4. Restart: streamlit run app.py
```

## Advanced Usage

### Scheduled Scanning

Create `schedule_scan.py`:

```python
import schedule
import time
from main import main

schedule.every().day.at("10:00").do(main)

while True:
    schedule.run_pending()
    time.sleep(60)
```

Run: `python schedule_scan.py`

### Slack Integration

Add to `src/commenter.py`:

```python
import requests

def notify_slack(lead_data):
    webhook_url = os.getenv('SLACK_WEBHOOK')
    requests.post(webhook_url, json={
        "text": f"New lead posted: {lead_data['author_name']}"
    })
```

## Support

For issues:
1. Check `tenzing_growth.log` for error messages
2. Review Facebook selectors with DevTools
3. Verify Ollama is running and responsive
4. Test individual components with `test_tenzing.py`
