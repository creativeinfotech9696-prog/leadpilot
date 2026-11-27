"""Prints a Clerk session token for the test user (creates it if needed). Usage: python clerk_token.py [ticket]"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
SK = os.environ["CLERK_SECRET_KEY"]
EMAIL = "ops+clerk_test@example.com"


def bapi(path, body=None, method="POST"):
    req = urllib.request.Request("https://api.clerk.com/v1" + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers={"Authorization": "Bearer " + SK, "Content-Type": "application/json", "User-Agent": "emergent-test"})
    return json.load(urllib.request.urlopen(req))


users = bapi("/users?" + urllib.parse.urlencode({"email_address": EMAIL}), method="GET")
user = users[0] if users else bapi("/users", {"email_address": [EMAIL], "password": "Test-pass-12345!", "skip_password_checks": True})
if len(sys.argv) > 1 and sys.argv[1] == "ticket":
    print(bapi("/sign_in_tokens", {"user_id": user["id"], "expires_in_seconds": 1800})["token"])
else:
    session = bapi("/sessions", {"user_id": user["id"]})
    print(bapi(f"/sessions/{session['id']}/tokens", {"expires_in_seconds": 3600})["jwt"])
