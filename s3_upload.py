import boto3

s3 = boto3.client("s3", region_name="ap-south-1")

bucket_name = "harini-aws-cost-optimizer-reports-2026"

file_name = "cost-optimization-report.csv"

s3.upload_file(
    file_name,
    bucket_name,
    "reports/cost-optimization-report.csv"
)

print("Report uploaded to S3 successfully!")