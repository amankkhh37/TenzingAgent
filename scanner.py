"""
Facebook group scanner - continuously scans for travel leads
Runs in background independent of Streamlit dashboard
"""
import time
import threading
from typing import List, Optional
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, BrowserContext
from database import (
    LeadDatabase, GroupDatabase, SettingsDatabase, DailyStatsDatabase,
    AuditLogDatabase, init_db
)
from lead_scorer import LeadScorer
from comment_generator import CommentGenerator
from config import (
    FACEBOOK_PROFILE_PATH, FACEBOOK_HEADLESS, MAX_SCROLLS, 
    SCAN_INTERVAL, GROUP_URLS
)
from logger import scanner_logger

class FacebookScanner:
    """Continuously scan Facebook groups for travel leads"""
    
    def __init__(self):
        self.running = False
        self.lead_scorer = LeadScorer()
        self.comment_generator = CommentGenerator()
        self.scan_thread = None
        init_db()
        scanner_logger.info("Facebook Scanner initialized")
    
    def start(self):
        """Start the scanner in background thread"""
        if self.running:
            scanner_logger.warning("Scanner already running")
            return
        
        self.running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=False)
        self.scan_thread.start()
        scanner_logger.info("Scanner started")
    
    def stop(self):
        """Stop the scanner"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=10)
        scanner_logger.info("Scanner stopped")
    
    def _scan_loop(self):
        """Main scanning loop"""
        while self.running:
            try:
                # Check if scanning is enabled
                scan_enabled = SettingsDatabase.get_setting("scan_enabled", "true").lower() == "true"
                
                if not scan_enabled:
                    scanner_logger.debug("Scanning disabled, sleeping...")
                    time.sleep(10)
                    continue
                
                # Get group URLs
                group_urls = self._get_group_urls()
                if not group_urls:
                    scanner_logger.warning("No group URLs configured")
                    time.sleep(SCAN_INTERVAL)
                    continue
                
                # Scan each group
                scanner_logger.info(f"Starting scan of {len(group_urls)} groups")
                self._scan_groups(group_urls)
                
                # Sleep before next scan
                scanner_logger.info(f"Scan complete, sleeping for {SCAN_INTERVAL} seconds")
                time.sleep(SCAN_INTERVAL)
                
            except Exception as e:
                scanner_logger.error(f"Error in scan loop: {e}", exc_info=True)
                time.sleep(30)
    
    def _get_group_urls(self) -> List[str]:
        """Get enabled group URLs from database and config"""
        urls = []
        
        # Get from database
        db_groups = GroupDatabase.get_all_groups()
        urls.extend([g.group_url for g in db_groups])
        
        # Add from config if not already present
        for url in GROUP_URLS:
            if url.strip() and url not in urls:
                urls.append(url)
                GroupDatabase.create_or_update_group(url, url)
        
        return list(set(urls))  # Remove duplicates
    
    def _scan_groups(self, group_urls: List[str]):
        """Scan multiple groups"""
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    FACEBOOK_PROFILE_PATH,
                    headless=FACEBOOK_HEADLESS,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-first-run",
                        "--no-default-browser-check"
                    ]
                )
                
                page = context.new_page()
                
                for group_url in group_urls:
                    if not self.running:
                        break
                    try:
                        self._scan_single_group(page, group_url)
                    except Exception as e:
                        scanner_logger.error(f"Error scanning group {group_url}: {e}")
                
                context.close()
        except Exception as e:
            scanner_logger.error(f"Error in browser context: {e}")
    
    def _scan_single_group(self, page: Page, group_url: str):
        """Scan a single Facebook group"""
        scanner_logger.info(f"Scanning group: {group_url}")
        
        try:
            # Navigate to group
            page.goto(group_url, wait_until="networkidle", timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # Extract group name
            try:
                group_name_elem = page.query_selector('h1, [data-testid="page-title-wrapper"], .x1heor9g')
                group_name = group_name_elem.inner_text() if group_name_elem else "Unknown"
            except:
                group_name = "Unknown"
            
            # Get or create group in database
            group = GroupDatabase.create_or_update_group(group_name, group_url)
            group_id = group.id  # Extract ID while object is still valid
            
            # Scroll and collect posts
            posts_found = 0
            leads_found = 0
            
            for scroll_count in range(MAX_SCROLLS):
                if not self.running:
                    break
                
                # Get posts on current view
                post_elements = page.query_selector_all('[data-testid="post"], [role="article"], div[class*="story"]')
                
                for post_elem in post_elements:
                    if not self.running:
                        break
                    
                    try:
                        # Extract post data
                        post_data = self._extract_post_data(post_elem, group_name, group_url, group_id)
                        if not post_data:
                            continue
                        
                        posts_found += 1
                        
                        # Check for duplicate
                        if LeadDatabase.get_lead_by_post_id(post_data.get("post_id", "")):
                            scanner_logger.debug(f"Duplicate post skipped: {post_data.get('post_id')}")
                            continue
                        
                        # Score the post
                        analysis = self.lead_scorer.analyze_post(post_data["post_text"], post_data["author"])
                        if not analysis:
                            continue
                        
                        # Skip if not a lead
                        if analysis.get("lead_score", 0) == 0:
                            scanner_logger.debug(f"Post from {post_data['author']} scored 0, skipping")
                            continue
                        
                        # Generate suggested reply
                        suggested_reply = self.comment_generator.generate_reply(
                            post_data["post_text"],
                            analysis.get("classification", ""),
                            analysis.get("destination", ""),
                            analysis.get("travel_date", ""),
                            analysis.get("group_size", ""),
                            analysis.get("budget", "")
                        )
                        
                        # Create lead in database
                        lead_data = {
                            "post_id": post_data.get("post_id"),
                            "author": post_data["author"],
                            "author_profile": post_data.get("author_profile", ""),
                            "group_id": group.id,
                            "group_name": group_name,
                            "post_text": post_data["post_text"],
                            "post_url": post_data["post_url"],
                            "destination": analysis.get("destination"),
                            "travel_date": analysis.get("travel_date"),
                            "group_size": analysis.get("group_size"),
                            "budget": analysis.get("budget"),
                            "intent": analysis.get("classification"),
                            "lead_score": analysis.get("lead_score", 0),
                            "reason": analysis.get("reason"),
                            "suggested_reply": suggested_reply,
                            "status": "NEW"
                        }
                        
                        lead = LeadDatabase.create_lead(lead_data)
                        if lead:
                            leads_found += 1
                            AuditLogDatabase.log_action(lead.id, "CREATED", f"Auto-discovered in group: {group_name}")
                            DailyStatsDatabase.update_stats(leads_found=1)
                            
                            # Update daily stats by score
                            if analysis.get("lead_score", 0) >= 8:
                                DailyStatsDatabase.update_stats(leads_high_value=1)
                    
                    except Exception as e:
                        scanner_logger.debug(f"Error processing post: {e}")
                        continue
                
                # Scroll for more posts
                if scroll_count < MAX_SCROLLS - 1:
                    try:
                        page.mouse.wheel(0, 3000)
                        time.sleep(2)
                    except:
                        break
            
            # Update group statistics
            GroupDatabase.update_group_stats(group_id, posts_found, leads_found)
            DailyStatsDatabase.update_stats(
                groups_scanned=1,
                posts_read=posts_found
            )
            
            scanner_logger.info(f"Group '{group_name}': {posts_found} posts, {leads_found} leads found")
        
        except Exception as e:
            scanner_logger.error(f"Error scanning group {group_url}: {e}")
    
    def _extract_post_data(self, post_elem, group_name: str, group_url: str, group_id: int) -> Optional[dict]:
        """Extract data from a post element"""
        try:
            # Extract post text
            text_selectors = [
                'div[data-testid="post_message"]',
                'div[dir="auto"]',
                '.xdj266r',
                'div[class*="message"]'
            ]
            post_text = ""
            for selector in text_selectors:
                elem = post_elem.query_selector(selector)
                if elem:
                    post_text = elem.inner_text()
                    break
            
            if not post_text or len(post_text) < 10:
                return None
            
            # Extract author
            author_selectors = [
                'a[data-testid="story_side_panel_link"]',
                'h3 a',
                '[data-testid="actor_name"] a'
            ]
            author = "Unknown"
            author_profile = ""
            for selector in author_selectors:
                elem = post_elem.query_selector(selector)
                if elem:
                    author = elem.inner_text()
                    author_profile = elem.get_attribute("href") or ""
                    break
            
            # Extract post URL
            url_elem = post_elem.query_selector('a[href*="/posts/"], a[href*="/groups/"]')
            post_url = ""
            if url_elem:
                post_url = url_elem.get_attribute("href") or ""
                if post_url and not post_url.startswith("http"):
                    post_url = f"https://www.facebook.com{post_url}"
            
            # Generate post ID from URL
            post_id = post_url.split("/")[-1] if post_url else f"{group_id}_{int(time.time())}"
            
            return {
                "post_id": post_id,
                "post_url": post_url,
                "post_text": post_text,
                "author": author,
                "author_profile": author_profile,
                "group_name": group_name,
                "group_url": group_url
            }
        
        except Exception as e:
            scanner_logger.debug(f"Error extracting post data: {e}")
            return None


def main():
    """Run scanner continuously"""
    scanner = FacebookScanner()
    try:
        scanner.start()
        scanner_logger.info("Scanner is running. Press Ctrl+C to stop.")
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scanner_logger.info("Stopping scanner...")
        scanner.stop()
    except Exception as e:
        scanner_logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
