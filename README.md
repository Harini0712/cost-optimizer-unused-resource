# AWS Cost Optimizer

An automated AWS cost monitoring, cleanup, reporting, and alerting
project built with Python, Boto3, AWS Lambda, EventBridge, DynamoDB, S3,
AWS Cost Explorer, AWS Compute Optimizer, Slack, Flask, and CloudWatch.

The project scans AWS resources, detects possible cost waste,
automatically cleans selected resources based on defined rules, stores
cleanup results, creates reports, sends Slack notifications, and exposes
the findings through a Flask dashboard.

------------------------------------------------------------------------

## 1. Project Overview

AWS accounts can accumulate resources that are no longer required or are
not being used efficiently.

Common examples are:

-   Stopped EC2 instances
-   Unattached EBS volumes
-   Unused Elastic IP addresses
-   Old or unnecessary EBS snapshots
-   EC2 instances that may be over-provisioned
-   Resources that are difficult to track manually

The goal of this project is to reduce unnecessary AWS cost by automating
the discovery and cleanup process.

The system uses Python and Boto3 to communicate with AWS services. AWS
Lambda runs the automation, EventBridge triggers it daily, DynamoDB
stores findings, S3 stores reports, Slack sends notifications, and a
Flask application provides a dashboard.

------------------------------------------------------------------------

## 2. Problem Statement

Manual AWS cost optimization has several problems:

1.  Unused resources are difficult to identify continuously.
2.  Stopped EC2 instances can remain for long periods.
3.  Unattached EBS volumes can continue to generate storage charges.
4.  Unused Elastic IPs can generate unnecessary charges.
5.  Snapshots can accumulate storage cost.
6.  EC2 resources may be larger than required.
7.  Cost information is spread across different AWS services.
8.  Manual checking takes time.
9.  Teams may not know immediately when cleanup is required.

This project provides an automated solution for these problems.

------------------------------------------------------------------------

## 3. Project Objectives

The main objectives are:

-   Scan AWS resources automatically.
-   Detect stopped EC2 instances.
-   Detect unattached EBS volumes.
-   Detect unused Elastic IPs.
-   Scan owned EBS snapshots.
-   Automatically clean resources according to predefined rules.
-   Handle AMI-linked snapshots.
-   Retrieve monthly AWS cost data using Cost Explorer.
-   Retrieve EC2 right-sizing recommendations using Compute Optimizer.
-   Store cleanup findings in DynamoDB.
-   Store JSON reports in S3.
-   Send cleanup results to Slack.
-   Display stored results in a Flask dashboard.
-   Run the complete workflow automatically using EventBridge and
    Lambda.
-   Monitor execution through CloudWatch Logs.

------------------------------------------------------------------------

## 4. High-Level Architecture

``` text
                         AWS ACCOUNT
                              |
                              v
                   EventBridge Scheduler
                       rate(1 day)
                              |
                              v
                       AWS Lambda
                    Python + Boto3
                              |
        +---------------------+----------------------+
        |                     |                      |
        v                     v                      v
       EC2                   EBS                    EIP
        |                     |                      |
        +---------------------+----------------------+
                              |
                              v
                       EBS Snapshots
                              |
                              v
                    AMI Relationship Check
                              |
                              v
                    Cost Explorer + 
                    Compute Optimizer
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
         DynamoDB            S3              Slack
         Findings          Reports           Alerts
             |
             v
         Flask API
             |
             v
         Dashboard

                     CloudWatch Logs
                     Lambda Monitoring
```

------------------------------------------------------------------------

## 5. Technologies Used

  Technology              Purpose
  ----------------------- -------------------------------------
  Python                  Main programming language
  Boto3                   AWS SDK for Python
  AWS Lambda              Serverless execution
  Amazon EC2              Instance scanning and cleanup
  Amazon EBS              Volume scanning and cleanup
  Elastic IP              Unused EIP detection and release
  EBS Snapshots           Snapshot scanning and cleanup
  AMI                     Snapshot relationship handling
  AWS Cost Explorer       AWS cost analysis
  AWS Compute Optimizer   EC2 right-sizing recommendations
  DynamoDB                Store findings and cleanup status
  Amazon S3               Store generated reports
  Slack                   Notifications
  Flask                   API and dashboard
  EventBridge             Daily automation
  CloudWatch              Lambda logs and monitoring
  IAM                     AWS permissions and access control
  python-dotenv           Local environment variable handling
  Requests                Local Slack testing

