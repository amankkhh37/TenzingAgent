"""
Facebook Login Helper - Run this first to authenticate
"""
from playwright.sync_api import sync_playwright
from config import FACEBOOK_PROFILE_PATH, FACEBOOK_HEADLESS
from logger import scanner_logger

def login_to_facebook():
    """Open browser for Facebook login"""
    print("\n" + "="*60)
    print("🔐 FACEBOOK LOGIN HELPER")
    print("="*60)
    print("\nOpening Chrome browser for Facebook login...")
    print("Follow these steps:")
    print("  1. Wait for Chrome to open")
    print("  2. Log in to your Facebook account")
    print("  3. Accept any permission prompts")
    print("  4. Navigate to your travel group")
    print("  5. Close the browser when done")
    print("\nYour login will be saved for future scans.")
    print("="*60 + "\n")
    
    try:
        with sync_playwright() as p:
            # Open browser in NON-headless mode so user can log in
            browser = p.chromium.launch_persistent_context(
                FACEBOOK_PROFILE_PATH,
                headless=False,  # Show browser window
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--no-default-browser-check"
                ]
            )
            
            # Open Facebook
            page = browser.new_page()
            print("⏳ Navigating to Facebook...")
            page.goto("https://www.facebook.com", timeout=30000)
            
            print("\n✅ Browser is open! Please:")
            print("   1. Log in with your Facebook account")
            print("   2. Accept permission requests")
            print("   3. Visit your travel groups")
            print("   4. Type 'done' below and press Enter when finished")
            
            # Wait for user input
            user_input = input("\n>>> Enter 'done' when finished: ").strip().lower()
            
            if user_input == "done":
                browser.close()
                print("\n✅ Login saved! Your session is ready.")
                print("   Run the scanner: python scanner.py")
                return True
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = login_to_facebook()
    exit(0 if success else 1)
