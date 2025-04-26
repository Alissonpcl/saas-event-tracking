# AWS Implementation Guide

## Creating the S3 Bucket

1. Access the AWS console and navigate to the S3 service.
1. Click on "Create bucket."
1. Configure the bucket:
    1. Name: saas-event-tracking (use a unique name).
    1. Region: select the same region for all services (e.g., us-east-1).
    1. Access settings: Block public access (recommended).
    1. Versioning: Optional (enable if you want version history).
    1. Encryption: Enable default SSE-S3 encryption.

## Lambda Function

### Create the Lambda Function

1. In the AWS console, navigate to the Lambda service.
1. Click on "Create function."
1. Select "Author from scratch."
1. Configure the basic details:
    1. Function name: saas-event-tracking-processor.
    1. Runtime: Python 3.11 (or available version).
    1. Architecture: x86_64.
1. Under "Permissions," select "Create a new role with basic Lambda permissions."
    1. This will create a role with basic CloudWatch Logs permissions.
1. Click on "Create function."

**Add S3 Permissions to the IAM Role**

After the Lambda function is created:

1. On the Lambda function page, scroll to "Configuration" and click on "Permissions."
1. Click on the execution role name to open it in the IAM console.
1. In the IAM console, click on "Add permissions" and then "Create inline policy."
1. Select the "JSON" tab and insert the policy below (you can also keep existing permissions and add only the content of *Statement*):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::saas-event-tracking/*",
                "arn:aws:s3:::saas-event-tracking"
            ]
        }
    ]
}
```

1. Click on "Review policy."
1. Name the policy, e.g., LambdaS3EventTracking.
1. Click on "Create policy."

### Configure the Function Code

1. On the newly created function page, scroll down to the "Function code" section.
1. In the code editor, replace the default code with the Python code below:

```python
import json
import boto3
import time
import os
from datetime import datetime

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'your-event-tracking-bucket')  # Configure in environment variables
AUTH_TOKEN = "qwe123-saas-tracking"  # Required auth token

def lambda_handler(event, context):
    try:
        # Check for the authentication token
        # This is a simple example of how it can be done. 
        # A better approach would be to look for a key of 
        # an authenticated token in a cache (eg.: Redis, ElastiCache)
        headers = event.get('headers', {}) or {}
        auth_token = headers.get('x-auth-token')
        
        # Validate the auth token
        if not auth_token or auth_token != AUTH_TOKEN:
            return {
                'statusCode': 401,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'message': 'Unauthorized: Invalid or missing authentication token',
                    'headers': event
                })
            }
        
        # Get the request body
        body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        
        # Validate if it's a single event or a batch
        events = body if isinstance(body, list) else [body]
        
        # Add processing timestamp if it doesn't exist
        for evt in events:
            if 'event_time' not in evt:
                evt['event_time'] = datetime.utcnow().isoformat()
        
        # Define file path with partitioning
        now = datetime.utcnow()
        year, month, day, hour = now.year, now.month, now.day, now.hour
        
        # Create a unique file name
        file_name = f"events_{time.time_ns()}.json"
        key = f"events/year={year}/month={month:02d}/day={day:02d}/hour={hour:02d}/{file_name}"
        
        # Save events to S3
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json.dumps(events),
            ContentType='application/json'
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',  # Allow CORS
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': f'Successfully processed {len(events)} event(s)',
                'events_count': len(events)
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': f'Error processing events: {str(e)}'
            })
        }
```        

### Configure Environment Variables

1. Scroll down to the "Environment variables" section.
1. Click on "Edit."
1. Add a new variable:
    1. Key: BUCKET_NAME.
    1. Value: saas-event-tracking
1. Click on "Save."

### Configure Function Settings

1. Scroll up and click on the "Configuration" tab.
1. Click on "General configuration" and then "Edit."
1. Configure:
    1. Memory: 128 MB (sufficient for this case).
    1. Timeout: 10 seconds (adjust as needed).
    1. Reserved concurrency: (leave as default).
1. Click on "Save."

### Test the Function

1. Go back to the Lambda function page.
1. Click on "Test" in the side panel.
1. Click on "Create new event."
1. Configure the test event:
    1. Event name: TestEventAPI.
    1. Event body:

```json
{
  "body": [
    {
      "event_name": "test_event",
      "user_id": "test_user_123",
      "properties": {
        "action": "test_lambda"
      }
    }
  ]
}
```

1. Click on "Save" and then "Test."
1. Verify that the test is successful and that the file was created in the S3 bucket.

## API Gateway

### Create a New API

1. On the API Gateway homepage, click the "Create API" button.
1. Select "REST API" and then "Build."
1. On the configuration screen:
    1. Choose "New API."
    1. API name: saas-event-tracking-api.
    1. Endpoint type: Regional.
1. Click on "Create API."

### Create a Resource

1. With the API created, you will be on the resources screen.
1. Click the "Create Resource" button.
1. Configure the resource:
    1. Uncheck the "Proxy resource" option.
    1. Resource name: events.
    1. Resource path: /.
    1. Enable the CORS option.
1. Click on "Create Resource."

### Create the POST Method

1. With the /events resource selected, click on "Create Method."
1. In the dropdown menu, select "POST" and click the checkmark icon.
1. Configure the method:
    1. Integration type: Lambda Function.
    1. Lambda Function: Enter the name of your Lambda function (event-tracking-processor).
    1. Enable Lambda proxy integration
        1. This is important so Api Getaway will pass request header to your Lambda function
    1. Integration timeout: leave as default (29 seconds).
1. Click on "Create Method."

### Configure CORS (Cross-Origin Resource Sharing)

1. Select the /events resource.
1. Click on the "Actions" menu and select "Enable CORS."
1. Configure the CORS options:
    1. ACCESS-CONTROL-ALLOW-ORIGIN: * (or your specific domain for better security).
    1. ACCESS-CONTROL-ALLOW-HEADERS: Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token.
    1. ACCESS-CONTROL-ALLOW-METHODS: Select POST and OPTIONS.
1. Click on "Enable CORS and replace existing methods."
1. Confirm by clicking "Yes, replace existing."

### Deploy the API

1. In the "Actions" menu, select "Deploy API."
1. In the deployment window:
    1. Stage: [New Stage].
    1. Stage name: **prod** (or another name of your choice).
    1. Stage description: **Production environment.**
1. Click on "Deploy."

### Get the API URL

1. In the side menu, click on "Stages."
1. Select the prod stage.
1. Note the URL displayed at the top of the page (Invoke URL).