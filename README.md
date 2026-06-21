# Tenzing Growth Agent

A sophisticated Python application for automating travel agent lead generation and engagement through Facebook groups. The app uses Playwright to scrape posts, Ollama/Qwen for AI analysis, and Streamlit for dashboard management.

## Features

- 🔍 **Facebook Group Scanning** - Automatically scan multiple Facebook groups for travel-related posts
- 🤖 **AI Lead Scoring** - Uses local Ollama with Qwen3 model to analyze posts and score leads
- 📊 **Interactive Dashboard** - Streamlit-based dashboard to review and manage leads
- 💬 **Automated Commenting** - Post curated responses directly to Facebook posts
- 💾 **SQLite Storage** - Persistent storage of posts, leads, and comments
- 🔄 **Retry Logic** - Automatic retry with exponential backoff for failed operations
- 📋 **Comprehensive Logging** - Detailed logging for debugging and monitoring

## Project Structure

```
TravelAgent/
├── app.py                 # Streamlit dashboard
├── src/
│   ├── database.py       # SQLite database management
│   ├── lead_scorer.py    # AI-powered lead analysis
│   ├── scanner.py        # Facebook group scanning
│   ├── commenter.py      # Facebook commenting automation
│   └── utils.py          # Utility functions and decorators
├── requirements.txt      # Python dependencies
└── tenzing_growth.db     # SQLite database (auto-created)
```

## Requirements

### System Requirements
- Python 3.8+
- Ollama running locally on `http://localhost:11434`
- Chrome/Chromium browser (for Playwright)

### Python Dependencies
- **playwright** - Browser automation
- **streamlit** - Web dashboard
- **ollama** - Local LLM integration
- **sqlite3** - Database (built-in)
- **pydantic** - Data validation
- **requests** - HTTP client
- **python-dotenv** - Environment variables

## Installation

1. **Clone or download the project**
   ```bash
   cd TravelAgent
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

3. **Ensure Ollama is running**
   ```bash
   # Download Qwen3 model (one-time)
   ollama pull qwen3:8b
   
   # Start Ollama server
   ollama serve
   ```

## Usage

### Initial Setup - Facebook Authentication

The app uses Playwright's persistent context to maintain your logged-in Facebook session:

1. First run will prompt browser authentication
2. Log into your Facebook account
3. Session is saved and reused for subsequent runs
4. **User data directory:** `./.facebook_session`

### Running the Dashboard

```bash
streamlit run app.py
```

The dashboard will open at `http://localhost:8501`

### Workflow

1. **Enter Facebook Group URLs** in the sidebar (one per line)
2. **Click "🔍 Scan Groups"** to start scanning
   - Posts are extracted and analyzed using Qwen3
   - Leads are scored and displayed automatically
3. **Review Leads** in the main dashboard
4. **Take Action:**
   - ✅ **Approve** - Marks lead as approved
   - ✏️ **Edit** - Modify the suggested reply and post
   - ❌ **Reject** - Marks lead as rejected
5. **Post Comments** - Click "Post Comment" to reply on Facebook

## Configuration

### Ollama Endpoint
- **Default:** `http://localhost:11434`
- **Model:** `qwen3:8b`
- Configure in app settings (sidebar)

### Database
- **Location:** `tenzing_growth.db` (created automatically)
- Contains:
  - **posts** - Scraped Facebook posts
  - **leads** - Analyzed leads with scores
  - **comments** - Posted comments history

### Logging
- **Log file:** `tenzing_growth.log`
- **Console output:** Enabled
- **Level:** INFO

## Data Structure

### Lead Analysis Output
```json
{
  "intent": "Looking for honeymoon packages",
  "destination": "Maldives",
  "lead_score": 85,
  "reason": "Specific destination mentioned, high travel intent",
  "suggested_reply": "Hi! The Maldives is absolutely stunning..."
}
```

### Post Data
```json
{
  "post_url": "https://www.facebook.com/groups/.../posts/...",
  "group_url": "https://www.facebook.com/groups/...",
  "author_name": "John Doe",
  "post_text": "Looking for a vacation in Maldives...",
  "timestamp": "2 hours ago"
}
```

## Error Handling

- **Retry Logic** - Automatic retry with exponential backoff (3 attempts)
- **Logging** - All errors logged to file and console
- **Graceful Degradation** - Failed operations don't stop the entire scan

## Known Limitations

1. Facebook layout changes may require selector updates
2. Facebook rate limiting may affect large-scale scanning
3. Requires active Facebook login session
4. Some private groups may not be accessible

## Troubleshooting

### Issue: Ollama connection failed
```
Ensure Ollama is running: ollama serve
Check endpoint: http://localhost:11434
```

### Issue: No posts found
```
- Verify group URLs are correct
- Check Facebook is logged in (check .facebook_session directory)
- Verify group visibility permissions
- Try manual Facebook group navigation first
```

### Issue: Comments not posting
```
- Verify post URL is correct
- Check comment box selectors (FB layout changes frequently)
- Ensure account has permission to comment
- Check browser console for errors
```

### Issue: Database locked
```
- Close all instances of the app
- Delete old database: rm tenzing_growth.db
- Restart the app
```

## Performance Tips

1. **Batch Processing** - Scan multiple groups in one session
2. **Lead Filtering** - Focus on leads with score >= 75
3. **Scheduled Runs** - Use cron or task scheduler for periodic scans
4. **Model Optimization** - Qwen3:8b is lightweight; consider qwen3:4b for faster inference

## Development

### Adding Custom Selectors

Edit `src/scanner.py` to update Facebook selectors if the layout changes:

```python
# Update these selectors based on Facebook's current structure
text_elem = post.query_selector('div[data-ad-comet-preview="message"], div[dir="auto"]')
author_elem = post.query_selector('h3 span a, strong span, a[role="link"] span')
```

### Extending Lead Scoring

Modify `lead_scorer.py` prompt to adjust analysis:

```python
prompt = f"""
Analyze the following Facebook post...
[Customize analysis criteria here]
"""
```

## License

Proprietary - Tenzing Growth Agent

## Support

For issues or questions:
1. Check logs: `tail -f tenzing_growth.log`
2. Verify Ollama is running
3. Check Facebook connectivity
4. Review selector validity with browser DevTools
