import sys
from playwright.sync_api import sync_playwright

def check_login_page():
    # Target URL
    target_url = "https://www.flipkart.com/account/login"

    with sync_playwright() as p:
        # Headless mode me browser launch karna
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            print(f"Opening URL: {target_url}...")
            # Page load hone ka wait karein (timeout 30 seconds)
            response = page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

            # Check response status code
            if response and response.status < 400:
                print(f"Success: Page successfully load ho gaya (Status code: {response.status})")
                browser.close()
                sys.exit(0)  # GitHub Action PASS hoga
            else:
                status = response.status if response else "Unknown"
                print(f"Failed: Page response error (Status code: {status})")
                browser.close()
                sys.exit(1)  # GitHub Action FAIL hoga

        except Exception as e:
            print(f"Error aaya: {str(e)}")
            browser.close()
            sys.exit(1)  # GitHub Action FAIL hoga

if __name__ == "__main__":
    check_login_page()
