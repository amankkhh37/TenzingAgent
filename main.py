import sys
import logging
from src.database import Database
from src.scanner import FacebookScanner
from src.lead_scorer import LeadScorer
from src.commenter import FacebookCommenter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tenzing_growth.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    CLI entry point for scanning Facebook groups.
    Usage: python main.py <group_url1> <group_url2> ...
    """
    logger.info("Starting Tenzing Growth Agent")
    
    # Initialize components
    db = Database("tenzing_growth.db")
    lead_scorer = LeadScorer()
    scanner = FacebookScanner(db, lead_scorer, "./.facebook_session")
    
    # Get group URLs from command line or prompt user
    if len(sys.argv) > 1:
        group_urls = sys.argv[1:]
    else:
        print("Enter Facebook group URLs (one per line, empty line to finish):")
        group_urls = []
        while True:
            url = input().strip()
            if not url:
                break
            group_urls.append(url)
    
    if not group_urls:
        logger.warning("No group URLs provided")
        return
    
    # Run scanner
    try:
        scanner.run(group_urls)
        logger.info("Scanning completed successfully")
    except Exception as e:
        logger.error(f"Scanning failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
