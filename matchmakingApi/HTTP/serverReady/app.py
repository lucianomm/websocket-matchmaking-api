import os
import boto3
import json
from matchmakingTableRepository import WebSocketRepository, Match, User, UserNotFound

connection_table_name = os.environ['CONNECTION_TABLE_NAME']
connection_table_pk = os.environ['CONNECTION_TABLE_PK']
data_table_name = os.environ['DATA_TABLE_NAME']
data_table_pk = os.environ['DATA_TABLE_PK']
matchmaking_endpoint = os.environ['MATCHMAKING_ENDPOINT']


def lambda_handler(event:dict, context):
    headers:dict = event.get('headers', {})
    server_ip:str = headers.get('X-Forwarded-For', '').split(',')[0].strip()
    body:dict = json.loads(event.get('body', '{}'))
    connection_ids: list[str] = body.get('connection_ids', [])
    
    matchmakingDataRepo = WebSocketRepository(connection_table_name, connection_table_pk, data_table_name, data_table_pk)

    for connection_id in connection_ids:
        try:
            user_id = matchmakingDataRepo.get_user_id(connection_id)
        except UserNotFound:
            continue
        matchmakingDataRepo.set_user_in_match(user_id,server_ip)
    
    endpoint_url="https://"+f"{matchmaking_endpoint}"
    apigw_client = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)
    
    for connection_id in connection_ids:
        apigw_client.post_to_connection(ConnectionId=connection_id, Data="server created with ip: " + str(server_ip))
        
    return {
        'statusCode': 200,
    }
