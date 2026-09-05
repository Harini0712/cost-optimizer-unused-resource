import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")

table = dynamodb.Table("aws-cost-optimization")

item = {
    "resource_id": "i-0c161a820cf999289",
    "resource_type": "EC2",
    "status": "STOPPED",
    "recommendation": "Review stopped EC2 instance",
    "scanned_at": datetime.now(timezone.utc).isoformat()
}

table.put_item(Item=item)

print("Resource finding stored in DynamoDB!")