------------------------------------------------------------------------

# 6. Project Phases

## Phase 0 - Manual AWS Test Environment

A small AWS test environment was created to validate the project.

Initial test resources included:

``` text
1 Running EC2
1 Stopped EC2
1 Unattached EBS volume
1 Unused Elastic IP
2 EBS snapshots
```

The EC2 test type was:

``` text
t3.micro
```

The snapshots were approximately 55 days old.

The running EC2 was intentionally protected from automatic cleanup.

------------------------------------------------------------------------

# 7. Phase 1 - AWS Resource Scanner

The first Python scanner used Boto3 to retrieve EC2 instances.

Example:

``` python
import boto3

ec2 = boto3.client("ec2")

response = ec2.describe_instances()

for reservation in response["Reservations"]:
    for instance in reservation["Instances"]:
        instance_id = instance["InstanceId"]
        instance_type = instance["InstanceType"]
        state = instance["State"]["Name"]

        print("Instance ID:", instance_id)
        print("Instance Type:", instance_type)
        print("State:", state)
        print("----------------------")
```

The scanner identified:

-   Instance ID
-   Instance type
-   Instance state

Example output:

``` text
Instance ID: i-xxxxxxxx
Instance Type: t3.micro
State: running

Instance ID: i-yyyyyyyy
Instance Type: t3.micro
State: stopped
```

------------------------------------------------------------------------

# 8. Phase 2 - Stale Resource Detection

The scanner was extended to identify possible cost-wasting resources.

## 8.1 Stopped EC2

The project searches for instances with:

``` text
instance-state-name = stopped
```

A stopped instance is not immediately terminated unless it satisfies the
configured cleanup rule.

Current rule:

``` text
Stopped for >= 30 days
        |
        v
TERMINATE
```

A stopped instance below 30 days is kept.

Running instances are not automatically terminated.

------------------------------------------------------------------------

## 8.2 Unattached EBS

EBS volumes with:

``` text
status = available
```

are treated as unattached.

Current rule:

``` text
Unattached EBS
      |
      v
DELETE
```

------------------------------------------------------------------------

## 8.3 Unused Elastic IP

An Elastic IP without an `AssociationId` is treated as unused.

Current rule:

``` text
Unused EIP
    |
    v
RELEASE
```

------------------------------------------------------------------------

## 8.4 EBS Snapshots

The scanner retrieves snapshots owned by the AWS account.

Snapshot information includes:

-   Snapshot ID
-   Volume size
-   State
-   Start time
-   Age in days

Current project rule:

``` text
ALL OWNED EBS SNAPSHOTS
            |
            v
          DELETE
```

This is intentionally different from the original 54/55-day test rule.
The final automation was changed to delete all owned snapshots as
requested for this project.

------------------------------------------------------------------------

# 9. Initial Detection Results

The initial test environment produced:

``` text
Stopped EC2:     1
Unattached EBS:  1
Unused EIP:      1
Snapshots:       2
--------------------
Total Findings:  5
```

Example findings:

``` text
STOPPED EC2
i-0c161a820cf999289 | t3.micro

UNATTACHED EBS
vol-00525c6fe489d15fb | 1 GB | gp3

UNUSED EIP
13.235.43.30

SNAPSHOTS
snap-0bc01ed9bb11dec43 | 8 GB | 55 days
snap-047613ce5bf5258c5 | 8 GB | 55 days
```

------------------------------------------------------------------------

# 10. Phase 3 - AWS Cost Explorer

AWS Cost Explorer is used to retrieve cost information.

The project groups the previous month's cost by AWS service.

The Cost Explorer client is created in:

