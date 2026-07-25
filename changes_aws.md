### Overview
We have completely migrated our database strategy from local/containerized MongoDB to Amazon DynamoDB (AWS Managed) and configured the necessary AWS infrastructure (IAM, VPC Endpoints, and ECS Environment Variables).

### Required Code Modifications
Please update the FastAPI backend (`workout-agent`) to support DynamoDB as follows:

1. Dependencies:
   - Remove `pymongo` / MongoDB drivers.
   - Add `boto3>=1.34.0` to `requirements.txt`.

2. Lifespan Cleanup (`api/main.py`):
   - Remove any call to `ensure_indexes()` or MongoDB initialization routines inside the FastAPI `lifespan` context manager.

3. DynamoDB Integration (`tools/dynamo.py` or equivalent):
   - Use `boto3.resource('dynamodb')` without hardcoding AWS credentials (IAM Task Roles and VPC Endpoints are already configured in ECS).
   - Read configuration from environment variables:
     * `AWS_REGION` (default: `eu-north-1`)
     * `DYNAMODB_TABLE_NAME` (default: `workout_users`)

4. Data Queries & Schema:
   - Primary Key: `user_id` (String)
   - Querying by Google Identifier: Use the Global Secondary Index (GSI) named `google_sub-index` where `google_sub` is the Partition Key.
   - Query Example for `google_sub`:
     ```python
     response = table.query(
         IndexName='google_sub-index',
         KeyConditionExpression=Key('google_sub').eq(google_sub_val)
     )
     ```

5. Build & Deployment:
   - Build and push the updated Docker image to AWS ECR so ECS Fargate can pull the new release.