import os
from flask import Flask, jsonify, render_template_string
import requests

app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fullbot Status</title>
  <style>
    body{font-family:system-ui,sans-serif;background:#101827;color:#f3f4f6;margin:0;padding:24px}
    main{max-width:650px;margin:8vh auto;background:#1d293b;border:1px solid #344256;border-radius:18px;padding:24px}
    h1{margin-top:0} p{line-height:1.6;color:#cbd5e1}
    button{background:#38bdf8;color:#082f49;border:0;border-radius:10px;padding:12px 18px;font-weight:700;font-size:16px}
    #result{margin-top:18px;padding:14px;background:#0f172a;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere}
  </style>
</head>
<body><main>
  <h1>Fullbot</h1>
  <p>Render deployment status and safe public-page connectivity check.</p>
  <p>This version does not submit phone numbers, request OTPs, or automate account login.</p>
  <button onclick="checkSite()">Check public site connection</button>
  <div id="result">Ready.</div>
</main>
<script>
async function checkSite(){
  const out=document.getElementById('result');
  out.textContent='Checking…';
  try{
    const r=await fetch('/check');
    const data=await r.json();
    out.textContent=JSON.stringify(data,null,2);
  }catch(e){out.textContent='Request failed: '+e.message;}
}
</script></body></html>
"""

@app.get("/")
def index():
    return render_template_string(PAGE)

@app.get("/health")
def health():
    return jsonify(status="ok", service="Fullbot", mode="safe-connectivity-check")

@app.get("/check")
def check_public_site():
    try:
        response = requests.get(
            "https://www.flipkart.com/",
            timeout=15,
            headers={"User-Agent": "Fullbot-Connectivity-Check/1.0"}
        )
        return jsonify(
            ok=response.status_code < 500,
            target="https://www.flipkart.com/",
            http_status=response.status_code,
            message="Public homepage connectivity checked; this does not test login or OTP delivery."
        ), 200
    except requests.RequestException as exc:
        return jsonify(
            ok=False,
            target="https://www.flipkart.com/",
            error=type(exc).__name__,
            message=str(exc)
        ), 502

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
