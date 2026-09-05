import os
import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# Slack
# -----------------------------
webhook_url = os.getenv("SLACK_WEBHOOK_URL")

if not webhook_url:
    raise ValueError("SLACK_WEBHOOK_URL is not set")


# -----------------------------
# AWS Clients
# -----------------------------
ce = boto3.client("ce", region_name="us-east-1")
ec2 = boto3.client("ec2")
optimizer = boto3.client(
    "compute-optimizer",
    region_name="ap-south-1"
)


# -----------------------------
# Cost Explorer
# -----------------------------
response = ce.get_cost_and_usage(
    TimePeriod={
        "Start": "2026-08-01",
        "End": "2026-09-01"
    },
    Granularity="MONTHLY",
    Metrics=["UnblendedCost"],
    GroupBy=[
        {
            "Type": "DIMENSION",
            "Key": "SERVICE"
        }
    ]
)

cost_lines = []
total_cost = 0

for result in response["ResultsByTime"]:
    for group in result["Groups"]:

        service = group["Keys"][0]

        amount = float(
            group["Metrics"]["UnblendedCost"]["Amount"]
        )

        if abs(amount) < 0.005:
            amount = 0

        if amount > 0:
            cost_lines.append(
                f"• {service}: ${amount:.2f}"
            )

        total_cost += amount


# -----------------------------
# Resource Findings
# -----------------------------

# Stopped EC2
stopped_response = ec2.describe_instances(
    Filters=[
        {
            "Name": "instance-state-name",
            "Values": ["stopped"]
        }
    ]
)

stopped_count = sum(
    len(reservation["Instances"])
    for reservation in stopped_response["Reservations"]
)


# Unattached EBS
ebs_response = ec2.describe_volumes(
    Filters=[
        {
            "Name": "status",
            "Values": ["available"]
        }
    ]
)

unattached_ebs_count = len(
    ebs_response["Volumes"]
)


# Unused EIP
eip_response = ec2.describe_addresses()

unused_eip_count = sum(
    1
    for address in eip_response["Addresses"]
    if "AssociationId" not in address
)


# Snapshots
snapshot_response = ec2.describe_snapshots(
    OwnerIds=["self"]
)

snapshot_count = len(
    snapshot_response["Snapshots"]
)


# -----------------------------
# Compute Optimizer
# -----------------------------

try:
    optimizer_response = (
        optimizer.get_ec2_instance_recommendations()
    )

    recommendations = optimizer_response.get(
        "instanceRecommendations",
        []
    )

    recommendation_count = len(recommendations)

except Exception:
    recommendation_count = 0


# -----------------------------
# Slack Message
# -----------------------------

cost_text = "\n".join(cost_lines)

if not cost_text:
    cost_text = "• No positive AWS service cost found"


message = {
    "text": f"""
🚨 *AWS Cost Optimization Report*

📊 *August 2026 Cost*

{cost_text}

🔍 *Resource Findings*

• Stopped EC2: {stopped_count}
• Unattached EBS: {unattached_ebs_count}
• Unused EIP: {unused_eip_count}
• Snapshots: {snapshot_count}

⚙️ *Compute Optimizer*

• Recommendations: {recommendation_count}

💡 *Action Required*

Review the flagged resources and remove unused resources where appropriate.
"""
}


# -----------------------------
# Send to Slack
# -----------------------------

slack_response = requests.post(
    webhook_url,
    json=message,
    timeout=10
)

slack_response.raise_for_status()

print("AWS Cost Optimization report sent to Slack!")
print("Status Code:", slack_response.status_code)