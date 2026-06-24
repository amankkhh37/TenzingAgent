"""
Facebook group scanner - continuously scans for travel leads
Runs in background independent of Streamlit dashboard
"""
import time
import threading
from typing import List, Optional
from datetime import datetime
from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
from database import (
    LeadDatabase, GroupDatabase, SettingsDatabase, DailyStatsDatabase,
    AuditLogDatabase, init_db
)
from lead_scorer import LeadScorer
from comment_generator import CommentGenerator
from config import (
    FACEBOOK_PROFILE_PATH, FACEBOOK_HEADLESS, MAX_SCROLLS, 
    SCAN_INTERVAL, GROUP_URLS, SCAN_LOGIN_WAIT_SECONDS, REQUIRE_LOGIN_BEFORE_SCAN
)
from logger import scanner_logger

class FacebookScanner:
    """Continuously scan Facebook groups for travel leads"""
    _instance_lock = threading.Lock()
    _active_instance = None
    
    def __init__(self):
        self.running = False
        self.lead_scorer = LeadScorer()
        self.comment_generator = CommentGenerator()
        self.scan_thread = None
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        init_db()
        scanner_logger.info("Facebook Scanner initialized")
    
    def start(self):
        """Start the scanner in background thread"""
        with self.__class__._instance_lock:
            if self.running:
                scanner_logger.warning("Scanner already running")
                return

            if self.__class__._active_instance is not None and self.__class__._active_instance != self:
                scanner_logger.warning("Another scanner instance is already running; start request ignored")
                return

            self.__class__._active_instance = self
        
        self.running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=False)
        self.scan_thread.start()
        scanner_logger.info("Scanner started")
    
    def stop(self):
        """Stop the scanner"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=10)
        with self.__class__._instance_lock:
            if self.__class__._active_instance == self:
                self.__class__._active_instance = None
        scanner_logger.info("Scanner stopped")

    def _sleep_until_stopped(self, seconds: int) -> None:
        """Sleep in short chunks so Stop Scanner can close the browser promptly."""
        end_time = time.time() + seconds
        while self.running and time.time() < end_time:
            time.sleep(min(1, end_time - time.time()))
    
    def _scan_loop(self):
        """Main scanning loop"""
        try:
            while self.running:
                try:
                    # Check if scanning is enabled
                    scan_enabled = SettingsDatabase.get_setting("scan_enabled", "true").lower() == "true"
                    use_groups = SettingsDatabase.get_setting("scan_use_groups", "true").lower() == "true"
                    
                    if not scan_enabled:
                        scanner_logger.debug("Scanning disabled, sleeping...")
                        self._sleep_until_stopped(10)
                        continue

                    if use_groups:
                        # Get group URLs
                        group_urls = self._get_group_urls()
                        if not group_urls:
                            scanner_logger.warning("Group scan mode enabled but no group URLs configured")
                            self._sleep_until_stopped(SCAN_INTERVAL)
                            continue

                        # Scan each group
                        scanner_logger.info(f"Starting group scan of {len(group_urls)} groups")
                        self._scan_groups(group_urls)
                    else:
                        scanner_logger.info("Group scan mode disabled. Scanning Facebook home/current feed")
                        self._scan_home_feed()
                    
                    # Close browser after the scan cycle is complete to release profile lock
                    self._close_browser()
                    
                    # Sleep before next scan
                    scanner_logger.info(f"Scan complete, sleeping for {SCAN_INTERVAL} seconds")
                    self._sleep_until_stopped(SCAN_INTERVAL)
                    
                except Exception as e:
                    scanner_logger.error(f"Error in scan loop: {e}", exc_info=True)
                    self._sleep_until_stopped(30)
        finally:
            self._close_browser()
            with self.__class__._instance_lock:
                if self.__class__._active_instance == self:
                    self.__class__._active_instance = None
    
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

    def _get_browser_page(self, headless: bool) -> Page:
        """Create or reuse the scanner-owned page in the scanner thread."""
        if self._context is not None:
            try:
                if self._page is not None and not self._page.is_closed():
                    return self._page

                pages = self._context.pages
                if pages:
                    self._page = pages[-1]
                    return self._page

                self._page = self._context.new_page()
                return self._page
            except Exception:
                self._close_browser()

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        scanner_logger.info(
            "Opening scanner-owned Facebook browser (headless=%s, profile=%s)",
            headless,
            FACEBOOK_PROFILE_PATH,
        )
        self._context = self._playwright.chromium.launch_persistent_context(
            FACEBOOK_PROFILE_PATH,
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        self._page = self._context.new_page()
        return self._page

    def _close_browser(self) -> None:
        """Close scanner-owned browser resources from the scanner thread."""
        if self._context is not None:
            try:
                self._context.close()
            except Exception as e:
                scanner_logger.debug(f"Error closing scanner browser context: {e}")
            finally:
                self._context = None
                self._page = None

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as e:
                scanner_logger.debug(f"Error stopping scanner Playwright: {e}")
            finally:
                self._playwright = None

    def _handle_browser_start_error(self, error: Exception) -> bool:
        message = str(error)
        if "Opening in existing browser session" not in message:
            return False

        scanner_logger.error(
            "Facebook profile is already open in another browser. Close the visible "
            "Facebook login/scanner browser window, then start the scanner again."
        )
        self.running = False
        return True
    
    def _scan_groups(self, group_urls: List[str]):
        """Scan multiple groups"""
        try:
            debug_visible_browser = SettingsDatabase.get_setting("debug_visible_browser", "false").lower() == "true"
            use_headless = FACEBOOK_HEADLESS and not debug_visible_browser
            scanner_logger.info(
                f"Using scanner-owned browser for group scan (headless={use_headless}, profile={FACEBOOK_PROFILE_PATH})"
            )

            page = self._get_browser_page(headless=use_headless)
            scanner_logger.info("Scanner browser page ready for group scan")

            if REQUIRE_LOGIN_BEFORE_SCAN:
                if not self._wait_for_login(page):
                    scanner_logger.warning(
                        "Facebook login not detected within grace period. Skipping this scan cycle."
                    )
                    return

            for group_url in group_urls:
                if not self.running:
                    break
                try:
                    self._scan_single_group(page, group_url)
                except Exception as e:
                    scanner_logger.error(f"Error scanning group {group_url}: {e}")
        except Exception as e:
            if self._handle_browser_start_error(e):
                return
            scanner_logger.error(f"Error in browser context: {e}")

    def _scan_home_feed(self):
        """Scan posts from Facebook home/current feed when group mode is disabled."""
        try:
            debug_visible_browser = SettingsDatabase.get_setting("debug_visible_browser", "false").lower() == "true"
            use_headless = FACEBOOK_HEADLESS and not debug_visible_browser
            scanner_logger.info(
                f"Using scanner-owned browser for home scan (headless={use_headless}, profile={FACEBOOK_PROFILE_PATH})"
            )

            page = self._get_browser_page(headless=use_headless)
            scanner_logger.info("Scanner browser page ready for home scan")

            if REQUIRE_LOGIN_BEFORE_SCAN:
                if not self._wait_for_login(page):
                    scanner_logger.warning(
                        "Facebook login not detected within grace period. Skipping home scan cycle."
                    )
                    return

            self._scan_single_group(page, "https://www.facebook.com/")
        except Exception as e:
            if self._handle_browser_start_error(e):
                return
            scanner_logger.error(f"Error scanning home feed: {e}")

    def _is_logged_in(self, page: Page) -> bool:
        try:
            current_url = page.url.lower()

            print(f"LOGIN CHECK URL: {current_url}")

            # If we're already on Facebook and not on login page,
            # assume login is valid.
            if "facebook.com" in current_url and "login" not in current_url:
                return True

            return False

        except Exception as e:
            print(f"LOGIN CHECK ERROR: {e}")
            return False
    def _wait_for_login(self, page: Page) -> bool:
        """Give user time to authenticate before scanning starts."""
        if self._is_logged_in(page):
            scanner_logger.info("Facebook login/session already active on existing page.")
            return True

        try:
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=60000)
        except Exception:
            # Continue with polling even if initial navigation is flaky.
            pass

        start = time.time()
        wait_seconds = max(0, SCAN_LOGIN_WAIT_SECONDS)
        scanner_logger.info(
            f"Waiting up to {wait_seconds}s for Facebook login before scanning..."
        )

        while self.running and (time.time() - start) <= wait_seconds:
            if self._is_logged_in(page):
                scanner_logger.info("Facebook login/session detected. Starting scan.")
                return True
            try:
                scanner_logger.debug(
                    "Waiting for Facebook login/session... url=%s title=%s",
                    page.url,
                    page.title(),
                )
            except Exception:
                scanner_logger.debug("Waiting for Facebook login/session...")
            time.sleep(2)

        scanner_logger.warning("Facebook login/session was not detected before timeout")
        return False
    
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
                            "group_id": group_id,
                            "group_name": group_name,
                            "post_text": post_data["post_text"],
                            "post_url": post_data.get("post_url", ""),
                            "destination": analysis.get("destination", "Not mentioned"),
                            "travel_date": analysis.get("travel_date", "Not mentioned"),
                            "group_size": analysis.get("group_size", "Not mentioned"),
                            "budget": analysis.get("budget", "Not mentioned"),
                            "intent": analysis.get("classification", "Not A Lead"),
                            "lead_score": analysis.get("lead_score", 0),
                            "reason": analysis.get("reason", ""),
                            "suggested_reply": suggested_reply,
                            "status": "APPROVED" if SettingsDatabase.get_setting("auto_comment_enabled", "true").lower() == "true" else "NEW"
                        }
                        
                        new_lead = LeadDatabase.create_lead(lead_data)
                        if new_lead:
                            leads_found += 1
                            AuditLogDatabase.log_action(new_lead.id, "CREATED", "Discovered via Facebook scan")
                            
                            stats_update = {"leads_found": 1}
                            if new_lead.status == "APPROVED":
                                AuditLogDatabase.log_action(new_lead.id, "AUTO_APPROVED", "Automatically approved based on settings")
                                stats_update["approvals"] = 1
                            
                            if (analysis.get("lead_score") or 0) >= 8:
                                stats_update["leads_high_value"] = 1
                                
                            DailyStatsDatabase.update_stats(**stats_update)
                            scanner_logger.info(f"Saved new lead {new_lead.id} from {new_lead.author} (status: {new_lead.status})")
                            
                    except Exception as e:
                        scanner_logger.error(f"Error processing post in group {group_url}: {e}")
                
                # Scroll for more posts
                if scroll_count < MAX_SCROLLS - 1:
                    try:
                        page.mouse.wheel(0, 800)
                        time.sleep(3)
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
            post_url = ""
            all_links = post_elem.query_selector_all('a')
            hrefs = []
            for link in all_links:
                href = link.get_attribute("href") or ""
                if href:
                    if not href.startswith("http"):
                        href = f"https://www.facebook.com{href}"
                    hrefs.append(href)
            
            # 1. First priority: look for direct post/permalink links
            for href in hrefs:
                if any(x in href for x in ["/posts/", "/permalink/", "story_fbid", "permalink.php", "story.php", "/multi_permalinks/"]):
                    post_url = href
                    break
            
            # 2. Second priority: look for general group links, but exclude user profile links or group main page links
            if not post_url:
                for href in hrefs:
                    if "/groups/" in href and "/user/" not in href:
                        norm_href = href.split("?")[0].rstrip("/")
                        norm_group_url = group_url.split("?")[0].rstrip("/")
                        if norm_href != norm_group_url:
                            post_url = href
                            break
                            
            if not post_url and hrefs:
                # Fallback to first link as last resort
                post_url = hrefs[0]
            
            # Extract clean post_id from post_url
            post_id = ""
            if post_url:
                from urllib.parse import urlparse, parse_qs
                try:
                    parsed = urlparse(post_url)
                    queries = parse_qs(parsed.query)
                    
                    if "story_fbid" in queries:
                        post_id = queries["story_fbid"][0]
                    elif "fbid" in queries:
                        post_id = queries["fbid"][0]
                    else:
                        path_parts = [p for p in parsed.path.split("/") if p]
                        if path_parts:
                            post_id = path_parts[-1]
                except Exception as ex:
                    scanner_logger.debug(f"Error parsing post ID from URL {post_url}: {ex}")
            
            if not post_id:
                post_id = f"{group_id}_{int(time.time())}"
            
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