``` text
us-east-1
```

because Cost Explorer is accessed through that regional endpoint.

The reporting period is calculated dynamically.

Example:

``` text
Cost period:
2026-08-01 -> 2026-09-01
```

The end date is exclusive, so this represents the previous calendar
month.

Example service data from the test account included:

``` text
AWS Data Transfer
EC2 - Other
Amazon Elastic Compute Cloud - Compute
Amazon Elastic Container Service
Amazon Elastic Load Balancing
```

### Cost calculation note

During testing, the account had a small positive/negative service-level
cost combination:

``` text
AWS Data Transfer:                     -0.077873
EC2 - Other:                            0.077541
Amazon Elastic Compute Cloud - Compute: 0.000056
Amazon Elastic Container Service:       0.000267
Amazon Elastic Load Balancing:          0.000009
```

The current code rounds very small negative totals to zero.

Therefore the displayed total can be:

``` text
$0.00
```

even though individual service entries contain small amounts.

This is a known test-account accounting/credit display issue and should
be refined if this project is later used as a production financial
reporting system.

------------------------------------------------------------------------

# 11. AWS Compute Optimizer

AWS Compute Optimizer is integrated to retrieve EC2 right-sizing
recommendations.

The API used is:

``` python
compute_optimizer.get_ec2_instance_recommendations()
```

A recommendation can contain:

``` text
Current instance type
Finding
Recommended instance type
```

Example:

``` text
Current:     t3.large
Recommended: t3.medium
```

During testing, the account returned:

``` text
Recommendations: 0
```

This is handled safely.

The project does not create artificial workloads just to generate
Compute Optimizer recommendations.

------------------------------------------------------------------------

# 12. Phase 4 - Slack Integration

Slack is used for cost optimization notifications.

Channel:

``` text
#aws-cost-optimization
```

The Lambda sends a summary after execution.

Example:

``` text
AWS COST OPTIMIZER - AUTO CLEANUP

Region: ap-south-1

AUTO CLEANUP RULES
• Stopped EC2 >= 30 days -> TERMINATE
• Unattached EBS -> DELETE
• Unused EIP -> RELEASE
• ALL owned snapshots -> DELETE
• AMI-linked snapshots -> DEREGISTER AMI + DELETE

CLEANUP RESULT
EC2: ...
EBS: ...
EIP: ...
Snapshots: ...
Total actions: ...

Previous month cost: $...
S3 Report: reports/...
```

The Slack webhook is stored as an environment variable:

``` text
SLACK_WEBHOOK_URL
```

The webhook URL must never be committed to Git.

------------------------------------------------------------------------

# 13. Phase 5 - DynamoDB

A DynamoDB table was created:

``` text
aws-cost-optimization
```

Region:

``` text
ap-south-1
```

Partition key:

``` text
resource_id
```

Type:

``` text
String
```

The table stores information such as:

``` json
{
    "resource_id": "vol-xxxxxxxx",
    "resource_type": "EBS",
    "status": "DELETED",
    "recommendation": "Automatically deleted unattached EBS volume",
    "scanned_at": "2026-09-04T18:00:00+00:00"
}
```

Additional information can include:

-   Resource size
-   Resource type
-   Snapshot age
-   Stopped days
-   Cleanup timestamp
-   Linked AMI IDs

------------------------------------------------------------------------

# 14. Phase 5 - Amazon S3

S3 stores generated JSON reports.

Bucket:

``` text
harini-aws-cost-optimizer-reports-2026
```

Reports are stored under:

``` text
reports/
```

Example:

``` text
reports/2026-09-04_18-26-08.json
```

A report contains:

-   Timestamp
-   AWS region
-   Cleanup rules
-   Cleanup actions
-   Summary
-   Cost Explorer information
-   Compute Optimizer information

Example structure:

``` json
{
    "timestamp": "...",
    "region": "ap-south-1",
    "cleanup_rules": {},
    "cleanup_actions": {},
    "summary": {},
    "cost_explorer": {},
    "compute_optimizer": []
}
```

------------------------------------------------------------------------

