"""
GET /files/{id}
Looks up a specific file scoped to the requesting user (userId + fileId
combined key = the ownership check) and returns a short-lived pre-signed
S3 GET URL. A file that exists but belongs to someone else returns the
same 404 as a file that doesn't exist at all, to avoid leaking existence.
"""
import json
import boto3

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = 'aishwarya-filestorage-8823'
TABLE_NAME = 'FileMetadata'
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    try:
        claims = event['requestContext']['authorizer']['jwt']['claims']
        user_id = claims['sub']
    except KeyError:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthorized - missing user identity'})
        }

    try:
        file_id = event['pathParameters']['id']
    except (KeyError, TypeError):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'File ID is required in the URL'})
        }

    try:
        response = table.get_item(
            Key={'userId': user_id, 'fileId': file_id}
        )
    except Exception:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to look up file'})
        }

    if 'Item' not in response:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'File not found'})
        }

    file_item = response['Item']
    s3_key = file_item['s3Key']

    # ResponseContentDisposition forces the browser to download (rather
    # than preview) the file, even when fetched cross-origin from S3.
    try:
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ResponseContentDisposition': f'attachment; filename="{file_item["fileName"]}"'
            },
            ExpiresIn=300
        )
    except Exception:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to generate download URL'})
        }

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'fileId': file_id,
            'fileName': file_item['fileName'],
            'downloadUrl': presigned_url
        })
    }
