"""
Comment Worker - Posts approved comments to Facebook
Runs in background continuously
"""
import time
import threading
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Page
from database import LeadDatabase, AuditLogDatabase, SettingsDatabase, DailyStatsDatabase, init_db
from config import FACEBOOK_PROFILE_PATH, FACEBOOK_HEADLESS, COMMENT_CHECK_INTERVAL, COMMENT_RETRY_ATTEMPTS, COMMENT_RETRY_DELAY, SCREENSHOTS_DIR
from logger import comment_worker_logger

class CommentWorker:
    """Post approved comments to Facebook automatically"""
    _instance_lock = threading.Lock()
    _active_instance = None
    
    def __init__(self):
        self.running = False
        self.worker_thread = None
        init_db()
        comment_worker_logger.info("Comment Worker initialized")
    
    def start(self):
        """Start the comment worker in background thread"""
        with self.__class__._instance_lock:
            if self.running:
                comment_worker_logger.warning("Worker already running")
                return

            if self.__class__._active_instance is not None and self.__class__._active_instance != self:
                comment_worker_logger.warning("Another comment worker instance is already running; start request ignored")
                return

            self.__class__._active_instance = self
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._work_loop, daemon=False)
        self.worker_thread.start()
        comment_worker_logger.info("Comment Worker started")
    
    def stop(self):
        """Stop the comment worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        with self.__class__._instance_lock:
            if self.__class__._active_instance == self:
                self.__class__._active_instance = None
        comment_worker_logger.info("Comment Worker stopped")
    
    def _work_loop(self):
        """Main worker loop"""
        try:
            while self.running:
                try:
                    # Check if posting is enabled
                    posting_enabled = SettingsDatabase.get_setting("posting_enabled", "true").lower() == "true"
                    
                    if not posting_enabled:
                        comment_worker_logger.debug("Posting disabled, sleeping...")
                        time.sleep(10)
                        continue
                    
                    # Get approved leads
                    approved_leads = LeadDatabase.get_leads_by_status("APPROVED")
                    
                    if approved_leads:
                        comment_worker_logger.info(f"Found {len(approved_leads)} approved leads to post")
                        self._post_comments(approved_leads)
                    
                    # Sleep before next check
                    time.sleep(COMMENT_CHECK_INTERVAL)
                    
                except Exception as e:
                    comment_worker_logger.error(f"Error in work loop: {e}", exc_info=True)
                    time.sleep(30)
        finally:
            with self.__class__._instance_lock:
                if self.__class__._active_instance == self:
                    self.__class__._active_instance = None
    
    def _post_comments(self, leads):
        """Post comments for approved leads"""
        posted_count = 0
        failed_count = 0
        
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    FACEBOOK_PROFILE_PATH,
                    headless=FACEBOOK_HEADLESS,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage"
                    ]
                )
                
                page = context.new_page()
                
                for lead in leads:
                    if not self.running:
                        break
                    
                    success = False
                    for attempt in range(COMMENT_RETRY_ATTEMPTS):
                        try:
                            success = self._post_single_comment(page, lead)
                            if success:
                                posted_count += 1
                                break
                        except Exception as e:
                            comment_worker_logger.warning(f"Attempt {attempt + 1} failed for lead {lead.id}: {e}")
                            if attempt < COMMENT_RETRY_ATTEMPTS - 1:
                                time.sleep(COMMENT_RETRY_DELAY)
                    
                    if not success:
                        failed_count += 1
                        # Move back to REVIEWING if all attempts failed
                        LeadDatabase.update_lead(lead.id, status="REVIEWING")
                        AuditLogDatabase.log_action(lead.id, "POST_FAILED", "Max retries exceeded")
                        comment_worker_logger.error(f"Failed to post comment for lead {lead.id}")
                
                context.close()
        
        except Exception as e:
            err_msg = str(e)
            if any(x in err_msg.lower() for x in ["lock", "user data directory is already in use", "existing browser session", "closed"]):
                comment_worker_logger.warning("Could not start browser context - profile directory may be locked by another process (e.g., scanner). Will retry in the next cycle.")
            else:
                comment_worker_logger.error(f"Error in posting comments: {e}", exc_info=True)
        
        # Update statistics
        if posted_count > 0:
            DailyStatsDatabase.update_stats(comments_posted=posted_count)
            comment_worker_logger.info(f"Successfully posted {posted_count} comments")
        
        if failed_count > 0:
            comment_worker_logger.warning(f"Failed to post {failed_count} comments")
    
    def _post_single_comment(self, page: Page, lead) -> bool:
        """Post a single comment to Facebook"""
        try:
            comment_worker_logger.info(f"Posting comment for lead {lead.id}: {lead.post_url}")
            
            # Skip invalid URLs (e.g. pointing to user profile page)
            is_valid_url = lead.post_url and any(x in lead.post_url for x in ["/posts/", "/permalink/", "story_fbid", "permalink.php", "story.php", "/multi_permalinks/"])
            is_user_profile = lead.post_url and ("/user/" in lead.post_url or "/people/" in lead.post_url)
            
            if is_user_profile or not is_valid_url:
                comment_worker_logger.warning(f"Skipping lead {lead.id} due to invalid post URL: {lead.post_url}")
                LeadDatabase.update_lead(lead.id, status="REJECTED")
                AuditLogDatabase.log_action(lead.id, "REJECTED", f"Automatically rejected: URL '{lead.post_url}' points to a user profile, not a specific post thread.")
                return False
            
            # Navigate to post
            page.goto(lead.post_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
            
            # Check if this is a comment reply rather than a post comment
            is_comment_reply = False
            comment_id = ""
            if "comment_id=" in lead.post_url:
                from urllib.parse import urlparse, parse_qs
                try:
                    parsed = urlparse(lead.post_url)
                    queries = parse_qs(parsed.query)
                    if "comment_id" in queries:
                        comment_id = queries["comment_id"][0]
                        is_comment_reply = True
                except Exception as ex:
                    comment_worker_logger.debug(f"Error parsing comment_id from URL: {ex}")

            comment_box = None
            
            if is_comment_reply and comment_id:
                comment_worker_logger.info(f"Targeting comment reply thread for comment_id: {comment_id}")
                
                # Locate the specific comment container
                comment_container_selectors = [
                    f'div[data-commentid*="{comment_id}"]',
                    f'[id*="{comment_id}"]',
                    f'div[role="article"]:has(a[href*="{comment_id}"])',
                    f'div:has(a[href*="{comment_id}"])'
                ]
                
                comment_container = None
                for selector in comment_container_selectors:
                    try:
                        comment_container = page.wait_for_selector(selector, timeout=5000)
                        if comment_container:
                            comment_worker_logger.info(f"Found comment container with selector: {selector}")
                            break
                    except:
                        continue
                
                if comment_container:
                    # Find and click the "Reply" button/link within the comment container
                    reply_button_selectors = [
                        'div[role="button"]:has-text("Reply")',
                        'span:has-text("Reply")',
                        'a:has-text("Reply")',
                        '[role="button"][aria-label*="Reply"]',
                        '[aria-label*="Reply"]'
                    ]
                    
                    reply_button = None
                    for r_selector in reply_button_selectors:
                        try:
                            reply_button = comment_container.query_selector(r_selector)
                            if reply_button:
                                comment_worker_logger.info(f"Found Reply button with selector: {r_selector}")
                                reply_button.scroll_into_view_if_needed()
                                time.sleep(0.5)
                                reply_button.click()
                                time.sleep(1)
                                break
                        except:
                            continue
                    
                    # After clicking Reply, find the reply input box in the comment container
                    reply_box_selectors = [
                        'div[role="textbox"][aria-label*="reply"]',
                        'div[role="textbox"][aria-label*="Reply"]',
                        'div[aria-label*="Write a reply"]',
                        'textarea[aria-label*="reply"]',
                        'div[role="textbox"]'
                    ]
                    
                    for box_selector in reply_box_selectors:
                        try:
                            comment_box = comment_container.query_selector(box_selector)
                            if comment_box:
                                comment_worker_logger.info(f"Found reply input box within container: {box_selector}")
                                break
                        except:
                            continue
                            
                    if not comment_box:
                        for box_selector in reply_box_selectors:
                            try:
                                comment_box = page.wait_for_selector(box_selector, timeout=2000)
                                if comment_box:
                                    comment_worker_logger.info(f"Found reply input box globally: {box_selector}")
                                    break
                            except:
                                continue
                else:
                    comment_worker_logger.warning(f"Could not find comment container for comment_id {comment_id}, falling back to main comment box.")
            
            if not comment_box:
                # Find and click main comment box
                comment_box_selectors = [
                    'div[role="textbox"][aria-label*="comment"]',
                    'div[role="textbox"][aria-label*="Comment"]',
                    'div[aria-label*="Write a comment"]',
                    'textarea[aria-label*="comment"]'
                ]
                
                for selector in comment_box_selectors:
                    try:
                        comment_box = page.wait_for_selector(selector, timeout=5000)
                        if comment_box:
                            break
                    except:
                        continue
            
            if not comment_box:
                comment_worker_logger.error(f"Could not find comment box for lead {lead.id}")
                self._save_screenshot(page, lead.id, "error_comment_box_not_found")
                return False
            
            # Scroll comment box into view and click
            try:
                comment_box.scroll_into_view_if_needed()
                time.sleep(0.5)
            except Exception as e:
                comment_worker_logger.debug(f"Scroll into view failed: {e}")
                
            comment_box.click()
            time.sleep(0.5)
            
            # Type comment
            page.keyboard.type(lead.suggested_reply, delay=10)
            time.sleep(0.5)
            
            # Find and click post button
            post_button_selectors = [
                'form [role="button"][aria-label*="Comment"]',
                'div[role="button"][aria-label*="Comment"]',
                'button:has-text("Post")',
                'button[aria-label*="Post"]',
                'button[type="submit"]',
                'div[aria-label="Comment"]',
                'div[aria-label="Post"]',
                'span:has-text("Post")'
            ]
            
            post_button = None
            for selector in post_button_selectors:
                try:
                    post_button = page.query_selector(selector)
                    if post_button:
                        break
                except:
                    continue
            
            if post_button:
                try:
                    post_button.scroll_into_view_if_needed()
                    time.sleep(0.2)
                    post_button.click()
                except Exception as e:
                    comment_worker_logger.warning(f"Failed to click post button, will try pressing Enter: {e}")
                    page.keyboard.press("Enter")
            else:
                comment_worker_logger.info("Post button not found, attempting to post by pressing Enter")
                page.keyboard.press("Enter")
            
            time.sleep(2)
            
            # Verify post was successful (simple check: page loaded without error)
            try:
                page.wait_for_selector('div[role="status"]', timeout=3000)  # Posted notification
            except:
                pass
            
            # Save screenshot of successful post
            self._save_screenshot(page, lead.id, "success")
            
            # Update lead status
            LeadDatabase.update_lead(lead.id, status="POSTED", contacted=True)
            AuditLogDatabase.log_action(lead.id, "POSTED", f"Comment posted at {datetime.utcnow()}")
            DailyStatsDatabase.update_stats(approvals=1)
            
            comment_worker_logger.info(f"Successfully posted comment for lead {lead.id}")
            return True
        
        except Exception as e:
            comment_worker_logger.error(f"Error posting comment for lead {lead.id}: {e}")
            self._save_screenshot(page, lead.id, f"error_{str(e)[:20]}")
            return False
    
    def _save_screenshot(self, page: Page, lead_id: int, status: str):
        """Save screenshot for debugging"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"lead_{lead_id}_{status}_{timestamp}.png"
            filepath = SCREENSHOTS_DIR / filename
            page.screenshot(path=str(filepath))
            comment_worker_logger.debug(f"Screenshot saved: {filename}")
        except Exception as e:
            comment_worker_logger.debug(f"Could not save screenshot: {e}")


def main():
    """Run comment worker continuously"""
    worker = CommentWorker()
    try:
        worker.start()
        comment_worker_logger.info("Comment Worker is running. Press Ctrl+C to stop.")
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        comment_worker_logger.info("Stopping Comment Worker...")
        worker.stop()
    except Exception as e:
        comment_worker_logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
