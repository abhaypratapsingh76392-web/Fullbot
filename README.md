# Fullbot — Render-ready safe version

This package provides a Render web service with:
- `/` — status page
- `/health` — health check for Render
- `/check` — checks connectivity to the public Flipkart homepage

It intentionally does **not** automate account login, submit phone numbers, request OTPs, or bypass anti-bot controls.

## Deploy from a phone
1. Upload these files to the root of your GitHub repository.
2. Open https://dashboard.render.com/
3. Choose **New + → Blueprint** if using `render.yaml`, or **New + → Web Service**.
4. Connect the repository.
5. If creating a Web Service manually, use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
6. Deploy, then open the generated Render URL. `/health` should return JSON with `"status":"ok"`.

Render free services may sleep when idle and are not guaranteed to run continuously.
