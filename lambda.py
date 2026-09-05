import boto3
import json
import os
import urllib.request
import re
from datetime import datetime, timezone, timedelta


# ============================================================
# CONFIG
# ============================================================

REGION = "ap-south-1"

DYNAMODB_TABLE = "aws-cost-optimization"

S3_BUCKET = "harini-aws-cost-optimizer-reports-2026"

# Stopped EC2 older than this -> terminate
STOPPED_EC2_DAYS = 30

# ALL owned EBS snapshots -> delete
DELETE_ALL_SNAPSHOTS = True

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


# ============================================================
# AWS CLIENTS
# ============================================================

ec2 = boto3.client(
    "ec2",
    region_name=REGION
)

dynamodb = boto3.resource(
    "dynamodb",
    region_name=REGION
)

table = dynamodb.Table(
    DYNAMODB_TABLE
)

s3 = boto3.client(
    "s3",
    region_name=REGION
)

# Cost Explorer is available through us-east-1
ce = boto3.client(
    "ce",
    region_name="us-east-1"
)

compute_optimizer = boto3.client(
    "compute-optimizer",
    region_name=REGION
)


# ============================================================
# TIME
# ============================================================

def now():
    return datetime.now(timezone.utc)


# ============================================================
# DYNAMODB
# ============================================================

def save_finding(
    resource_id,
    resource_type,
    status,
    recommendation,
    extra=None
):
    item = {
        "resource_id": resource_id,
        "resource_type": resource_type,
        "status": status,
        "recommendation": recommendation,
        "scanned_at": now().isoformat()
    }

    if extra:
        item.update(extra)

    try:
        table.put_item(Item=item)
    except Exception as error:
        print(
            f"DynamoDB save failed for {resource_id}:",
            error
        )


# ============================================================
# SLACK
# ============================================================

def send_slack(message):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not configured")
        return

    payload = json.dumps({
        "text": message
    }).encode("utf-8")

    request = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=10
        ) as response:
            print("Slack status:", response.status)

    except Exception as error:
        print("Slack error:", error)


# ============================================================
# 1. STOPPED EC2 CLEANUP
# ============================================================

def cleanup_stopped_ec2():
    print("\n========== STOPPED EC2 CLEANUP ==========")

    actions = []

    try:
        paginator = ec2.get_paginator("describe_instances")

        pages = paginator.paginate(
            Filters=[
                {
                    "Name": "instance-state-name",
                    "Values": ["stopped"]
                }
            ]
        )

        for page in pages:
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):

                    instance_id = instance["InstanceId"]
                    instance_type = instance["InstanceType"]

                    reason = instance.get(
                        "StateTransitionReason",
                        ""
                    )

                    stopped_since = None

                    if "(" in reason and ")" in reason:
                        try:
                            date_text = (
                                reason
                                .split("(")[1]
                                .split(")")[0]
                            )

                            stopped_since = datetime.strptime(
                                date_text,
                                "%Y-%m-%d %H:%M:%S GMT"
                            ).replace(
                                tzinfo=timezone.utc
                            )

                        except Exception:
                            stopped_since = None

                    if not stopped_since:
                        print(
                            f"SKIP EC2: {instance_id} "
                            "- stopped date unavailable"
                        )

                        save_finding(
                            instance_id,
                            "EC2",
                            "STOPPED",
                            "Skipped because stopped date "
                            "could not be determined"
                        )

                        continue

                    stopped_days = (
                        now() - stopped_since
                    ).days

                    print(
                        f"{instance_id} | "
                        f"{instance_type} | "
                        f"Stopped: {stopped_days} days"
                    )

                    if stopped_days >= STOPPED_EC2_DAYS:
                        try:
                            ec2.terminate_instances(
                                InstanceIds=[instance_id]
                            )

                            print(
                                f"TERMINATED EC2: {instance_id}"
                            )

                            save_finding(
                                instance_id,
                                "EC2",
                                "TERMINATED",
                                f"Automatically terminated "
                                f"after {stopped_days} days stopped",
                                {
                                    "stopped_since":
                                        stopped_since.isoformat(),
                                    "stopped_days":
                                        stopped_days,
                                    "cleanup_at":
                                        now().isoformat()
                                }
                            )

                            actions.append(
                                f"EC2 terminated: {instance_id}"
                            )

                        except Exception as error:
                            print(
                                f"EC2 termination failed "
                                f"{instance_id}:",
                                error
                            )

                    else:
                        print(
                            f"KEEP EC2: {instance_id} "
                            f"- only {stopped_days} days stopped"
                        )

                        save_finding(
                            instance_id,
                            "EC2",
                            "STOPPED",
                            f"Keep - stopped "
                            f"{stopped_days} days"
                        )

    except Exception as error:
        print("EC2 cleanup error:", error)

    return actions


