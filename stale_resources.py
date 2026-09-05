import boto3
import csv
from datetime import datetime, timezone

ec2 = boto3.client("ec2")


def find_stopped_instances():

    response = ec2.describe_instances(
        Filters=[
            {
                "Name": "instance-state-name",
                "Values": ["stopped"]
            }
        ]
    )

    instances = []

    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:

            instances.append({
                "resource": "EC2",
                "id": instance["InstanceId"],
                "type": instance["InstanceType"],
                "status": "Stopped",
                "recommendation": "Review if instance is still required"
            })

    return instances


def find_unattached_volumes():

    response = ec2.describe_volumes(
        Filters=[
            {
                "Name": "status",
                "Values": ["available"]
            }
        ]
    )

    volumes = []

    for volume in response["Volumes"]:

        volumes.append({
            "resource": "EBS",
            "id": volume["VolumeId"],
            "type": volume["VolumeType"],
            "status": "Unattached",
            "recommendation": "Review and delete if no longer required"
        })

    return volumes


def find_unused_eips():

    response = ec2.describe_addresses()

    eips = []

    for address in response["Addresses"]:

        if "AssociationId" not in address:

            eips.append({
                "resource": "Elastic IP",
                "id": address.get("AllocationId"),
                "type": address.get("PublicIp"),
                "status": "Unassociated",
                "recommendation": "Review and release if no longer required"
            })

    return eips


def find_snapshots():

    response = ec2.describe_snapshots(
        OwnerIds=["self"]
    )

    snapshots = []

    now = datetime.now(timezone.utc)

    for snapshot in response["Snapshots"]:

        age_days = (now - snapshot["StartTime"]).days

        snapshots.append({
            "resource": "Snapshot",
            "id": snapshot["SnapshotId"],
            "type": f"{snapshot['VolumeSize']} GB",
            "status": f"{age_days} days old",
            "recommendation": "Review snapshot retention"
        })

    return snapshots


# Collect findings

findings = []

findings.extend(find_stopped_instances())
findings.extend(find_unattached_volumes())
findings.extend(find_unused_eips())
findings.extend(find_snapshots())


# Display findings

print("\n========== AWS COST OPTIMIZATION FINDINGS ==========\n")

for finding in findings:

    print(
        f"{finding['resource']} | "
        f"{finding['id']} | "
        f"{finding['status']} | "
        f"{finding['recommendation']}"
    )


# Create CSV report

filename = "cost-optimization-report.csv"

with open(filename, "w", newline="") as file:

    writer = csv.DictWriter(
        file,
        fieldnames=[
            "resource",
            "id",
            "type",
            "status",
            "recommendation"
        ]
    )

    writer.writeheader()

    for finding in findings:
        writer.writerow(finding)


# Summary

print("\n========== SUMMARY ==========")

print("Total findings:", len(findings))

print("\nReport created successfully:")
print(filename)

print("=============================\n")