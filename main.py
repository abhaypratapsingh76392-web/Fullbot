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

app = FastAPI(title="Flipkart Bot")

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
        "--disable-dev-shm-usage",
        "--disable-gpu"
    ]

    try:
        browser_instance = await playwright_instance.chromium.launch(headless=True, args=browser_args)
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        browser_instance = await playwright_instance.chromium.launch(headless=True, args=browser_args)

    print(">>> Browser Engine Live!")

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
    if key != VALID_KEY:
        return JSONResponse(status_code=403, content={"status": "error", "message": "Key Galat hai!"})

    number = number.strip().replace("+91", "").replace(" ", "")
    if len(number) != 10 or not number.isdigit():
        return JSONResponse(status_code=400, content={"status": "error", "message": "10 digit valid number dalein."})

    if number in active_sessions:
        try:
            await active_sessions[number]["context"].close()
        except:
            pass
        del active_sessions[number]

    try:
        # Wahi Desktop context jo GitHub Actions me success hua tha
        context = await browser_instance.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        print(f"[{number}] Opening Flipkart Login...")
        await page.goto("https://www.flipkart.com/account/login", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # Check page status (Debugging ke liye)
        title = await page.title()
        print(f"[{number}] Page Loaded! Title: {title}")

        if "access denied" in title.lower() or "blocked" in title.lower():
            await context.close()
            return JSONResponse(status_code=403, content={"status": "failed", "message": "Flipkart ne Render IP ko temporarily block kiya hai."})

        # Desktop Flipkart input selectors
        phone_input = page.locator("input[class*='_2IX_2-'], input[type='text'], input[autocomplete='off']").first
        await phone_input.wait_for(state="visible", timeout=15000)
        
        await phone_input.click()
        await phone_input.fill("")
        await phone_input.type(number, delay=50)

        # Desktop Continue / Request OTP button
        btn = page.locator("button:has-text('Request OTP'), button:has-text('Continue'), button[type='submit']").first
        await btn.wait_for(state="visible", timeout=5000)
        await btn.click()

        # OTP Sent Screen indicator
        otp_screen = page.locator("text=Please enter the verification code, text=verification code, text=Resend code, text=Enter OTP").first
        await otp_screen.wait_for(state="visible", timeout=12000)

        active_sessions[number] = {
            "context": context,
            "page": page,
            "created_at": time.time()
        }

        return {
            "status": "success",
            "message": f"OTP successfully sent to +91-{number}",
            "number": number
        }

    except Exception as e:
        if 'context' in locals():
            await context.close()
        return JSONResponse(status_code=500, content={"status": "failed", "message": f"OTP error: {str(e)}"})

# ==========================================
# 2. VERIFY OTP ENDPOINT: /virifid
# ==========================================
@app.get("/virifid")
async def verify_otp(number: str = Query(...), otp: str = Query(...)):
    number = number.strip().replace("+91", "").replace(" ", "")
    otp = otp.strip()

    if number not in active_sessions:
        return JSONResponse(status_code=404, content={"status": "failed", "message": "Session nahi mila ya expire ho gaya!"})

    session_data = active_sessions[number]
    context = session_data["context"]
    page = session_data["page"]

    try:
        # OTP input handle karna
        otp_boxes = page.locator("input[maxlength='1']")
        boxes_count = await otp_boxes.count()

        if boxes_count >= 6:
            for idx in range(min(6, len(otp))):
                await otp_boxes.nth(idx).fill(otp[idx])
        else:
            first_box = page.locator("input[type='tel'], input[type='number'], input[maxlength='6'], input").first
            await first_box.fill(otp)

        await asyncio.sleep(0.5)

        verify_btn = page.locator("button:has-text('Verify'), button:has-text('Login')").first
        if await verify_btn.is_visible():
            await verify_btn.click()

        login_success = False
        error_msg = None

        for _ in range(10):
            await asyncio.sleep(0.5)

            if "login" not in page.url:
                login_success = True
                break

            if await page.locator("text=Incorrect OTP, text=Invalid OTP").first.is_visible():
                error_msg = "Galat OTP"
                break
            if await page.locator("text=OTP expired, text=expired").first.is_visible():
                error_msg = "OTP Expired"
                break

        if login_success:
            return {"status": "success", "message": f"Login successful for {number}!", "login": True}
        else:
            return {"status": "failed", "message": error_msg if error_msg else "Login failed / Wrong OTP", "login": False}

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    finally:
        # Full clear on finish
        try:
            await context.close()
        except:
            pass
        if number in active_sessions:
            del active_sessions[number]
