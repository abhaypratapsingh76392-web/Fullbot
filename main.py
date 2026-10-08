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

app = FastAPI(title="Turbo Flipkart OTP & Login Bot")

VALID_KEY = "Akshay12dev"
playwright_instance = None
browser_instance = None
active_sessions = {}

# Resource blocker: Images, Fonts aur Trackers ko block karega taaki speed 10x ho jaye
async def block_heavy_resources(route):
    req_type = route.request.resource_type
    req_url = route.request.url.lower()
    if req_type in ["image", "media", "font"] or any(x in req_url for x in ["analytics", "tracker", "doubleclick", "google-analytics"]):
        await route.abort()
    else:
        await route.continue_()

@app.on_event("startup")
async def startup_event():
    global playwright_instance, browser_instance
    print(">>> Starting Ultra-Fast Playwright Engine...")
    playwright_instance = await async_playwright().start()

    browser_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--blink-settings=imagesEnabled=false", # Direct browser-level image disable
        "--disable-extensions"
    ]

    try:
        browser_instance = await playwright_instance.chromium.launch(headless=True, args=browser_args)
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        browser_instance = await playwright_instance.chromium.launch(headless=True, args=browser_args)

    print(">>> Turbo Browser Ready!")

@app.on_event("shutdown")
async def shutdown_event():
    global playwright_instance, browser_instance
    if browser_instance:
        await browser_instance.close()
    if playwright_instance:
        await playwright_instance.stop()

async def cleanup_old_sessions():
    now = time.time()
    for num, data in list(active_sessions.items()):
        if now - data["created_at"] > 180: # 3 min expiry
            try:
                await data["context"].close()
            except:
                pass
            del active_sessions[num]

# ==========================================
# 1. TURBO SEND OTP: /sent (Target: ~2-3s)
# ==========================================
@app.get("/sent")
async def send_otp(number: str = Query(...), key: str = Query(...)):
    asyncio.create_task(cleanup_old_sessions())

    if key != VALID_KEY:
        return JSONResponse(status_code=403, content={"status": "error", "message": "Key Galat hai!"})

    number = number.strip().replace("+91", "").replace(" ", "")
    if len(number) != 10 or not number.isdigit():
        return JSONResponse(status_code=400, content={"status": "error", "message": "Valid 10 digit number dalein."})

    # Purana session ho toh remove
    if number in active_sessions:
        try:
            await active_sessions[number]["context"].close()
        except:
            pass
        del active_sessions[number]

    try:
        context = await browser_instance.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915},
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()

        # Heavy files route block karna
        await page.route("**/*", block_heavy_resources)

        # Fast page load (domcontentloaded)
        await page.goto("https://www.flipkart.com/account/login", wait_until="domcontentloaded", timeout=15000)

        # Phone input box par direct instant fill (No delay)
        phone_input = page.locator("input[type='tel'], input[maxlength='10'], input[type='text']").first
        await phone_input.wait_for(state="visible", timeout=4000)
        await phone_input.fill(number)

        # Continue button click
        btn = page.locator("button:has-text('Continue'), button:has-text('Request OTP'), button[type='submit']").first
        await btn.click()

        # Event-based wait: Jaise hi OTP indicator screen par aayega turant response trigger hoga
        otp_screen = page.locator("text=Please enter the verification code, text=verification code, text=Resend code, text=Trying to autocapture").first
        await otp_screen.wait_for(state="visible", timeout=6000)

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
        return JSONResponse(status_code=500, content={"status": "failed", "message": f"OTP nahi bheja ja saka: {str(e)}"})

# ==========================================
# 2. TURBO VERIFY OTP: /virifid (Target: ~1-2s)
# ==========================================
@app.get("/virifid")
async def verify_otp(number: str = Query(...), otp: str = Query(...)):
    number = number.strip().replace("+91", "").replace(" ", "")
    otp = otp.strip()

    if number not in active_sessions:
        return JSONResponse(status_code=404, content={"status": "failed", "message": "Session nahi mila ya expire ho gaya! Pehle /sent call karein."})

    session_data = active_sessions[number]
    context = session_data["context"]
    page = session_data["page"]

    try:
        # OTP Boxes instant fill
        otp_boxes = page.locator("input[maxlength='1']")
        boxes_count = await otp_boxes.count()

        if boxes_count >= 6:
            for idx in range(min(6, len(otp))):
                await otp_boxes.nth(idx).fill(otp[idx])
        else:
            first_box = page.locator("input[type='tel'], input[type='number'], input[maxlength='6'], input").first
            await first_box.fill(otp)

        # "Verify" button instant click
        verify_btn = page.locator("button:has-text('Verify')").first
        await verify_btn.click()

        # Ultra-fast check: Check if URL changed or error showed up
        login_success = False
        error_msg = None

        for _ in range(8):  # 8 x 300ms = Max 2.4 seconds
            await asyncio.sleep(0.3)
            
            if "login" not in page.url:
                login_success = True
                break

            if await page.locator("text=Incorrect OTP, text=Invalid OTP").first.is_visible():
                error_msg = "Invalid OTP (Galat OTP)"
                break
            if await page.locator("text=OTP expired, text=expired").first.is_visible():
                error_msg = "OTP Expired"
                break

        if login_success:
            return {"status": "success", "message": f"Login successful for +91-{number}!", "login": True}
        else:
            return {"status": "failed", "message": error_msg if error_msg else "Login failed / Wrong OTP", "login": False}

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    finally:
        # Zero-delay cleanup: memory & cookies instant clear
        try:
            await context.close()
        except:
            pass
        if number in active_sessions:
            del active_sessions[number]
        print(f"[TURBO CLEANUP] Tab closed & full data cleared for: {number}")