# ============================================================
# 2. UNATTACHED EBS CLEANUP
# ============================================================

def cleanup_unattached_ebs():
    print("\n========== UNATTACHED EBS CLEANUP ==========")

    actions = []

    try:
        paginator = ec2.get_paginator("describe_volumes")

        pages = paginator.paginate(
            Filters=[
                {
                    "Name": "status",
                    "Values": ["available"]
                }
            ]
        )

        for page in pages:
            for volume in page.get("Volumes", []):

                volume_id = volume["VolumeId"]
                size = volume.get("Size", 0)
                volume_type = volume.get(
                    "VolumeType",
                    "unknown"
                )

                print(
                    f"Unattached EBS: "
                    f"{volume_id} | "
                    f"{size} GB | "
                    f"{volume_type}"
                )

                try:
                    ec2.delete_volume(
                        VolumeId=volume_id
                    )

                    print(
                        f"DELETED EBS: {volume_id}"
                    )

                    save_finding(
                        volume_id,
                        "EBS",
                        "DELETED",
                        "Automatically deleted "
                        "unattached EBS volume",
                        {
                            "size_gb": size,
                            "volume_type": volume_type,
                            "cleanup_at": now().isoformat()
                        }
                    )

                    actions.append(
                        f"EBS deleted: {volume_id}"
                    )

                except Exception as error:
                    print(
                        f"EBS deletion failed "
                        f"{volume_id}:",
                        error
                    )

    except Exception as error:
        print("EBS cleanup error:", error)

    return actions


# ============================================================
# 3. UNUSED ELASTIC IP CLEANUP
# ============================================================

def cleanup_unused_eip():
    print("\n========== UNUSED EIP CLEANUP ==========")

    actions = []

    try:
        response = ec2.describe_addresses()

        for address in response.get("Addresses", []):

            public_ip = address.get("PublicIp")
            allocation_id = address.get("AllocationId")
            association_id = address.get("AssociationId")

            # No association = unused EIP
            if not association_id and allocation_id:

                print(
                    f"Unused EIP: {public_ip}"
                )

                try:
                    ec2.release_address(
                        AllocationId=allocation_id
                    )

                    print(
                        f"RELEASED EIP: {public_ip}"
                    )

                    save_finding(
                        allocation_id,
                        "EIP",
                        "RELEASED",
                        "Automatically released "
                        "unused Elastic IP",
                        {
                            "public_ip": public_ip,
                            "cleanup_at": now().isoformat()
                        }
                    )

                    actions.append(
                        f"EIP released: {public_ip}"
                    )

                except Exception as error:
                    print(
                        f"EIP release failed "
                        f"{public_ip}:",
                        error
                    )

    except Exception as error:
        print("EIP cleanup error:", error)

    return actions


# ============================================================
# 4. GET ALL OWNED AMIS
# ============================================================

