from flask import Flask, jsonify, render_template
import boto3

app = Flask(__name__)

dynamodb = boto3.resource(
    "dynamodb",
    region_name="ap-south-1"
)

table = dynamodb.Table("aws-cost-optimization")


@app.route("/")
def home():
    return "AWS Cost Optimizer API is running!"


@app.route("/findings")
def get_findings():
    response = table.scan()
    return jsonify(response["Items"])


@app.route("/findings/<resource_type>")
def get_by_type(resource_type):

    response = table.scan()

    items = [
        item for item in response["Items"]
        if item["resource_type"].lower() == resource_type.lower()
    ]

    return jsonify(items)


@app.route("/summary")
def summary():

    response = table.scan()
    items = response["Items"]

    result = {
        "total_findings": len(items),
        "EC2": 0,
        "EBS": 0,
        "EIP": 0,
        "SNAPSHOT": 0
    }

    for item in items:
        resource_type = item["resource_type"]

        if resource_type in result:
            result[resource_type] += 1

    return jsonify(result)
@app.route("/dashboard")
def dashboard():

    response = table.scan()
    items = response["Items"]

    summary = {
        "total_findings": len(items),
        "EC2": 0,
        "EBS": 0,
        "EIP": 0,
        "SNAPSHOT": 0
    }

    for item in items:

        resource_type = item["resource_type"]

        if resource_type in summary:
            summary[resource_type] += 1

    return render_template(
        "dashboard.html",
        summary=summary,
        findings=items
    )

if __name__ == "__main__":
    app.run(debug=True)