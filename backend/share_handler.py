"""
POST /files/{id}/share
Bonus feature: generates a long-lived (24h) pre-signed S3 GET URL that
can be shared with anyone, with no login required to use it - permission
is baked into the signed URL itself. Creating the link is still an
authenticated, owner-only action.
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

    try:
        share_url = s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=86400  # 24 hours
        )
    except Exception:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to generate share link'})
        }

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'message': 'Share link generated successfully',
            'fileId': file_id,
            'shareUrl': share_url,
            'expiresIn': 86400
        })
    }
