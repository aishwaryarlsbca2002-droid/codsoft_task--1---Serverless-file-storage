"""
DELETE /files/{id}
Ownership-checked delete. Removes the object from S3 first, then the
metadata row from DynamoDB - deleting S3 first means a partial failure
leaves at worst an orphaned metadata row (visible/fixable), rather than
an orphaned file in storage with no record of it anywhere.
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
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
    except Exception:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to delete file from storage'})
        }

    try:
        table.delete_item(Key={'userId': user_id, 'fileId': file_id})
    except Exception:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'File was deleted from storage but metadata cleanup failed'})
        }

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'message': 'File deleted successfully',
            'fileId': file_id
        })
    }
