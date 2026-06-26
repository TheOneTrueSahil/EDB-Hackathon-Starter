#!/usr/bin/env python3
import requests
import json
import uuid

URL = "http://127.0.0.1:8080/api/chat"
SESSION_ID = f"test-goal-session-{uuid.uuid4().hex[:8]}"
USER_ID = "test-user-alice"

def send_message(msg):
    print(f"\nUser: {msg}")
    payload = {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "message": msg
    }
    response = requests.post(URL, json=payload)
    if response.status_code == 200:
        res_json = response.json()
        print(f"Agent: {res_json['response']}")
    else:
        print(f"Error {response.status_code}: {response.text}")

def main():
    # 1. Greet
    send_message("Hello!")

    # 2. Verify identity
    send_message("My customer ID is C001")

    # 3. Request savings goal
    send_message("I'd like to set a savings goal: I want to save £5,000 for a holiday next year.")

if __name__ == "__main__":
    main()