# 15. Phase 6 - Flask API and Dashboard

A Flask application was used to provide a simple dashboard.

The dashboard reads stored findings and displays information such as:

``` text
AWS Cost Optimization Dashboard

EC2          1
EBS          1
EIP          1
Snapshots    2

Total Findings: 5
```

Details include:

-   Resource ID
-   Resource type
-   Status
-   Recommendation
-   Scan information

The dashboard provides a centralized view of the project's findings and
cleanup results.

------------------------------------------------------------------------

# 16. Phase 7 - AWS Lambda

The main Lambda function is:

``` text
aws-cost-optimizer
```

Region:

``` text
ap-south-1
```

Runtime:

``` text
Python 3.12
```

The Lambda execution timeout was increased from the default 3 seconds
to:

``` text
30 seconds
```

This was required because the function performs multiple AWS API
operations, report generation, S3 upload, and Slack notification.

------------------------------------------------------------------------

# 17. Lambda Workflow

The complete Lambda workflow is:

``` text
Lambda starts
     |
     +--> Scan stopped EC2
     |       |
     |       +--> >= 30 days -> TERMINATE
     |       +--> < 30 days  -> KEEP
     |
     +--> Scan unattached EBS
     |       |
     |       +--> DELETE
     |
     +--> Scan unused EIP
     |       |
     |       +--> RELEASE
     |
     +--> Scan all owned snapshots
     |       |
     |       +--> Check AMI relationships
     |       |
     |       +--> Deregister linked AMIs
     |       |
     |       +--> DELETE snapshots
     |       |
     |       +--> Verify deletion
     |
     +--> Get Cost Explorer data
     |
     +--> Get Compute Optimizer data
     |
     +--> Save findings to DynamoDB
     |
     +--> Upload JSON report to S3
     |
     +--> Send Slack notification
     |
     v
Lambda completes
```

------------------------------------------------------------------------

# 18. Automatic Cleanup Rules

The final cleanup rules are:

  -----------------------------------------------------------------------
  Resource                Condition               Action
  ----------------------- ----------------------- -----------------------
  Running EC2             Running                 KEEP

  Stopped EC2             Stopped \< 30 days      KEEP

  Stopped EC2             Stopped \>= 30 days     TERMINATE

  EBS volume              Unattached              DELETE

  Elastic IP              Unassociated            RELEASE

  Owned snapshot          Any age                 DELETE

  Snapshot linked to AMI  Snapshot selected for   Deregister AMI, then
                          deletion                delete snapshot
  -----------------------------------------------------------------------

The cleanup code intentionally does not terminate running EC2 instances.

This is important because a running server may be hosting an active
application, Jenkins, Prometheus, API, or other workload.

------------------------------------------------------------------------

# 19. AMI-Linked Snapshot Problem and Solution

During testing, snapshot deletion initially failed.

CloudWatch showed:

``` text
InvalidSnapshot.InUse
```

The snapshot was being used by a disabled AMI.

The affected resources were:

``` text
snap-0bc01ed9bb11dec43
    |
    +--> ami-005fa2ed1c9d32a9e

snap-047613ce5bf5258c5
    |
    +--> ami-002b8f86396089270
```

The first implementation did not discover disabled AMIs.

The final solution includes disabled AMIs when calling `DescribeImages`:

``` python
pages = paginator.paginate(
    Owners=["self"],
    IncludeDeprecated=True,
    IncludeDisabled=True
)
```

The cleanup flow is:

``` text
Snapshot
   |
   v
Find linked AMI
   |
   v
Deregister AMI
   |
   v
Delete snapshot
   |
   v
Verify
```

A fallback is also used when AWS returns an `InvalidSnapshot.InUse`
error containing an AMI ID.

The Lambda can extract the AMI ID, deregister the AMI, and retry the
snapshot deletion.

### Final test result

The previously blocked snapshots were successfully deleted after
implementing the disabled-AMI handling.

This confirmed that the automatic snapshot cleanup workflow works.

------------------------------------------------------------------------

