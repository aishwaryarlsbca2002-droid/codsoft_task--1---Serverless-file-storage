"""
POST /files
Generates a pre-signed S3 PUT URL for uploading a file, and records
the file's metadata in DynamoDB. The actual file bytes are uploaded
directly from the browser to S3 using the returned URL (Lambda never
touches the file content itself).
"""
import json
import boto3
import uuid
from datetime import datetime, timezone

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = 'aishwarya-filestorage-8823'
TABLE_NAME = 'FileMetadata'
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    # Extract the user's ID from the Cognito token that API Gateway verified
    try:
        claims = event['requestContext']['authorizer']['jwt']['claims']
        user_id = claims['sub']
    except KeyError:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthorized - missing user identity'})
        }

    # Parse the incoming JSON body sent by the frontend
    try:
        body = json.loads(event['body'])
        file_name = body['fileName']
        content_type = body['contentType']
    except (KeyError, TypeError, json.JSONDecodeError):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid request - fileName and contentType are required'})
        }

    # Basic validation
    file_name = file_name.strip()

    if not file_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'File name cannot be empty'})
        }

    BLOCKED_EXTENSIONS = ('.exe', '.bat', '.sh', '.cmd', '.msi', '.dll')
    if file_name.lower().endswith(BLOCKED_EXTENSIONS):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'This file type is not allowed'})
        }

    if len(file_name) > 200:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'File name is too long'})
        }

    # Generate a unique ID for this file
    file_id = str(uuid.uuid4())

    # Build the S3 object key: users/{userId}/{fileId}-{filename}
    # This structure is what enforces per-user isolation of files.
    s3_key = f"users/{user_id}/{file_id}-{file_name}"

    # Generate a pre-signed URL that allows a temporary, direct upload to S3
    try:
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ContentType': content_type
            },
            ExpiresIn=300  # 5 minutes
        )
    except Exception:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to generate upload URL'})
        }

    # Record this file's metadata in DynamoDB
    upload_timestamp = datetime.now(timezone.utc).isoformat()

    try:
        table.put_item(
            Item={
                'userId': user_id,
                'fileId': file_id,
                'fileName': file_name,
                's3Key': s3_key,
                'contentType': content_type,
                'uploadDate': upload_timestamp,
                'status': 'pending'
            }
        )
    except Exception:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to save file metadata'})
        }

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'fileId': file_id,
            'uploadUrl': presigned_url,
            'fileName': file_name,
            's3Key': s3_key
        })
    }
