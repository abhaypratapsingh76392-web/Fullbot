import sys
import time
from playwright.sync_api import sync_playwright

def flipkart_otp_bot():
    phone_number = "9335565511"
    target_url = "https://www.flipkart.com/account/login"

    with sync_playwright() as p:
        # Anti-detection arguments ke saath browser launch
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        # Real mobile browser emulate karna (taaki OTP page easily trigger ho)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915},
            is_mobile=True,
            has_touch=True
        )
        page = context.new_page()

        try:
            print(f"[1/4] Flipkart login page open ho raha hai: {target_url}...")
            page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(2000)

            # Mobile number input field dhoondna
            print("[2/4] Phone number input box dhoonda ja raha hai...")
            input_box = None
            input_selectors = [
                "input[type='tel']",
                "input[type='number']",
                "input[type='text']",
                "input[maxlength='10']"
            ]

            for selector in input_selectors:
                loc = page.locator(selector).first
                if loc.is_visible():
                    input_box = loc
                    break

            if not input_box:
                print("FAILED: Mobile number input field nahi mila!")
                browser.close()
                sys.exit(1)

            # Number enter karna
            input_box.click()
            input_box.fill("")
            input_box.type(phone_number, delay=50)
            print(f"Number successfully dala gaya: {phone_number}")
            page.wait_for_timeout(1000)

            # Continue button par click karna
            print("[3/4] 'Continue' button click kiya ja raha hai...")
            continue_btn = None
            btn_selectors = [
                "button:has-text('Continue')",
                "button:has-text('Request OTP')",
                "button[type='submit']",
                "button:has-text('Proceed')"
            ]

            for b_selector in btn_selectors:
                b_loc = page.locator(b_selector).first
                if b_loc.is_visible():
                    continue_btn = b_loc
                    break

            if not continue_btn:
                print("FAILED: 'Continue' button nahi mila!")
                browser.close()
                sys.exit(1)

            continue_btn.click()
            print("Continue button clicked. Waiting for OTP screen...")

            # OTP verification screen check karna
            print("[4/4] Verification check: OTP send hua ya nahi...")
            success_indicators = [
                "text=Please enter the verification code",
                "text=verification code",
                "text=Resend code",
                "text=Trying to autocapture",
                "input[maxlength='1']"
            ]

            otp_sent = False
            start_time = time.time()

            # 15 seconds tak wait karega verification screen aane ka
            while time.time() - start_time < 15:
                for indicator in success_indicators:
                    if page.locator(indicator).first.is_visible():
                        otp_sent = True
                        break
                if otp_sent:
                    break
                page.wait_for_timeout(1000)

            if otp_sent:
                print(f"\n==========================================")
                print(f"SUCCESS: Verification code/OTP sent to +91-{phone_number}!")
                print(f"==========================================\n")
                browser.close()
                sys.exit(0)  # GitHub Action PASS (Green Tick)
            else:
                print("\nFAILED: OTP screen load nahi hua (Blocked ya Captcha issue).")
                page.screenshot(path="failure_debug.png")
                browser.close()
                sys.exit(1)  # GitHub Action FAIL (Red Cross)

        except Exception as e:
            print(f"Error: {str(e)}")
            browser.close()
            sys.exit(1)

if __name__ == "__main__":
    flipkart_otp_bot()
