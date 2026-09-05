import boto3
from datetime import datetime, timezone


# AWS clients
ec2 = boto3.client("ec2", region_name="ap-south-1")
dynamodb = boto3.resource(
    "dynamodb",
    region_name="ap-south-1"
)

table = dynamodb.Table("aws-cost-optimization")


def save_finding(resource_id, resource_type, status, recommendation):
    item = {
        "resource_id": resource_id,
        "resource_type": resource_type,
        "status": status,
        "recommendation": recommendation,
        "scanned_at": datetime.now(timezone.utc).isoformat()
    }

    table.put_item(Item=item)

    print(f"Saved: {resource_type} | {resource_id}")


# --------------------------------
# 1. STOPPED EC2
# --------------------------------

response = ec2.describe_instances(
    Filters=[
        {
            "Name": "instance-state-name",
            "Values": ["stopped"]
        }
    ]
)

for reservation in response["Reservations"]:
    for instance in reservation["Instances"]:

        instance_id = instance["InstanceId"]
        instance_type = instance["InstanceType"]

        save_finding(
            instance_id,
            "EC2",
            "STOPPED",
            f"Review stopped {instance_type} instance"
        )


# --------------------------------
# 2. UNATTACHED EBS
# --------------------------------

response = ec2.describe_volumes(
    Filters=[
        {
            "Name": "status",
            "Values": ["available"]
        }
    ]
)

for volume in response["Volumes"]:

    volume_id = volume["VolumeId"]
    size = volume["Size"]
    volume_type = volume["VolumeType"]

    save_finding(
        volume_id,
        "EBS",
        "UNATTACHED",
        f"Review unused {size} GB {volume_type} volume"
    )


# --------------------------------
# 3. UNUSED ELASTIC IP
# --------------------------------

response = ec2.describe_addresses()

for address in response["Addresses"]:

    if "AssociationId" not in address:

        allocation_id = address["AllocationId"]
        public_ip = address["PublicIp"]

        save_finding(
            allocation_id,
            "EIP",
            "UNUSED",
            f"Review unused Elastic IP {public_ip}"
        )


# --------------------------------
# 4. SNAPSHOTS
# --------------------------------

response = ec2.describe_snapshots(
    OwnerIds=["self"]
)

for snapshot in response["Snapshots"]:

    snapshot_id = snapshot["SnapshotId"]
    size = snapshot["VolumeSize"]
    start_time = snapshot["StartTime"]

    age_days = (
        datetime.now(timezone.utc) - start_time
    ).days

    save_finding(
        snapshot_id,
        "SNAPSHOT",
        "COMPLETED",
        f"Review {size} GB snapshot, age {age_days} days"
    )


print("\n================================")
print("All AWS findings stored in DynamoDB")
print("================================")