# 20. Important AMI Warning

Deregistering an AMI means the AMI cannot be used for launching new
instances.

Therefore, automatic AMI deregistration and snapshot deletion must only
be enabled when the AMI is known to be disposable.

For production environments, a safer design would use:

-   Resource tags
-   Protected-resource lists
-   Environment checks
-   Approval workflows
-   Backup checks
-   AWS Backup awareness
-   Recycle Bin policies

This project intentionally follows the cleanup rules defined for the
test environment.

------------------------------------------------------------------------

# 21. IAM Permissions

The Lambda execution role contains the permissions required by the
application.

Main read permissions:

``` text
ec2:DescribeInstances
ec2:DescribeVolumes
ec2:DescribeAddresses
ec2:DescribeSnapshots
ec2:DescribeImages
```

Cleanup permissions:

``` text
ec2:TerminateInstances
ec2:DeleteVolume
ec2:ReleaseAddress
ec2:DeleteSnapshot
ec2:DeregisterImage
```

DynamoDB:

``` text
dynamodb:PutItem
```

S3:

``` text
s3:PutObject
```

Cost Explorer:

``` text
ce:GetCostAndUsage
```

Compute Optimizer:

``` text
compute-optimizer:GetEC2InstanceRecommendations
```

Lambda logging:

``` text
AWSLambdaBasicExecutionRole
```

The application uses the Lambda execution role instead of storing AWS
access keys inside the Python code.

------------------------------------------------------------------------

# 22. EventBridge Automation

EventBridge rule:

``` text
aws-cost-optimizer-daily
```

Schedule:

``` text
rate(1 day)
```

State:

``` text
ENABLED
```

The workflow is:

``` text
EventBridge
     |
     | every day
     v
Lambda
     |
     v
AWS Cost Optimizer
     |
     +--> Cleanup
     +--> Cost analysis
     +--> DynamoDB
     +--> S3
     +--> Slack
```

This removes the need to manually execute the Lambda every day.

------------------------------------------------------------------------

# 23. CloudWatch Monitoring

AWS Lambda automatically writes execution logs to CloudWatch.

Logs are useful for:

-   Checking Lambda execution
-   Debugging errors
-   Checking cleanup results
-   Checking AWS API failures
-   Confirming S3 uploads
-   Confirming Slack delivery

Important successful test logs included:

``` text
AWS COST OPTIMIZER + AUTO CLEANUP
Region: ap-south-1
Stopped EC2 rule: >= 30 days -> TERMINATE
Unattached EBS -> DELETE
Unused EIP -> RELEASE
ALL owned snapshots -> DELETE
```

The earlier snapshot failure was also visible in CloudWatch as:

``` text
InvalidSnapshot.InUse
```

This made it possible to identify the disabled-AMI problem.

After the code was fixed, the snapshot cleanup completed successfully.

------------------------------------------------------------------------

# 24. Security

Important security practices used in this project:

### AWS credentials

Do not hard-code AWS access keys in Lambda code.

Lambda uses its IAM execution role.

### Slack webhook

The Slack webhook is stored as:

``` text
SLACK_WEBHOOK_URL
```

Never commit the webhook to Git.

### .env

For local development:

``` text
SLACK_WEBHOOK_URL=your_webhook_url
```

The `.env` file must not be committed.

Example `.gitignore`:

``` text
venv/
.env
__pycache__/
*.pyc
```

### Destructive operations

This project contains destructive operations:

``` text
Terminate EC2
Delete EBS
Release EIP
Deregister AMI
Delete snapshots
```

Therefore, the Lambda should only be attached to an AWS account where
these cleanup rules are intentionally approved.

------------------------------------------------------------------------

# 25. Local Project Structure

Recommended project structure:

``` text
cost-optimizer/
|
+-- venv/
|
+-- ec2_scanner.py
+-- stale_resources.py
+-- cost_analyzer.py
+-- compute_optimizer.py
+-- phase3_combined_report.py
+-- slack_test.py
+-- phase4_slack_report.py
+-- phase5_full_scan.py
+-- s3_upload.py
+-- aws_cost_optimizer_lambda.py
+-- requirements.txt
+-- .env
+-- .gitignore
+-- README.md
```

