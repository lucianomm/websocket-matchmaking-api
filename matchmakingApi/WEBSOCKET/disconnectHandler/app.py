import boto3
from botocore.exceptions import ClientError
import os
from matchmakingTableRepository import WebSocketRepository

connection_table_name = os.environ['CONNECTION_TABLE_NAME']  # Replace with the actual table name
connection_table_pk = os.environ['CONNECTION_TABLE_PK']  # Replace with the actual primary key
data_table_name = os.environ['DATA_TABLE_NAME']  # Replace with the actual table name
data_table_pk = os.environ['DATA_TABLE_PK']  # Replace with the actual primary key

def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    
    try:
        wssRepo = WebSocketRepository(connection_table_name, connection_table_pk, data_table_name, data_table_pk)
        wssRepo.disconnect(connection_id)
        return {
            'statusCode': 200
        }
    except ClientError as e:
        print(f'Error: {e}')
        return {
            'statusCode': 500,
            'body': 'Failed to disconnect:'
        }
