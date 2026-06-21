import logging
import time
from playwright.sync_api import sync_playwright, Page
from src.database import Database
from src.utils import retry

logger = logging.getLogger(__name__)

class FacebookCommenter:
    def __init__(self, db: Database, user_data_dir: str):
        self.db = db
        self.user_data_dir = user_data_dir

    @retry(max_attempts=3, delay=2)
    def post_comment(self, post_url: str, comment_text: str, post_id: int):
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.new_page()
            
            try:
                logger.info(f"Navigating to post: {post_url}")
                page.goto(post_url)
                page.wait_for_load_state("networkidle")
                
                # Look for comment box
                # FB comment boxes usually have role="textbox" and are inside a div with aria-label="Write a comment"
                comment_box = page.wait_for_selector('div[role="textbox"][aria-label*="Write a comment"], div[aria-label="Write a comment..."]', timeout=10000)
                
                if comment_box:
                    comment_box.click()
                    comment_box.fill(comment_text)
                    time.sleep(1)
                    page.keyboard.press("Enter")
                    time.sleep(2) # Wait for post to register
                    
                    logger.info("Successfully posted comment")
                    self.db.save_comment(post_id, comment_text)
                    return True
                else:
                    logger.warning("Could not find comment box")
                    return False
                    
            except Exception as e:
                logger.error(f"Error posting comment: {e}")
                return False
            finally:
                context.close()