The Lambda code contains the complete automated workflow.

------------------------------------------------------------------------

# 26. Python Environment Setup

Create the project directory:

``` bash
mkdir cost-optimizer
cd cost-optimizer
```

Create a virtual environment:

``` bash
python -m venv venv
```

Activate it on Windows:

``` bash
venv\Scripts\activate
```

Install required packages:

``` bash
pip install boto3
```

For Slack/local testing:

``` bash
pip install requests python-dotenv
```

A requirements file can contain:

``` text
boto3
requests
python-dotenv
Flask
```

------------------------------------------------------------------------

# 27. Important AWS Resource Configuration

Current project configuration:

``` text
AWS Region:
ap-south-1

DynamoDB Table:
aws-cost-optimization

S3 Bucket:
harini-aws-cost-optimizer-reports-2026

Lambda:
aws-cost-optimizer

EventBridge Rule:
aws-cost-optimizer-daily

EventBridge Schedule:
rate(1 day)

Stopped EC2 Threshold:
30 days

Snapshot Rule:
Delete all owned snapshots
```

Slack:

``` text
#aws-cost-optimization
```

The actual Slack webhook URL is intentionally not documented in this
README.

------------------------------------------------------------------------

# 28. Testing Performed

## Test 1 - EC2 Scanner

Result:

``` text
Running EC2 detected
Stopped EC2 detected
```

## Test 2 - Stale Resource Scanner

Result:

``` text
Stopped EC2: 1
Unattached EBS: 1
Unused EIP: 1
Snapshots: 2
```

## Test 3 - Cost Explorer

Result:

``` text
Cost Explorer API successfully returned service-level data.
```

## Test 4 - Compute Optimizer

Result:

``` text
Recommendations: 0
```

This was handled without creating artificial workloads.

## Test 5 - Slack

Result:

``` text
Slack status: 200
```

## Test 6 - DynamoDB

Findings were successfully stored in:

``` text
aws-cost-optimization
```

## Test 7 - S3

JSON reports were successfully uploaded under:

``` text
reports/
```

## Test 8 - Flask Dashboard

The dashboard successfully displayed stored findings.

## Test 9 - Lambda

Lambda successfully executed the complete workflow.

## Test 10 - EventBridge

The daily EventBridge rule was enabled successfully.

## Test 11 - Snapshot Cleanup

Initially:

``` text
InvalidSnapshot.InUse
```

After disabled-AMI support was added:

``` text
Snapshot deletion successful
```

This confirmed the final cleanup workflow.

------------------------------------------------------------------------

# 29. Example Final Cleanup Flow

``` text
                 EVENTBRIDGE
                     |
                     v
                  LAMBDA
                     |
          +----------+----------+
          |          |          |
          v          v          v
         EC2        EBS        EIP
          |          |          |
          v          v          v
       30 days?    Delete     Release
          |
       Terminate
          |
          +-------------------+
                              |
                              v
                         SNAPSHOTS
                              |
                              v
                         Find AMIs
                              |
                              v
                     Deregister AMIs
                              |
                              v
                      Delete Snapshots
                              |
                              v
                       Verify cleanup
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
         DynamoDB            S3              Slack
          Results          Report           Alert
                              |
                              v
                          Dashboard
```

------------------------------------------------------------------------

# 30. Current Project Status

  Phase                                Status
  ------------------------------------ -----------------
  Phase 0 - Test Environment           Completed
  Phase 1 - Boto3 Scanner              Completed
  Phase 2 - Stale Resource Detection   Completed
  Phase 3 - Cost Explorer              Completed
  Phase 3 - Compute Optimizer          Completed
  Phase 4 - Slack                      Completed
  Phase 5 - DynamoDB                   Completed
  Phase 5 - S3                         Completed
  Phase 6 - Flask Dashboard            Completed
  Phase 7 - Lambda                     Completed
  Phase 7 - Automatic Cleanup          Completed
  Phase 7 - EventBridge                Completed
  Disabled AMI Snapshot Handling       Completed
  Phase 8 - Terraform                  Skipped for now

