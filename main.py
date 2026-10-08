import asyncio
import time
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="Flipkart Auto OTP & Login Bot")

# Secret Security Key
VALID_KEY = "Akshay12dev"

# Browser aur Active sessions store karne ke liye
playwright_instance = None
browser_instance = None
active_sessions = {}  # { "number": {"context": ctx, "page": page, "created_at": timestamp} }

@app.on_event("startup")
async def startup_event():
    global playwright_instance, browser_instance
    playwright_instance = await async_playwright().start()
    browser_instance = await playwright_instance.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu"
        ]
    )
    print(">>> Playwright Browser Engine Started successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    global playwright_instance, browser_instance
    if browser_instance:
        await browser_instance.close()
    if playwright_instance:
        await playwright_instance.stop()

# Auto session cleanup (agar koi 3 minute tak OTP na dale toh memory clear kare)
async def cleanup_old_sessions():
    current_time = time.time()
    for num, data in list(active_sessions.items()):
        if current_time - data["created_at"] > 180:  # 3 minutes expiry
            try:
                await data["context"].close()
            except:
                pass
            del active_sessions[num]
            print(f"[CLEANUP] Expired session destroyed for: {num}")

# ==========================================
# 1. SEND OTP ENDPOINT: /sent
# ==========================================
@app.get("/sent")
async def send_otp(number: str = Query(...), key: str = Query(...)):
    await cleanup_old_sessions()

    # 1. Key Verification
    if key != VALID_KEY:
        return JSONResponse(status_code=403, content={"status": "error", "message": "Key Galat hai! Access Denied."})

    number = number.strip().replace("+91", "").replace(" ", "")
    if len(number) != 10 or not number.isdigit():
        return JSONResponse(status_code=400, content={"status": "error", "message": "Kripya 10 digit ka valid number dalein."})

    # Purana session ho toh pehle clean karo
    if number in active_sessions:
        try:
            await active_sessions[number]["context"].close()
        except:
            pass
        del active_sessions[number]

    try:
        # Har request ke liye bilkul fresh & isolated context (Pura data clear state)
        context = await browser_instance.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915},
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()

        # Flipkart Login Open karna
        await page.goto("https://www.flipkart.com/account/login", wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(1.5)

        # Phone Number Input Box dhoondna
        input_selectors = ["input[type='tel']", "input[type='number']", "input[type='text']", "input[maxlength='10']"]
        input_box = None
        for sel in input_selectors:
            loc = page.locator(sel).first
            if await loc.is_visible():
                input_box = loc
                break

        if not input_box:
            await context.close()
            return JSONResponse(status_code=500, content={"status": "failed", "message": "Phone input field nahi mila!"})

        await input_box.click()
        await input_box.fill("")
        await input_box.type(number, delay=40)

        # Continue Button click karna
        btn_selectors = ["button:has-text('Continue')", "button:has-text('Request OTP')", "button[type='submit']"]
        continue_btn = None
        for b_sel in btn_selectors:
            b_loc = page.locator(b_sel).first
            if await b_loc.is_visible():
                continue_btn = b_loc
                break

        if not continue_btn:
            await context.close()
            return JSONResponse(status_code=500, content={"status": "failed", "message": "Continue button nahi mila!"})

        await continue_btn.click()

        # OTP Screen Check karna
        otp_sent = False
        indicators = ["text=Please enter the verification code", "text=verification code", "text=Resend code", "text=Trying to autocapture"]
        
        for _ in range(15):  # 15 seconds wait
            for ind in indicators:
                if await page.locator(ind).first.is_visible():
                    otp_sent = True
                    break
            if otp_sent:
                break
            await asyncio.sleep(1)

        if otp_sent:
            # Session ko save rakhein taaki /virifid par yehi page use ho sake
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
        else:
            await context.close()
            return JSONResponse(status_code=400, content={"status": "failed", "message": "OTP nahi bheja ja saka (Limit block ya Captcha issue)."})

    except Exception as e:
        if 'context' in locals():
            await context.close()
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

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
        # OTP Boxes fill karna
        otp_boxes = page.locator("input[maxlength='1']")
        boxes_count = await otp_boxes.count()

        if boxes_count >= 6:
            # 6 alag alag dibbe hain
            for idx in range(min(6, len(otp))):
                box = otp_boxes.nth(idx)
                await box.click()
                await box.fill(otp[idx])
        else:
            # Single input box ya keyboard type
            first_box = page.locator("input[type='tel'], input[type='number'], input[maxlength='6'], input").first
            await first_box.click()
            await page.keyboard.type(otp, delay=50)

        await asyncio.sleep(1)

        # "Verify" button click karna
        verify_btn = page.locator("button:has-text('Verify')").first
        if await verify_btn.is_visible():
            await verify_btn.click()

        # Check response: Login hua ya Expire/Invalid hai
        login_success = False
        error_msg = None

        for _ in range(10):  # 10 second wait
            # Agar login ho gaya toh login screen gayab ho jayegi ya URL badal jayega
            current_url = page.url
            if "login" not in current_url:
                login_success = True
                break

            # Error messages check
            if await page.locator("text=Incorrect OTP").first.is_visible() or await page.locator("text=Invalid OTP").first.is_visible():
                error_msg = "Invalid OTP (Galat OTP dala hai)"
                break
            if await page.locator("text=OTP expired").first.is_visible() or await page.locator("text=expired").first.is_visible():
                error_msg = "OTP Expired (OTP expire ho gaya hai)"
                break

            await asyncio.sleep(1)

        # Response tayyar karna
        if login_success:
            result = {
                "status": "success",
                "message": f"Login successfully completed for +91-{number}!",
                "login": True
            }
        else:
            result = {
                "status": "failed",
                "message": error_msg if error_msg else "Login failed or wrong OTP.",
                "login": False
            }

        return result

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    finally:
        # Pura data turant wipe out aur clear karna (Aapki requirement ke anusar)
        try:
            await context.close()
        except:
            pass
        if number in active_sessions:
            del active_sessions[number]
        print(f"[CLEANUP COMPLETE] Session, cookies aur storage cleared for: {number}")
