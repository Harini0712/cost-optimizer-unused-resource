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
        print("--------------------")