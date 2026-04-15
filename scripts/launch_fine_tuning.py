"""Launch a Bedrock fine-tuning job for refi-agent Nova Lite.

Nova Lite v2:
  - Refined system prompt: explicit decision priority ordering, CRITICAL rule
    that failed checks cannot be edge cases, concrete DENIED vs AWC examples.
  - v7 training data: 3000 records with 30% near-miss DENIED scenarios
    (AWC-like numbers but clear failure on another check).
  - Same hyperparams: 4 epochs, LR 5e-5, batch 1.
  - Targeting the AWC/DENIED boundary confusion from v1 (83%).

Usage:
    python scripts/launch_fine_tuning.py
    python scripts/launch_fine_tuning.py --check          # check job status
    python scripts/launch_fine_tuning.py --deploy         # deploy after completion
    python scripts/launch_fine_tuning.py --smoke-test     # test the deployment
"""

import argparse
import json
import sys
import time

import boto3

# ── Config ──────────────────────────────────────────────────────────────────
REGION = "us-east-1"
JOB_NAME = "refi-agent-nova-lite-v2"
MODEL_NAME = "refi-agent-nova-lite-v2"
BASE_MODEL = "amazon.nova-lite-v1:0:300k"
ROLE_ARN = "arn:aws:iam::025066260073:role/service-role/bedrock-finetuning-role"

S3_TRAIN = "s3://kindlending-bedrock-finetuning/refi-v7-nova-lite/train/refi_training_v7_nova_lite.jsonl"
S3_VALID = "s3://kindlending-bedrock-finetuning/refi-v7-nova-lite/validation/refi_validation_v7_nova_lite.jsonl"
S3_OUTPUT = "s3://kindlending-bedrock-finetuning/refi-nova-lite-v2/output/"

HYPER_PARAMS = {
    "epochCount": "4",
    "batchSize": "1",
    "learningRate": "0.00005",          # 5e-5 (AWS sample default)
}


def launch(client):
    """Submit the fine-tuning job."""
    print(f"Launching fine-tuning job: {JOB_NAME}")
    print(f"  Base model:    {BASE_MODEL}")
    print(f"  Learning rate: {HYPER_PARAMS['learningRate']}")
    print(f"  Epochs:        {HYPER_PARAMS['epochCount']}")
    print(f"  Train data:    {S3_TRAIN}")
    print(f"  Output:        {S3_OUTPUT}")
    print()

    resp = client.create_model_customization_job(
        jobName=JOB_NAME,
        customModelName=MODEL_NAME,
        roleArn=ROLE_ARN,
        baseModelIdentifier=BASE_MODEL,
        customizationType="FINE_TUNING",
        trainingDataConfig={"s3Uri": S3_TRAIN},
        validationDataConfig={"validators": [{"s3Uri": S3_VALID}]},
        outputDataConfig={"s3Uri": S3_OUTPUT},
        hyperParameters=HYPER_PARAMS,
    )
    job_arn = resp["jobArn"]
    print(f"Job submitted: {job_arn}")
    return job_arn


def check(client, job_arn=None):
    """Check status of the most recent matching job."""
    if job_arn:
        job = client.get_model_customization_job(jobIdentifier=job_arn)
    else:
        # Find the latest job by name prefix
        jobs = client.list_model_customization_jobs(
            nameContains="refi-agent-nova-micro",
            sortBy="CreationTime",
            sortOrder="Descending",
            maxResults=5,
        )
        if not jobs.get("modelCustomizationJobSummaries"):
            print("No matching jobs found.")
            return None
        latest = jobs["modelCustomizationJobSummaries"][0]
        print(f"Latest job: {latest['jobName']} ({latest['jobArn']})")
        job = client.get_model_customization_job(jobIdentifier=latest["jobArn"])

    print(f"Job:    {job['jobName']}")
    print(f"ARN:    {job['jobArn']}")
    print(f"Status: {job['status']}")
    print(f"Base:   {job.get('baseModelArn', 'N/A')}")

    if job.get("outputModelArn"):
        print(f"Output model: {job['outputModelArn']}")
    if job.get("trainingMetrics"):
        print(f"Training loss:   {job['trainingMetrics'].get('trainingLoss', 'N/A')}")
    if job.get("validationMetrics"):
        for vm in job["validationMetrics"]:
            print(f"Validation loss: {vm.get('validationLoss', 'N/A')}")

    details = job.get("statusDetails", {})
    for phase in ("validationDetails", "trainingDetails"):
        if phase in details:
            d = details[phase]
            print(f"  {phase}: {d.get('status', '?')}")

    print(f"Created: {job.get('creationTime', 'N/A')}")
    if job.get("endTime"):
        print(f"Ended:   {job['endTime']}")

    return job


