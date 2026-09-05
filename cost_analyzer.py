import boto3
from datetime import date, timedelta

ce = boto3.client("ce", region_name="us-east-1")

today = date.today()
start = today.replace(day=1)
end = today + timedelta(days=1)

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

print("\n========== AWS COST REPORT ==========\n")

total = 0

for result in response["ResultsByTime"]:

    for group in result["Groups"]:

        service = group["Keys"][0]
        amount = float(
            group["Metrics"]["UnblendedCost"]["Amount"]
        )

        total += amount

        print(f"{service}: ${amount:.2f}")

print("\n-------------------------------------")
print(f"TOTAL AWS COST: ${total:.2f}")
print("=====================================\n")