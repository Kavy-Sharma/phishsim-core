import requests

routes = [
    "/",
    "/reports-demo",
    "/terms",
    "/privacy",
    "/acceptable-use",
    "/consent-policy"
]

port = 5050
base_url = f"http://127.0.0.1:{port}"

print("Checking routes...")
all_passed = True
for r in routes:
    url = base_url + r
    try:
        resp = requests.get(url, timeout=5)
        print(f"GET {r} -> status code {resp.status_code}")
        if resp.status_code != 200:
            print(f"FAILED: GET {r} returned {resp.status_code}")
            all_passed = False
    except Exception as e:
        print(f"FAILED: GET {r} raised exception: {e}")
        all_passed = False

# Test POST to /join-beta
try:
    resp = requests.post(base_url + "/join-beta", data={"email": "test@example.com"}, allow_redirects=False, timeout=5)
    print(f"POST /join-beta -> status code {resp.status_code} (Redirect: {resp.headers.get('Location')})")
    if resp.status_code not in (200, 302):
        print(f"FAILED: POST /join-beta returned {resp.status_code}")
        all_passed = False
except Exception as e:
    print(f"FAILED: POST /join-beta raised exception: {e}")
    all_passed = False

if all_passed:
    print("ALL ROUTES PASSED!")
else:
    print("SOME ROUTES FAILED!")
