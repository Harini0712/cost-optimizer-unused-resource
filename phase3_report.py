import boto3
from datetime import datetime

ce = boto3.client("ce", region_name="us-east-1")


# August 2026 cost
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


print("\n========== AWS COST OPTIMIZATION REPORT ==========\n")


# -----------------------------
# COST SUMMARY
# -----------------------------

print("AUGUST 2026 COST\n")

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
            print(f"{service}: ${amount:.2f}")

        total_cost += amount


print("----------------------------------------")
print(f"TOTAL COST: ${max(total_cost, 0):.2f}")


# -----------------------------
# RESOURCE FINDINGS
# -----------------------------

ec2 = boto3.client("ec2")

# Stopped EC2
stopped_response = ec2.describe_instances(
    Filters=[
        {
            "Name": "instance-state-name",
            "Values": ["stopped"]
        }
    ]
)

stopped_count = 0

for reservation in stopped_response["Reservations"]:
    stopped_count += len(reservation["Instances"])


# Unattached EBS
ebs_response = ec2.describe_volumes(
    Filters=[
        {
            "Name": "status",
            "Values": ["available"]
        }
    ]
)

unattached_ebs_count = len(ebs_response["Volumes"])


# Unused EIP
eip_response = ec2.describe_addresses()

unused_eip_count = 0

for address in eip_response["Addresses"]:

    if "AssociationId" not in address:
        unused_eip_count += 1


# Snapshots
snapshot_response = ec2.describe_snapshots(
    OwnerIds=["self"]
)

snapshot_count = len(snapshot_response["Snapshots"])


print("\n\nRESOURCE FINDINGS\n")

print("Stopped EC2:", stopped_count)
print("Unattached EBS:", unattached_ebs_count)
print("Unused EIP:", unused_eip_count)
print("Snapshots:", snapshot_count)


# -----------------------------
# COMPUTE OPTIMIZER
# -----------------------------

print("\n\nCOMPUTE OPTIMIZER\n")

optimizer = boto3.client(
    "compute-optimizer",
    region_name="ap-south-1"
)

try:

    optimizer_response = (
        optimizer.get_ec2_instance_recommendations()
    )

    recommendations = optimizer_response.get(
        "instanceRecommendations",
        []
    )

    if recommendations:

        print(
            "Recommendations:",
            len(recommendations)
        )

        for recommendation in recommendations:

            finding = recommendation["finding"]

            print("Finding:", finding)

    else:

        print("Recommendations: 0")
        print(
            "Status: No recommendation data available"
        )

except Exception as error:

    print("Unable to retrieve Compute Optimizer data.")
    print("Reason:", error)


print("\n===================================================")