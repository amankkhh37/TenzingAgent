import logging
import time
from typing import List, Dict
from playwright.sync_api import sync_playwright, BrowserContext, Page
from src.database import Database
from src.lead_scorer import LeadScorer
from src.utils import retry

logger = logging.getLogger(__name__)

class FacebookScanner:
    def __init__(self, db: Database, lead_scorer: LeadScorer, user_data_dir: str):
        self.db = db
        self.lead_scorer = lead_scorer
        self.user_data_dir = user_data_dir

    def run(self, group_urls: List[str]):
        with sync_playwright() as p:
            # Launch browser with persistent context to use existing session
            context = p.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=False, # Facebook often blocks headless
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.new_page()
            
            for url in group_urls:
                try:
                    self._scan_group(page, url)
                except Exception as e:
                    logger.error(f"Error scanning group {url}: {e}")
            
            context.close()

    @retry(max_attempts=3, delay=2)
    def _scan_group(self, page: Page, group_url: str):
        logger.info(f"Scanning group: {group_url}")
        page.goto(group_url)
        page.wait_for_load_state("networkidle")
        
        # Scroll to load more posts if needed
        for _ in range(3):
            page.mouse.wheel(0, 2000)
            time.sleep(2)

        # Basic selector for posts - this may need adjustment as FB changes
        # Posts are usually in role="feed" or similar
        post_elements = page.query_selector_all('div[role="feed"] > div, div[data-ad-preview="message"]')
        
        for post in post_elements:
            try:
                # Extract post text
                # Often in a div with data-ad-comet-preview="message" or similar
                text_elem = post.query_selector('div[data-ad-comet-preview="message"], div[dir="auto"]')
                if not text_elem:
                    continue
                
                post_text = text_elem.inner_text()
                
                # Extract author name
                author_elem = post.query_selector('h3 span a, strong span, a[role="link"] span')
                author_name = author_elem.inner_text() if author_elem else "Unknown"
                
                # Extract post URL
                # Usually the timestamp link
                url_elem = post.query_selector('span[id] a[role="link"], a[href*="/posts/"], a[href*="/groups/"]')
                post_url = ""
                if url_elem:
                    href = url_elem.get_attribute("href")
                    if href:
                        # Clean up URL
                        post_url = href.split("?")[0]
                        if not post_url.startswith("http"):
                            post_url = f"https://www.facebook.com{post_url}"

                # Extract timestamp
                time_elem = post.query_selector('abbr, span[id] a[role="link"] span')
                timestamp = time_elem.inner_text() if time_elem else "Just now"

                if post_text and post_url:
                    post_data = {
                        "post_url": post_url,
                        "group_url": group_url,
                        "author_name": author_name,
                        "post_text": post_text,
                        "timestamp": timestamp
                    }
                    
                    # Save to DB
                    post_id = self.db.save_post(post_data)
                    
                    if post_id != -1:
                        # Analyze with LLM
                        logger.info(f"Analyzing post from {author_name}")
                        analysis = self.lead_scorer.analyze_post(post_text)
                        if analysis:
                            analysis['post_id'] = post_id
                            self.db.save_lead(analysis)
                            
            except Exception as e:
                logger.debug(f"Error parsing post element: {e}")
                continue
