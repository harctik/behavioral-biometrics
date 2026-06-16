"""Quick test: hit the forgot-password endpoint and check response."""
import json, urllib.request

url = "https://behavioral-biometrics-cp5l.onrender.com/api/v1/auth/forgot-password"
body = json.dumps({"email": "harthikanand90@gmail.com"}).encode("utf-8")

req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(f"Status: {resp.status}")
        print(f"Response: {resp.read().decode()}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(f"Response: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
