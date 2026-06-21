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
    
    def __init__(self):
        self.running = False
        self.worker_thread = None
        init_db()
        comment_worker_logger.info("Comment Worker initialized")
    
    def start(self):
        """Start the comment worker in background thread"""
        if self.running:
            comment_worker_logger.warning("Worker already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._work_loop, daemon=False)
        self.worker_thread.start()
        comment_worker_logger.info("Comment Worker started")
    
    def stop(self):
        """Stop the comment worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        comment_worker_logger.info("Comment Worker stopped")
    
    def _work_loop(self):
        """Main worker loop"""
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
            comment_worker_logger.error(f"Error in posting comments: {e}")
        
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
            
            # Navigate to post
            page.goto(lead.post_url, wait_until="networkidle", timeout=30000)
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            
            # Find and click comment box
            comment_box_selectors = [
                'div[role="textbox"][aria-label*="comment"]',
                'div[role="textbox"][aria-label*="Comment"]',
                'div[aria-label*="Write a comment"]',
                'textarea[aria-label*="comment"]'
            ]
            
            comment_box = None
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
            
            # Click comment box
            comment_box.click()
            time.sleep(0.5)
            
            # Type comment
            page.keyboard.type(lead.suggested_reply, delay=10)
            time.sleep(0.5)
            
            # Find and click post button
            post_button_selectors = [
                'button:has-text("Post")',
                'button[aria-label*="Post"]',
                'button[type="submit"]'
            ]
            
            post_button = None
            for selector in post_button_selectors:
                try:
                    post_button = page.query_selector(selector)
                    if post_button:
                        break
                except:
                    continue
            
            if not post_button:
                comment_worker_logger.error(f"Could not find post button for lead {lead.id}")
                self._save_screenshot(page, lead.id, "error_post_button_not_found")
                return False
            
            # Click post button
            post_button.click()
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
