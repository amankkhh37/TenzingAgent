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

def is_post_older_than_n_days(time_text: str, n_days: int) -> bool:
    """
    Check if the post relative/absolute time string is older than n_days.
    Returns True if older than n_days, False otherwise.
    """
    if not time_text:
        return False
        
    time_text = time_text.lower().strip()
    
    # "just now", "1m", "59m", "1h", "23h" are all within 1 day, so not older than n_days (where n_days >= 1)
    if "just now" in time_text or "now" in time_text:
        return False
    if any(suffix in time_text for suffix in ["m", "min", "minute", "h", "hr", "hour"]):
        # Make sure it's not a day or month name starting with 'm' or 'h'
        if not ("day" in time_text or "yesterday" in time_text):
            return False
            
    # Parse relative days: "1d", "2d", "3d", "yesterday", "2 days ago", etc.
    if "yesterday" in time_text:
        return n_days < 1
        
    # Extract number if "d" or "day" is in the text
    if "d" in time_text or "day" in time_text:
        import re
        match = re.search(r'(\d+)', time_text)
        if match:
            days = int(match.group(1))
            return days > n_days
            
    # Parse absolute dates like "20 June", "June 20", "20 Jun at 14:00"
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    
    found_month = None
    for m_name, m_val in months.items():
        if m_name in time_text:
            found_month = m_val
            break
            
    if found_month:
        import re
        # Find day number
        match = re.search(r'(\d+)', time_text)
        if match:
            day = int(match.group(1))
            # Construct date
            now = datetime.utcnow()
            try:
                # Assume current year unless specified
                year = now.year
                # Check if year is mentioned (e.g. 4-digit number not matching day or time)
                year_match = re.search(r'\b(20\d{2})\b', time_text)
                if year_match:
                    year = int(year_match.group(1))
                
                from datetime import datetime as dt
                post_date = dt(year, found_month, day)
                # If post_date is in future (due to year rollover/timezone), assume previous year
                if post_date > now:
                    post_date = dt(year - 1, found_month, day)
                    
                age = now - post_date
                return age.days > n_days
            except:
                pass
                
    return False

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
                            scan_interval_mins = int(SettingsDatabase.get_setting("scan_interval_minutes", "15"))
                            self._sleep_until_stopped(scan_interval_mins * 60)
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
                    scan_interval_mins = int(SettingsDatabase.get_setting("scan_interval_minutes", "15"))
                    scanner_logger.info(f"Scan complete, sleeping for {scan_interval_mins} minutes")
                    self._sleep_until_stopped(scan_interval_mins * 60)
                    
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
                            
                        # Filter by post age (History Limit configured from UI)
                        max_days = int(SettingsDatabase.get_setting("scan_max_days", "2"))
                        post_age_str = post_data.get("timestamp", "")
                        if post_age_str and is_post_older_than_n_days(post_age_str, max_days):
                            scanner_logger.info(f"Skipping post {post_data.get('post_id')} because it is older than {max_days} days (Age: '{post_age_str}')")
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
                                
                                # Post comment immediately in the same browser context via a temporary page
                                posted_ok = self._post_comment_inline(
                                    post_url=new_lead.post_url,
                                    reply_text=new_lead.suggested_reply,
                                    lead_id=new_lead.id
                                )
                                if posted_ok:
                                    LeadDatabase.update_lead(new_lead.id, status="POSTED", contacted=True)
                                    AuditLogDatabase.log_action(new_lead.id, "POSTED", f"Comment posted immediately during scan at {datetime.utcnow()}")
                                    stats_update["comments_posted"] = 1
                                else:
                                    AuditLogDatabase.log_action(new_lead.id, "POST_FAILED", "Immediate posting failed; queued for comment worker")
                            
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
            
    def _post_comment_inline(self, post_url: str, reply_text: str, lead_id: int) -> bool:
        """Post a comment immediately using the scanner's browser context."""
        if not self._context:
            scanner_logger.warning("No browser context available to post comment immediately")
            return False
            
        post_page = None
        try:
            scanner_logger.info(f"Posting comment immediately for lead {lead_id} at {post_url}")
            post_page = self._context.new_page()
            
            # Navigate to post
            post_page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
            post_page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
            
            # Check if this is a comment reply rather than a post comment
            is_comment_reply = False
            comment_id = ""
            if "comment_id=" in post_url:
                from urllib.parse import urlparse, parse_qs
                try:
                    parsed = urlparse(post_url)
                    queries = parse_qs(parsed.query)
                    if "comment_id" in queries:
                        comment_id = queries["comment_id"][0]
                        is_comment_reply = True
                except Exception as ex:
                    scanner_logger.debug(f"Error parsing comment_id from URL: {ex}")

            comment_box = None
            comment_container = None
            
            if is_comment_reply and comment_id:
                scanner_logger.info(f"Targeting comment reply thread for comment_id: {comment_id}")
                
                # Locate the specific comment container
                comment_container_selectors = [
                    f'div[data-commentid*="{comment_id}"]',
                    f'[id*="{comment_id}"]',
                    f'div[role="article"]:has(a[href*="{comment_id}"])',
                    f'div:has(a[href*="{comment_id}"])'
                ]
                
                for selector in comment_container_selectors:
                    try:
                        comment_container = post_page.wait_for_selector(selector, timeout=5000)
                        if comment_container:
                            scanner_logger.info(f"Found comment container with selector: {selector}")
                            break
                    except:
                        continue
                
                if comment_container:
                    # Check if we already replied inside this specific comment thread
                    try:
                        container_text = comment_container.inner_text()
                        if "sikkimtourandcabs.in" in container_text:
                            scanner_logger.info(f"Duplicate check: Website link already found in comment thread for lead {lead_id}, skipping.")
                            return True
                    except Exception as e:
                        scanner_logger.debug(f"Comment container text check failed: {e}")
                        
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
                                scanner_logger.info(f"Found Reply button with selector: {r_selector}")
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
                            comment_box = comment_container.wait_for_selector(box_selector, timeout=3000)
                            if comment_box:
                                scanner_logger.info(f"Found reply input box within container: {box_selector}")
                                break
                        except:
                            continue
                            
                    if not comment_box:
                        for box_selector in reply_box_selectors:
                            try:
                                comment_box = post_page.wait_for_selector(box_selector, timeout=2000)
                                if comment_box:
                                    scanner_logger.info(f"Found reply input box globally: {box_selector}")
                                    break
                            except:
                                continue
                else:
                    scanner_logger.warning(f"Could not find comment container for comment_id {comment_id}, falling back to main comment box.")

            # If we couldn't find the comment container (or if it's not a comment reply in the first place)
            # check the entire page for duplication
            if not is_comment_reply or not comment_container:
                try:
                    page_text = post_page.content()
                    if "sikkimtourandcabs.in" in page_text:
                        scanner_logger.info(f"Duplicate check: Website link already found on page for lead {lead_id}, skipping.")
                        return True
                except Exception as e:
                    scanner_logger.debug(f"Page text duplicate check failed: {e}")

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
                        comment_box = post_page.wait_for_selector(selector, timeout=5000)
                        if comment_box:
                            break
                    except:
                        continue
            
            if not comment_box:
                scanner_logger.error(f"Could not find comment box for lead {lead_id}")
                return False
            
            # Scroll comment box into view and click
            try:
                comment_box.scroll_into_view_if_needed()
                time.sleep(0.5)
            except Exception as e:
                scanner_logger.debug(f"Scroll into view failed: {e}")
                
            comment_box.click()
            time.sleep(0.5)
            
            # Type comment
            post_page.keyboard.type(reply_text, delay=10)
            time.sleep(0.5)
            
            # Press Enter to post
            scanner_logger.info("Attempting to post by pressing Enter")
            post_page.keyboard.press("Enter")
            time.sleep(2)
            
            is_posted = False
            try:
                box_text = comment_box.inner_text()
                if reply_text not in box_text:
                    is_posted = True
            except Exception:
                is_posted = True
                
            if not is_posted:
                scanner_logger.info("Enter key press did not submit the comment. Attempting to find and click submit button.")
                # Find and click post button
                post_button_selectors = [
                    'form [role="button"][aria-label*="Comment"]',
                    'div[role="button"][aria-label*="Comment"]',
                    'button[aria-label*="Post"]',
                    'button[type="submit"]',
                    'div[aria-label="Comment"]',
                    'div[aria-label="Post"]'
                ]
                
                post_button = None
                if is_comment_reply and comment_container:
                    for selector in post_button_selectors:
                        try:
                            post_button = comment_container.query_selector(selector)
                            if post_button:
                                scanner_logger.info(f"Found post button inside comment container: {selector}")
                                break
                        except:
                            continue
                
                if not post_button:
                    for selector in post_button_selectors:
                        try:
                            post_button = post_page.query_selector(selector)
                            if post_button:
                                break
                        except:
                            continue
                
                if post_button:
                    try:
                        post_button.scroll_into_view_if_needed()
                        time.sleep(0.2)
                        post_button.click()
                        time.sleep(2)
                    except Exception as e:
                        scanner_logger.warning(f"Failed to click post button: {e}")
                else:
                    scanner_logger.warning("No submit button found to click.")
            
            # Final validation check
            final_posted = False
            try:
                box_text = comment_box.inner_text()
                if reply_text not in box_text:
                    final_posted = True
            except Exception:
                final_posted = True
                
            if not final_posted:
                scanner_logger.error(f"Comment was not successfully posted for lead {lead_id} (text box still contains text)")
                return False
                
            # Verify post was successful (simple check: page loaded without error)
            try:
                post_page.wait_for_selector('div[role="status"]', timeout=3000)
            except:
                pass
                
            # Save screenshot of successful post
            try:
                from pathlib import Path
                screenshots_dir = Path("screenshots")
                screenshots_dir.mkdir(exist_ok=True)
                from datetime import datetime
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                post_page.screenshot(path=str(screenshots_dir / f"lead_{lead_id}_success_{timestamp}.png"))
                scanner_logger.info(f"Saved success screenshot: lead_{lead_id}_success_{timestamp}.png")
            except Exception as se:
                scanner_logger.debug(f"Could not save success screenshot: {se}")
                
            scanner_logger.info(f"Successfully posted comment inline for lead {lead_id}")
            return True
        
        except Exception as e:
            scanner_logger.error(f"Error posting comment inline for lead {lead_id}: {e}")
            try:
                from pathlib import Path
                screenshots_dir = Path("screenshots")
                screenshots_dir.mkdir(exist_ok=True)
                from datetime import datetime
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                post_page.screenshot(path=str(screenshots_dir / f"lead_{lead_id}_error_{timestamp}.png"))
                scanner_logger.info(f"Saved error screenshot: lead_{lead_id}_error_{timestamp}.png")
            except Exception as se:
                scanner_logger.debug(f"Could not save error screenshot: {se}")
            return False
        finally:
            if post_page:
                try:
                    post_page.close()
                except Exception as e:
                    scanner_logger.debug(f"Error closing post page: {e}")
            
    
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
            
            # Extract timestamp text
            time_text = ""
            time_selectors = [
                'span.x1lliihq a[role="link"] span',
                'span[id] a[role="link"] span',
                'abbr',
                'a[role="link"] > span',
                '[data-testid="post_timestamp"]'
            ]
            for selector in time_selectors:
                elem = post_elem.query_selector(selector)
                if elem:
                    time_text = elem.inner_text()
                    if time_text and len(time_text.strip()) > 0:
                        break
            
            return {
                "post_id": post_id,
                "post_url": post_url,
                "post_text": post_text,
                "author": author,
                "author_profile": author_profile,
                "group_name": group_name,
                "group_url": group_url,
                "timestamp": time_text
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
