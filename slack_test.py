import os
import requests
from dotenv import load_dotenv

load_dotenv()

webhook_url = os.getenv("SLACK_WEBHOOK_URL")

if not webhook_url:
    raise ValueError("SLACK_WEBHOOK_URL is not set")

message = {
    "text": "🚀 AWS Cost Optimizer - Slack integration is working!"
}

response = requests.post(
    webhook_url,
    json=message,
    timeout=10
)

response.raise_for_status()

print("Slack message sent successfully!")
print("Status Code:", response.status_code)