import os
import sys
import time
import asyncio
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

BROWSER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pw-browsers")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSER_DIR

app = FastAPI(title="Flipkart Mobile OTP Bot")

VALID_KEY = "Akshay12dev"
playwright_instance = None
browser_instance = None
active_sessions = {}

@app.on_event("startup")
async def startup_event():
    global playwright_instance, browser_instance
    print(">>> Starting Playwright Engine...")
    playwright_instance = await async_playwright().start()

    browser_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage"
    ]

    try:
        browser_instance = await playwright_instance.chromium.launch(headless=True, args=browser_args)
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        browser_instance = await playwright_instance.chromium.launch(headless=True, args=browser_args)

    print(">>> Playwright Browser Engine Ready!")

@app.on_event("shutdown")
async def shutdown_event():
    global playwright_instance, browser_instance
    if browser_instance:
        await browser_instance.close()
    if playwright_instance:
        await playwright_instance.stop()

# ==========================================
# 1. SEND OTP ENDPOINT: /sent
# ==========================================
@app.get("/sent")
async def send_otp(number: str = Query(...), key: str = Query(...)):
    # 1. Key Check
    if key != VALID_KEY:
        return JSONResponse(status_code=403, content={"status": "error", "message": "Key Galat hai! Access Denied."})

    phone_number = number.strip().replace("+91", "").replace(" ", "")
    if len(phone_number) != 10 or not phone_number.isdigit():
        return JSONResponse(status_code=400, content={"status": "error", "message": "10 digit ka valid number dalein."})

    # Purana context agar ho toh band karein
    if phone_number in active_sessions:
        try:
            await active_sessions[phone_number]["context"].close()
        except:
            pass
        del active_sessions[phone_number]

    try:
        # Aapke script ka exact Real Mobile Context
        context = await browser_instance.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915},
            is_mobile=True,
            has_touch=True,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9,hi;q=0.8"
            }
        )
        page = await context.new_page()

        target_url = "https://www.flipkart.com/account/login"
        print(f"[{phone_number}] Opening: {target_url}...")
        
        # 45 second timeout taaki Render hang na ho
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)

        # Aapke script ke exact selectors
        input_selectors = [
            "input[type='tel']",
            "input[type='number']",
            "input[type='text']",
            "input[maxlength='10']"
        ]

        input_box = None
        for selector in input_selectors:
            loc = page.locator(selector).first
            if await loc.is_visible():
                input_box = loc
                break

        if not input_box:
            await context.close()
            return JSONResponse(status_code=500, content={"status": "failed", "message": "FAILED: Mobile number input field nahi mila!"})

        # Number enter karna (with exact delay=50)
        await input_box.click()
        await input_box.fill("")
        await input_box.type(phone_number, delay=50)
        print(f"Number successfully dala gaya: {phone_number}")
        await page.wait_for_timeout(1000)

        # Continue button selectors (Aapke script ke anusaar)
        btn_selectors = [
            "button:has-text('Continue')",
            "button:has-text('Request OTP')",
            "button[type='submit']",
            "button:has-text('Proceed')"
        ]

        continue_btn = None
        for b_selector in btn_selectors:
            b_loc = page.locator(b_selector).first
            if await b_loc.is_visible():
                continue_btn = b_loc
                break

        if not continue_btn:
            await context.close()
            return JSONResponse(status_code=500, content={"status": "failed", "message": "FAILED: 'Continue' button nahi mila!"})

        await continue_btn.click()
        print("Continue button clicked. Waiting for OTP screen...")

        # Success indicators (Aapke script ke exact words)
        success_indicators = [
            "text=Please enter the verification code",
            "text=verification code",
            "text=Resend code",
            "text=Trying to autocapture",
            "input[maxlength='1']"
        ]

        otp_sent = False
        start_time = time.time()

        # 15 seconds wait loop
        while time.time() - start_time < 15:
            for indicator in success_indicators:
                if await page.locator(indicator).first.is_visible():
                    otp_sent = True
                    break
            if otp_sent:
                break
            await page.wait_for_timeout(1000)

        if otp_sent:
            # Session store karna taaki /virifid me yehi open page use ho
            active_sessions[phone_number] = {
                "context": context,
                "page": page,
                "created_at": time.time()
            }
            return {
                "status": "success",
                "message": f"Verification code/OTP sent to +91-{phone_number}!",
                "number": phone_number
            }
        else:
            await context.close()
            return JSONResponse(status_code=400, content={"status": "failed", "message": "FAILED: OTP screen load nahi hua (Blocked ya Captcha issue)."})

    except Exception as e:
        if 'context' in locals():
            await context.close()
        return JSONResponse(status_code=500, content={"status": "failed", "message": f"Error aaya: {str(e)}"})

# ==========================================
# 2. VERIFY OTP ENDPOINT: /virifid
# ==========================================
@app.get("/virifid")
async def verify_otp(number: str = Query(...), otp: str = Query(...)):
    phone_number = number.strip().replace("+91", "").replace(" ", "")
    otp = otp.strip()

    if phone_number not in active_sessions:
        return JSONResponse(status_code=404, content={"status": "failed", "message": "Session expire ho gaya ya nahi mila! Pehle /sent call karein."})

    session_data = active_sessions[phone_number]
    context = session_data["context"]
    page = session_data["page"]

    try:
        # OTP boxes me fill karna
        otp_boxes = page.locator("input[maxlength='1']")
        boxes_count = await otp_boxes.count()

        if boxes_count >= 6:
            for idx in range(min(6, len(otp))):
                await otp_boxes.nth(idx).fill(otp[idx])
        else:
            first_box = page.locator("input[type='tel'], input[type='number'], input[maxlength='6'], input").first
            await first_box.click()
            await page.keyboard.type(otp, delay=50)

        await page.wait_for_timeout(1000)

        # Verify button click
        verify_btn = page.locator("button:has-text('Verify')").first
        if await verify_btn.is_visible():
            await verify_btn.click()

        login_success = False
        error_msg = None

        # Check loop (6 seconds)
        for _ in range(12):
            await page.wait_for_timeout(500)

            # Agar URL change ho gaya ya login se bahar nikal gaya
            if "login" not in page.url:
                login_success = True
                break

            if await page.locator("text=Incorrect OTP, text=Invalid OTP").first.is_visible():
                error_msg = "Incorrect OTP (Galat OTP)"
                break
            if await page.locator("text=OTP expired, text=expired").first.is_visible():
                error_msg = "OTP Expired"
                break

        if login_success:
            return {"status": "success", "message": f"Login successful for +91-{phone_number}!", "login": True}
        else:
            return {"status": "failed", "message": error_msg if error_msg else "Login failed or wrong OTP.", "login": False}

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    finally:
        # User ka data, tab aur cache instant clear
        try:
            await context.close()
        except:
            pass
        if phone_number in active_sessions:
            del active_sessions[phone_number]
        print(f"[CLEANUP] Full tab wiped and closed for: {phone_number}")
