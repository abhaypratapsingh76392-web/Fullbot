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
    button{background:#38bdf8;color:#082f49;border:0;border-radius:10px;padding:12px 18px;font-weight:700;font-size:16px;margin-right:8px;margin-top:8px}
    #result{margin-top:18px;padding:14px;background:#0f172a;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere}
  </style>
</head>
<body><main>
  <h1>Fullbot — Safe Status</h1>
  <p>Ye app sirf public pages ki reachability check karta hai. Koi login/OTP automation nahi.</p>
  <button onclick="hit('/check')">Check Flipkart homepage</button>
  <button onclick="hit('/check-login')">Check Flipkart login page</button>
  <button onclick="hit('/health')">Health</button>
  <div id="result">Ready.</div>
</main>
<script>
async function hit(path){
  const out=document.getElementById('result');
  out.textContent='Checking '+path+' …';
  try{
    const r=await fetch(path);
    const data=await r.json();
    out.textContent=JSON.stringify(data,null,2);
  }catch(e){out.textContent='Request failed: '+e.message;}
}
</script></body></html>
"""

def probe(url):
    try:
        r = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "Fullbot-Connectivity-Check/1.0"},
            allow_redirects=True,
        )
        return {
            "ok": r.status_code == 200,
            "target": url,
            "final_url": r.url,
            "http_status": r.status_code,
            "latency_ms": int(r.elapsed.total_seconds() * 1000),
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "target": url,
            "error": type(exc).__name__,
            "message": str(exc),
        }

@app.get("/")
def index():
    return render_template_string(PAGE)

@app.get("/health")
def health():
    return jsonify(status="ok", service="Fullbot", mode="connectivity-only")

@app.get("/check")
def check_home():
    return jsonify(probe("https://www.flipkart.com/")), 200

@app.get("/check-login")
def check_login():
    data = probe("https://www.flipkart.com/account/login")
    data["note"] = "Sirf page reachable hai ya nahi check. Koi number submit nahi hota."
    return jsonify(data), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
