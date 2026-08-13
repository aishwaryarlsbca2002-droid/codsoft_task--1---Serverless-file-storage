"""
GET /files
Returns every file belonging to the authenticated user, via a fast
DynamoDB Query on the userId partition key (no S3 access needed).
"""
import json
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
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
        response = table.query(
            KeyConditionExpression=Key('userId').eq(user_id)
        )
        files = response.get('Items', [])
    except Exception:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to retrieve files'})
        }

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'files': files,
            'count': len(files)
        })
    }
