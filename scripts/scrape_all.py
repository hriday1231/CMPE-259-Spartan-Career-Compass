"""run staff and event scrapers back to back"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scrape_events import main as scrape_events_main
from scrape_staff import main as scrape_staff_main


def main():
    print("=== Scraping Staff ===\n")
    scrape_staff_main()
    print("\n=== Scraping Events ===\n")
    scrape_events_main()
    print("\nDone. Events and staff are now loaded from the live Career Center site.")


if __name__ == "__main__":
    main()
