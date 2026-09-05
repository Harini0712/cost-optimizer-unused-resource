import boto3

optimizer = boto3.client("compute-optimizer", region_name="ap-south-1")

response = optimizer.get_ec2_instance_recommendations()

print("\n========== COMPUTE OPTIMIZER ==========\n")

recommendations = response.get("instanceRecommendations", [])

if not recommendations:
    print("No Compute Optimizer recommendations available.")
else:

    for recommendation in recommendations:

        instance_id = recommendation["instanceArn"].split("/")[-1]

        finding = recommendation["finding"]

        print("Instance:", instance_id)
        print("Finding:", finding)

        options = recommendation.get("recommendationOptions", [])

        if options:

            option = options[0]

            print(
                "Recommended Instance Type:",
                option["instanceType"]
            )

            print(
                "Estimated Monthly Savings:",
                option.get("estimatedMonthlySavings", {}).get("value", 0)
            )

        print("---------------------------------------")
        