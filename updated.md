Here are the confirmed specifications and local development setup:

1. AWS Region & Table Name:
   - Region: eu-north-1
   - Table Name: workout_users
   - Primary Key: user_id (String)

2. GSI Details (Action Required on AWS / Code):
   - In AWS Console, the GSI is currently created as: google_sub-index on Partition Key: google_sub.
   - If the system auth uses `username`, please construct the queries expecting partition key `username`. 
   - Note: I will update/re-create the GSI in AWS Console to be named `username-index` on partition key `username` to match the exact spec so queries won't fail.

3. Local Development Credentials:
   - The ECS Task Role strategy is strictly for production on Fargate.
   - For local development, please configure standard AWS SDK fallback in code:
     It should read AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from the local `.env` file if present, otherwise fall back to default AWS credentials chain / Task Role in production.
   - I will provide the AWS IAM Access Key / Secret for local testing directly in my local `.env` file.

Please update the backend code logic using `boto3` to support this setup!