Terraform was intentionally not included in the current implementation.

------------------------------------------------------------------------

# 31. Why This Project Is Useful

The project combines several AWS services into one practical
DevOps/Cloud cost-optimization workflow.

It demonstrates:

-   Python programming
-   Boto3
-   AWS IAM
-   EC2
-   EBS
-   Elastic IP
-   AMI management
-   EBS snapshots
-   Lambda
-   EventBridge
-   DynamoDB
-   S3
-   Cost Explorer
-   Compute Optimizer
-   Slack integration
-   Flask API
-   Dashboard development
-   CloudWatch monitoring
-   Automated resource cleanup

This makes the project useful as a hands-on AWS automation and
cost-optimization project.

------------------------------------------------------------------------

# 32. Interview Explanation

A simple interview explanation:

> I built an AWS Cost Optimizer using Python and Boto3. The system scans
> EC2, EBS, Elastic IPs, and snapshots for unnecessary resources. AWS
> Lambda performs the automation and EventBridge runs it daily. Based on
> predefined rules, stopped EC2 instances older than 30 days are
> terminated, unattached EBS volumes are deleted, unused Elastic IPs are
> released, and owned snapshots are deleted. If a snapshot is linked to
> an AMI, the Lambda handles the AMI relationship before deleting the
> snapshot. Cost Explorer is used for cost analysis and Compute
> Optimizer is used for EC2 right-sizing recommendations. The system
> stores results in DynamoDB, saves reports in S3, sends notifications
> to Slack, and displays findings through a Flask dashboard. CloudWatch
> is used to monitor Lambda execution.

------------------------------------------------------------------------

# 33. Key Learning

The main lessons from this project were:

1.  Boto3 can automate AWS resource management.
2.  IAM roles are important for secure AWS automation.
3.  Lambda can run Python automation without managing servers.
4.  EventBridge can schedule serverless jobs.
5.  Cost Explorer provides service-level cost information.
6.  Compute Optimizer can help with EC2 right-sizing.
7.  DynamoDB is useful for storing structured findings.
8.  S3 is useful for storing generated reports.
9.  Slack can provide immediate operational notifications.
10. CloudWatch logs are essential for debugging automation.
11. AWS resources can have dependencies that prevent deletion.
12. AMIs can keep snapshots in use.
13. Disabled AMIs must be considered when discovering AMI relationships.
14. Destructive automation must have clear rules and protection
    mechanisms.

------------------------------------------------------------------------

# 34. Future Improvements

Possible future improvements:

-   Add resource tagging rules.
-   Add protected-resource tags such as `CostOptimization=Protected`.
-   Add AWS Backup detection.
-   Add Recycle Bin awareness.
-   Add monthly savings calculation.
-   Add historical cost graphs.
-   Add dashboard charts.
-   Add email notifications.
-   Add SNS notifications.
-   Add approval workflow for destructive actions.
-   Add separate development and production modes.
-   Add unit tests.
-   Add automated deployment pipeline.
-   Add Terraform later if infrastructure-as-code is required.
-   Improve Cost Explorer credit/refund handling.
-   Add detailed cleanup audit history.

------------------------------------------------------------------------

# 35. Conclusion

The AWS Cost Optimizer evolved from a simple Boto3 resource scanner into
a complete automated AWS cost-management workflow.

The final system can:

``` text
SCAN
  ↓
DETECT
  ↓
ANALYZE COST
  ↓
CLEAN UP
  ↓
STORE RESULTS
  ↓
GENERATE REPORT
  ↓
SEND ALERT
  ↓
DISPLAY DASHBOARD
```

The project successfully demonstrated automatic cleanup of unnecessary
AWS resources and successfully handled the real-world case where
snapshots were blocked by disabled AMIs.

The final architecture provides a practical foundation for AWS cost
optimization automation while keeping the cleanup rules explicit and
configurable.