def get_owned_amis():
    """
    Returns:
        {
            "snapshot-id": ["ami-id-1", "ami-id-2"],
            ...
        }
    """

    snapshot_to_amis = {}

    try:
        paginator = ec2.get_paginator("describe_images")

        pages = paginator.paginate(
            Owners=["self"],
            IncludeDeprecated=True,
            IncludeDisabled=True
        )

        for page in pages:
            for image in page.get("Images", []):

                ami_id = image.get("ImageId")

                if not ami_id:
                    continue

                for mapping in image.get(
                    "BlockDeviceMappings",
                    []
                ):

                    ebs = mapping.get("Ebs", {})

                    snapshot_id = ebs.get(
                        "SnapshotId"
                    )

                    if snapshot_id:
                        snapshot_to_amis.setdefault(
                            snapshot_id,
                            []
                        ).append(ami_id)

    except Exception as error:
        print(
            "AMI lookup failed:",
            error
        )

    return snapshot_to_amis


# ============================================================
# 5. DELETE ALL SNAPSHOTS
# ============================================================

def cleanup_all_snapshots():
    """
    Deletes ALL EBS snapshots owned by this AWS account.

    If a snapshot is attached to one or more AMIs:
      1. Find the AMIs.
      2. Deregister every AMI using the snapshot.
      3. Try DeleteAssociatedSnapshots=True.
      4. Re-check the snapshot.
      5. Directly delete any snapshot still remaining.

    IMPORTANT:
    Deregistering an AMI means that AMI can no longer be
    used to launch new instances.
    """

    print("\n========== ALL SNAPSHOT CLEANUP ==========")

    actions = []

    if not DELETE_ALL_SNAPSHOTS:
        print("Snapshot deletion is disabled")
        return actions

    # --------------------------------------------------------
    # Step 1: Find AMI -> Snapshot relationships
    # --------------------------------------------------------

    snapshot_to_amis = get_owned_amis()

    print(
        f"AMI-linked snapshots found: "
        f"{len(snapshot_to_amis)}"
    )

    # --------------------------------------------------------
    # Step 2: Get ALL owned snapshots
    # --------------------------------------------------------

    try:
        paginator = ec2.get_paginator("describe_snapshots")

        pages = paginator.paginate(
            OwnerIds=["self"]
        )

        for page in pages:

            for snapshot in page.get(
                "Snapshots",
                []
            ):

                snapshot_id = snapshot["SnapshotId"]

                size = snapshot.get(
                    "VolumeSize",
                    0
                )

                state = snapshot.get(
                    "State",
                    "unknown"
                )

                start_time = snapshot.get(
                    "StartTime"
                )

                age_days = None

                if start_time:
                    age_days = (
                        now() - start_time
                    ).days

                linked_amis = snapshot_to_amis.get(
                    snapshot_id,
                    []
                )

                print(
                    f"\nSnapshot: {snapshot_id}"
                )

                print(
                    f"Size: {size} GB"
                )

                print(
                    f"State: {state}"
                )

                print(
                    f"Age: {age_days} days"
                )

                if linked_amis:
                    print(
                        "Linked AMIs:",
                        ", ".join(linked_amis)
                    )

                # ------------------------------------------------
                # Step 3: Deregister all linked AMIs
                # ------------------------------------------------

                for ami_id in linked_amis:

                    try:
                        print(
                            f"DEREGISTERING AMI: {ami_id}"
                        )

                        ec2.deregister_image(
                            ImageId=ami_id,
                            DeleteAssociatedSnapshots=True
                        )

                        print(
                            f"AMI deregistered: {ami_id}"
                        )

                        save_finding(
                            ami_id,
                            "AMI",
                            "DEREGISTERED",
                            "Deregistered because "
                            "its snapshot was selected "
                            "for automatic deletion",
                            {
                                "snapshot_id":
                                    snapshot_id,
                                "cleanup_at":
                                    now().isoformat()
                            }
                        )

                    except Exception as error:
                        print(
                            f"AMI deregistration failed "
                            f"{ami_id}:",
                            error
                        )

                # ------------------------------------------------
                # Step 4: Delete snapshot
                # ------------------------------------------------

                try:
                    ec2.delete_snapshot(
                        SnapshotId=snapshot_id
                    )

                    print(
                        f"DELETED SNAPSHOT: "
                        f"{snapshot_id}"
                    )

                    save_finding(
                        snapshot_id,
                        "SNAPSHOT",
                        "DELETED",
                        "Automatically deleted "
                        "all owned snapshots",
                        {
                            "age_days": age_days,
                            "size_gb": size,
                            "state": state,
                            "linked_amis":
                                linked_amis,
                            "cleanup_at":
                                now().isoformat()
                        }
                    )

                    actions.append(
                        f"Snapshot deleted: {snapshot_id}"
                    )

                except Exception as error:

                    error_text = str(error)

                    print(
                        f"Snapshot deletion failed "
                        f"{snapshot_id}:",
                        error
                    )

                    # ------------------------------------------------
                    # Step 4B: AWS may report disabled AMIs in the
                    # delete error. Extract them and deregister them.
                    # ------------------------------------------------

                    if "InvalidSnapshot.InUse" in error_text:

                        error_ami_ids = sorted(
                            set(
                                re.findall(
                                    r"ami-[0-9a-f]+",
                                    error_text
                                )
                            )
                        )

                        for ami_id in error_ami_ids:

                            if ami_id in linked_amis:
                                continue

                            try:
                                print(
                                    f"AMI found from delete error: {ami_id}"
                                )

                                print(
                                    f"DEREGISTERING AMI: {ami_id}"
                                )

                                ec2.deregister_image(
                                    ImageId=ami_id,
                                    DeleteAssociatedSnapshots=True
                                )

                                print(
                                    f"AMI deregistered: {ami_id}"
                                )

                                linked_amis.append(ami_id)

                                save_finding(
                                    ami_id,
                                    "AMI",
                                    "DEREGISTERED",
                                    "Deregistered because its snapshot "
                                    "was selected for automatic deletion",
                                    {
                                        "snapshot_id": snapshot_id,
                                        "cleanup_at": now().isoformat()
                                    }
                                )

                            except Exception as ami_error:
                                print(
                                    f"AMI deregistration failed "
                                    f"{ami_id}:",
                                    ami_error
                                )

                        # Retry snapshot deletion after AMI cleanup.
                        try:
                            ec2.delete_snapshot(
                                SnapshotId=snapshot_id
                            )

                            print(
                                f"DELETED SNAPSHOT AFTER AMI CLEANUP: "
                                f"{snapshot_id}"
                            )

                            save_finding(
                                snapshot_id,
                                "SNAPSHOT",
                                "DELETED",
                                "Automatically deleted after deregistering "
                                "AMI dependencies",
                                {
                                    "age_days": age_days,
                                    "size_gb": size,
                                    "state": state,
                                    "linked_amis": linked_amis,
                                    "cleanup_at": now().isoformat()
                                }
                            )

                            actions.append(
                                f"Snapshot deleted: {snapshot_id}"
                            )

                            continue

                        except Exception as retry_error:
                            print(
                                f"Snapshot retry deletion failed "
                                f"{snapshot_id}:",
                                retry_error
                            )

                    # ------------------------------------------------
                    # Step 5: Verify whether it still exists
                    # ------------------------------------------------

                    try:
                        ec2.describe_snapshots(
                            SnapshotIds=[snapshot_id]
                        )

                        print(
                            f"VERIFY: Snapshot still exists "
                            f"{snapshot_id}"
                        )

                    except Exception as verify_error:

                        error_text = str(
                            verify_error
                        )

                        if (
                            "InvalidSnapshot.NotFound"
                            in error_text
                            or
                            "does not exist"
                            in error_text
                        ):
                            print(
                                f"VERIFY: Snapshot already "
                                f"deleted {snapshot_id}"
                            )

                            save_finding(
                                snapshot_id,
                                "SNAPSHOT",
                                "DELETED",
                                "Snapshot was removed "
                                "during AMI deregistration",
                                {
                                    "age_days": age_days,
                                    "size_gb": size,
                                    "linked_amis":
                                        linked_amis,
                                    "cleanup_at":
                                        now().isoformat()
                                }
                            )

                            actions.append(
                                f"Snapshot deleted: "
                                f"{snapshot_id}"
                            )
                        else:
                            print(
                                f"VERIFY ERROR "
                                f"{snapshot_id}:",
                                verify_error
                            )

    except Exception as error:
        print(
            "Snapshot cleanup error:",
            error
        )

    return actions