def deploy(client):
    """Create an on-demand deployment for the fine-tuned model."""
    # Find the v4 custom model
    models = client.list_custom_models(nameContains=MODEL_NAME)
    matches = [m for m in models.get("modelSummaries", []) if m["modelName"] == MODEL_NAME]
    if not matches:
        print(f"Custom model '{MODEL_NAME}' not found. Is the job complete?")
        return None

    model_arn = matches[0]["modelArn"]
    deploy_name = f"{MODEL_NAME}-ondemand"
    print(f"Deploying: {model_arn}")
    print(f"Name:      {deploy_name}")

    resp = client.create_custom_model_deployment(
        modelDeploymentName=deploy_name,
        modelArn=model_arn,
        description=(
            "On-demand inference for refi-agent Nova Lite v2. "
            "LR=5e-5, 4 epochs, v7 data with near-miss DENIED scenarios "
            "and refined decision priority prompt."
        ),
    )
    deployment_arn = resp["customModelDeploymentArn"]
    print(f"Deployment ARN: {deployment_arn}")

    # Poll until active
    print("Waiting for deployment to become Active...")
    while True:
        d = client.get_custom_model_deployment(customModelDeploymentIdentifier=deployment_arn)
        status = d["status"]
        print(f"  Status: {status}")
        if status == "Active":
            print(f"\nDeployment ready: {deployment_arn}")
            return deployment_arn
        if status in ("Failed", "Deleted"):
            print(f"\nDeployment failed: {status}")
            return None
        time.sleep(30)


def smoke_test(client_rt, deployment_arn=None):
    """Send an exact training record to the deployment and check format."""
    if not deployment_arn:
        # Find the active v4 deployment
        bedrock = boto3.client("bedrock", region_name=REGION)
        deps = bedrock.list_custom_model_deployments()
        for d in deps.get("modelDeploymentSummaries", []):
            if MODEL_NAME in d.get("modelDeploymentName", "") and d.get("status") == "Active":
                deployment_arn = d["customModelDeploymentArn"]
                break
        if not deployment_arn:
            print("No active v4 deployment found.")
            return

    # Load exact first training record
    with open("data/nova/refi_training_v7_nova_lite.jsonl") as f:
        rec = json.loads(f.readline())

    system_prompt = rec["system"][0]["text"]
    user_prompt = rec["messages"][0]["content"][0]["text"]
    expected = rec["messages"][1]["content"][0]["text"]

    print(f"Deployment: {deployment_arn}")
    print(f"System:     {system_prompt!r}")
    print(f"Sending exact training record #1...")
    print()

    start = time.time()
    response = client_rt.converse(
        modelId=deployment_arn,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"temperature": 0.0, "maxTokens": 2048},
    )
    elapsed = time.time() - start

    actual = response["output"]["message"]["content"][0]["text"]
    usage = response.get("usage", {})

    print("=" * 60)
    print(actual)
    print("=" * 60)
    print(f"\nLatency: {elapsed:.2f}s")
    print(f"Input tokens:  {usage.get('inputTokens', '?')}")
    print(f"Output tokens: {usage.get('outputTokens', '?')}")

    # Format checks — generic markers that work for any decision class
    markers = [
        "**DECISION:",
        "**LOAN SUMMARY**",
        "PASS",
        "**NEXT STEPS**",
    ]
    print("\n--- FORMAT CHECK ---")
    passed = 0
    for m in markers:
        found = m in actual
        if found:
            passed += 1
        print(f"  {'PASS' if found else 'MISS'}: {m}")

    # Char-level prefix match
    match_len = 0
    for i, (a, e) in enumerate(zip(actual, expected)):
        if a == e:
            match_len = i + 1
        else:
            break
    print(f"\n  Char prefix match: {match_len}")
    print(f"  Format score: {passed}/{len(markers)}")

    if passed == len(markers):
        print("\n>>> FORMAT LOOKS GOOD — fine-tuning is working!")
    elif passed > 0:
        print("\n>>> PARTIAL — fine-tuning has some effect")
    else:
        print("\n>>> FORMAT NOT LEARNED — check training data")


def main():
    parser = argparse.ArgumentParser(description="Manage refi-agent fine-tuning (Nova Lite v2)")
    parser.add_argument("--check", action="store_true", help="Check job status")
    parser.add_argument("--job-arn", help="Specific job ARN to check")
    parser.add_argument("--deploy", action="store_true", help="Deploy the fine-tuned model")
    parser.add_argument("--smoke-test", action="store_true", help="Test the deployment")
    parser.add_argument("--deployment-arn", help="Specific deployment ARN for smoke test")
    args = parser.parse_args()

    bedrock = boto3.client("bedrock", region_name=REGION)

    if args.check:
        check(bedrock, args.job_arn)
    elif args.deploy:
        deploy(bedrock)
    elif args.smoke_test:
        rt = boto3.client("bedrock-runtime", region_name=REGION)
        smoke_test(rt, args.deployment_arn)
    else:
        # Default: launch the job
        launch(bedrock)


if __name__ == "__main__":
    main()
