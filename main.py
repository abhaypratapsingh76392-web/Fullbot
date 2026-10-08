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

app = FastAPI(title="Stable Flipkart Multi-User Bot")

VALID_KEY = "Akshay12dev"
playwright_instance = None
browser_instance = None

# Har user ka data isolate rakhne ke liye dict: { "number": { "context": ..., "page": ..., "time": ... } }
active_sessions = {}

@app.on_event("startup")
async def startup_event():
    global playwright_instance, browser_instance
    print(">>> Starting Playwright Browser...")
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

    print(">>> Browser Engine Live & Ready for Multi-User Requests!")

@app.on_event("shutdown")
async def shutdown_event():
    global playwright_instance, browser_instance
    if browser_instance:
        await browser_instance.close()
    if playwright_instance:
        await playwright_instance.stop()

# Jo session 3 minute purane ho jayein unko RAM se delete karna
async def auto_clean_expired():
    now = time.time()
    for num, data in list(active_sessions.items()):
        if now - data["created_at"] > 180:
            try:
                await data["context"].close()
            except:
                pass
            del active_sessions[num]
            print(f"[AUTO-CLEAN] Expired session wiped: {num}")

# ==========================================
# 1. SEND OTP ENDPOINT: /sent
# ==========================================
@app.get("/sent")
async def send_otp(number: str = Query(...), key: str = Query(...)):
    # Background me purane dead sessions clean karo
    asyncio.create_task(auto_clean_expired())

    if key != VALID_KEY:
        return JSONResponse(status_code=403, content={"status": "error", "message": "Key Galat hai! Access Denied."})

    number = number.strip().replace("+91", "").replace(" ", "")
    if len(number) != 10 or not number.isdigit():
        return JSONResponse(status_code=400, content={"status": "error", "message": "10 digit valid phone number dalein."})

    # Agar ye number pehle se active hai toh purana context band karke naya banayein
    if number in active_sessions:
        try:
            await active_sessions[number]["context"].close()
        except:
            pass
        del active_sessions[number]

    try:
        # Har user ke liye ek alag, fresh, private container (isolated cookies & cache)
        context = await browser_instance.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915},
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()

        # Flipkart Login Page Load (15s timeout Render ke slow CPU ke liye)
        await page.goto("https://www.flipkart.com/account/login", wait_until="domcontentloaded", timeout=25000)

        # Phone Number Input dhoondna
        phone_input = page.locator("input[type='tel'], input[maxlength='10'], input[type='text']").first
        await phone_input.wait_for(state="visible", timeout=12000)
        await phone_input.click()
        await phone_input.fill("")
        await phone_input.type(number, delay=30)

        # Continue button click
        btn = page.locator("button:has-text('Continue'), button:has-text('Request OTP'), button[type='submit']").first
        await btn.wait_for(state="visible", timeout=5000)
        await btn.click()

        # OTP Sent Screen ka intezar
        otp_screen = page.locator("text=Please enter the verification code, text=verification code, text=Resend code, text=Trying to autocapture").first
        await otp_screen.wait_for(state="visible", timeout=10000)

        # User ka session save karein
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
        return JSONResponse(status_code=500, content={"status": "failed", "message": f"OTP request fail hui: {str(e)}"})

# ==========================================
# 2. VERIFY OTP ENDPOINT: /virifid
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
        # OTP Boxes me enter karein
        otp_boxes = page.locator("input[maxlength='1']")
        boxes_count = await otp_boxes.count()

        if boxes_count >= 6:
            for idx in range(min(6, len(otp))):
                await otp_boxes.nth(idx).fill(otp[idx])
        else:
            first_box = page.locator("input[type='tel'], input[type='number'], input[maxlength='6'], input").first
            await first_box.fill(otp)

        await asyncio.sleep(0.5)

        # Verify button click
        verify_btn = page.locator("button:has-text('Verify')").first
        if await verify_btn.is_visible():
            await verify_btn.click()

        # Check response: Login hua ya fail
        login_success = False
        error_msg = None

        for _ in range(12):  # 12 x 0.5s = 6 seconds max check
            await asyncio.sleep(0.5)

            if "login" not in page.url:
                login_success = True
                break

            if await page.locator("text=Incorrect OTP, text=Invalid OTP").first.is_visible():
                error_msg = "Invalid OTP (Galat OTP dala hai)"
                break
            if await page.locator("text=OTP expired, text=expired").first.is_visible():
                error_msg = "OTP Expired (OTP ka samay samapt)"
                break

        if login_success:
            return {"status": "success", "message": f"Login successful for +91-{number}!", "login": True}
        else:
            return {"status": "failed", "message": error_msg if error_msg else "Login failed / Galat OTP", "login": False}

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    finally:
        # Instant Full Wipe: Session, tab, cookies aur storage turant clear
        try:
            await context.close()
        except:
            pass
        if number in active_sessions:
            del active_sessions[number]
        print(f"[SESSION WIPED] Data and browser context wiped clean for: {number}")