# ============================================================
# 6. COST EXPLORER
# ============================================================

def get_previous_month_cost():

    print("\n========== COST EXPLORER ==========")

    today = now().date()

    first_day = today.replace(
        day=1
    )

    last_month_end = (
        first_day -
        timedelta(days=1)
    )

    last_month_start = (
        last_month_end.replace(
            day=1
        )
    )

    start = last_month_start.isoformat()
    end = first_day.isoformat()

    print(
        f"Cost period: {start} -> {end}"
    )

    try:

        response = ce.get_cost_and_usage(
            TimePeriod={
                "Start": start,
                "End": end
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

        services = []
        total = 0.0

        for result in response.get(
            "ResultsByTime",
            []
        ):

            for group in result.get(
                "Groups",
                []
            ):

                service = group["Keys"][0]

                amount = float(
                    group["Metrics"][
                        "UnblendedCost"
                    ]["Amount"]
                )

                total += amount

                if abs(amount) > 0.000001:
                    services.append({
                        "service": service,
                        "cost": round(
                            amount,
                            6
                        )
                    })

        # AWS credits/refunds can make the grouped total
        # slightly negative.
        if total < 0 and abs(total) < 0.01:
            total = 0.0

        total = round(total, 6)

        print(
            "Total cost:",
            total
        )

        for service in services:
            print(
                f"{service['service']}: "
                f"${service['cost']}"
            )

        return {
            "start": start,
            "end": end,
            "total": total,
            "services": services
        }

    except Exception as error:

        print(
            "Cost Explorer error:",
            error
        )

        return {
            "start": start,
            "end": end,
            "total": 0.0,
            "services": [],
            "error": str(error)
        }


# ============================================================
# 7. COMPUTE OPTIMIZER
# ============================================================

def get_compute_optimizer():

    print(
        "\n========== COMPUTE OPTIMIZER =========="
    )

    try:

        response = (
            compute_optimizer
            .get_ec2_instance_recommendations()
        )

        recommendations = response.get(
            "instanceRecommendations",
            []
        )

        result = []

        for recommendation in recommendations:

            options = recommendation.get(
                "recommendationOptions",
                []
            )

            recommended_type = None

            if options:
                recommended_type = (
                    options[0].get(
                        "instanceType"
                    )
                )

            result.append({
                "instance":
                    recommendation.get(
                        "instanceArn"
                    ),
                "finding":
                    recommendation.get(
                        "finding"
                    ),
                "current_type":
                    recommendation.get(
                        "currentInstanceType"
                    ),
                "recommended_type":
                    recommended_type
            })

        print(
            "Recommendations:",
            len(result)
        )

        return result

    except Exception as error:

        print(
            "Compute Optimizer error:",
            error
        )

        return []


# ============================================================
# 8. S3 REPORT
# ============================================================

def upload_report(report):

    timestamp = now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    key = (
        f"reports/"
        f"{timestamp}.json"
    )

    try:

        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(
                report,
                indent=4,
                default=str
            ),
            ContentType="application/json"
        )

        print(
            "S3 report uploaded:",
            key
        )

        return key

    except Exception as error:

        print(
            "S3 upload failed:",
            error
        )

        return None


# ============================================================
# 9. LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):

    print(
        "=============================================="
    )

    print(
        "AWS COST OPTIMIZER + AUTO CLEANUP"
    )

    print(
        "=============================================="
    )

    print(
        f"Region: {REGION}"
    )

    print(
        f"Stopped EC2 rule: "
        f">= {STOPPED_EC2_DAYS} days -> TERMINATE"
    )

    print(
        "Unattached EBS -> DELETE"
    )

    print(
        "Unused EIP -> RELEASE"
    )

    print(
        "ALL owned snapshots -> DELETE"
    )

    # ========================================================
    # CLEANUP
    # ========================================================

    ec2_actions = cleanup_stopped_ec2()

    ebs_actions = cleanup_unattached_ebs()

    eip_actions = cleanup_unused_eip()

    snapshot_actions = cleanup_all_snapshots()

    # ========================================================
    # COST
    # ========================================================

    cost_data = get_previous_month_cost()

    # ========================================================
    # COMPUTE OPTIMIZER
    # ========================================================

    optimizer_data = get_compute_optimizer()

    # ========================================================
    # COMBINE ACTIONS
    # ========================================================

    all_actions = (
        ec2_actions
        + ebs_actions
        + eip_actions
        + snapshot_actions
    )

    # ========================================================
    # REPORT
    # ========================================================

    report = {

        "timestamp":
            now().isoformat(),

        "region":
            REGION,

        "cleanup_rules": {

            "stopped_ec2_days":
                STOPPED_EC2_DAYS,

            "stopped_ec2_action":
                "TERMINATE",

            "unattached_ebs":
                "DELETE",

            "unused_eip":
                "RELEASE",

            "snapshots":
                "DELETE ALL OWNED SNAPSHOTS",

            "ami_associated_snapshots":
                "DEREGISTER AMI THEN DELETE"
        },

        "cleanup_actions": {

            "ec2":
                ec2_actions,

            "ebs":
                ebs_actions,

            "eip":
                eip_actions,

            "snapshots":
                snapshot_actions
        },

        "summary": {

            "ec2":
                len(ec2_actions),

            "ebs":
                len(ebs_actions),

            "eip":
                len(eip_actions),

            "snapshots":
                len(snapshot_actions),

            "total":
                len(all_actions)
        },

        "cost_explorer":
            cost_data,

        "compute_optimizer":
            optimizer_data
    }

    # ========================================================
    # S3
    # ========================================================

    report_key = upload_report(
        report
    )

    # ========================================================
    # SLACK
    # ========================================================

    slack_message = (
        "🚨 AWS COST OPTIMIZER - AUTO CLEANUP\n\n"

        f"Region: {REGION}\n\n"

        "AUTO CLEANUP RULES\n"

        f"• Stopped EC2 >= "
        f"{STOPPED_EC2_DAYS} days -> TERMINATE\n"

        "• Unattached EBS -> DELETE\n"

        "• Unused EIP -> RELEASE\n"

        "• ALL owned snapshots -> DELETE\n"

        "• AMI-linked snapshots -> "
        "DEREGISTER AMI + DELETE\n\n"

        "CLEANUP RESULT\n"

        f"EC2: {len(ec2_actions)}\n"

        f"EBS: {len(ebs_actions)}\n"

        f"EIP: {len(eip_actions)}\n"

        f"Snapshots: {len(snapshot_actions)}\n"

        f"Total actions: {len(all_actions)}\n\n"

        f"Previous month cost: "
        f"${cost_data['total']}\n\n"

        f"S3 Report: "
        f"{report_key}"
    )

    send_slack(
        slack_message
    )

    # ========================================================
    # RETURN
    # ========================================================

    return {

        "statusCode": 200,

        "message":
            "AWS cost optimization and "
            "automatic cleanup completed",

        "ec2_actions":
            len(ec2_actions),

        "ebs_actions":
            len(ebs_actions),

        "eip_actions":
            len(eip_actions),

        "snapshot_actions":
            len(snapshot_actions),

        "total_actions":
            len(all_actions),

        "previous_month_cost":
            cost_data["total"],

        "compute_optimizer_recommendations":
            len(optimizer_data),

        "s3_report":
            report_key
    }
