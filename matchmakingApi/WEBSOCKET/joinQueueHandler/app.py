from botocore.exceptions import ClientError
from matchmakingTableRepository import WebSocketRepository, UserNotFound, UserAlreadyInMatch
import os
import boto3
import json

connection_table_name = os.environ['CONNECTION_TABLE_NAME']  # Replace with the actual table name
connection_table_pk = os.environ['CONNECTION_TABLE_PK']  # Replace with the actual primary key
data_table_name = os.environ['DATA_TABLE_NAME']  # Replace with the actual table name
data_table_pk = os.environ['DATA_TABLE_PK']  # Replace with the actual primary key


def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    eos_id = event['requestContext']['authorizer']['principalId']
    
    endpoint_url="https://"+f"{event['requestContext']['domainName']}"
    apigw_client = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)
    
    wssRepo = WebSocketRepository(connection_table_name, connection_table_pk, data_table_name, data_table_pk)
    
    try:
        region = json.loads(event['body'])['region']
        wssRepo.set_user_region(eos_id, region)
    except (KeyError, TypeError):
        region = ""
    
    try:
        wssRepo.join_queue(connection_id)
        apigw_client.post_to_connection(ConnectionId=connection_id, Data="joined queue")
    except UserNotFound:
        if not region:
            apigw_client.post_to_connection(ConnectionId=connection_id, Data="No region set for user")
        else:
            wssRepo.add_new_user(eos_id, region)
            wssRepo.join_queue(connection_id)
            apigw_client.post_to_connection(ConnectionId=connection_id, Data="joined queue")
    except UserAlreadyInMatch:
        apigw_client.post_to_connection(ConnectionId=connection_id, Data="already in match")
    return {
        'statusCode': 200,
    }
