# scratch/test_osint.py
import sys
import os

# Add root folder to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, scrape_company_cached

# Create Flask application context so we can run functions depending on app context
with app.app_context():
    try:
        print("Testing scrape_company_cached on demo-corp.com...")
        profile = scrape_company_cached("demo-corp.com")
        print("Scrape successful! Profile:")
        print(profile)
    except Exception as e:
        import traceback
        print("Exception occurred:")
        traceback.print_exc()
