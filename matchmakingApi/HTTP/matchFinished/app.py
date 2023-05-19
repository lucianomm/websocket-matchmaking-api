import os
import json
from matchmakingTableRepository import WebSocketRepository, User
from glicko_team import Player, TeamRatingCalculator
from decimal import Decimal

connection_table_name = os.environ['CONNECTION_TABLE_NAME']
connection_table_pk = os.environ['CONNECTION_TABLE_PK']
data_table_name = os.environ['DATA_TABLE_NAME']
data_table_pk = os.environ['DATA_TABLE_PK']


def lambda_handler(event:dict, context):
    body:dict = json.loads(event.get('body', '{}'))
    home_ids: list[str] = body.get('home', [])
    away_ids: list[str] = body.get('away', [])
    result: list[str] = body.get('result', [])
    
    webSocketRepo = WebSocketRepository(connection_table_name, connection_table_pk, data_table_name, data_table_pk)

    for user_id in home_ids + away_ids:
        webSocketRepo.set_user_not_in_match(user_id)

    home_users:list[User] = [webSocketRepo.get_user_data(user_id) for user_id in home_ids]
    away_users:list[User] = [webSocketRepo.get_user_data(user_id) for user_id in away_ids]
    
    away_players = [(Player(user.rating,user.rd,float(user.vol)),user.user_id) for user in away_users]
    home_players = [(Player(user.rating,user.rd,float(user.vol)),user.user_id) for user in home_users]
    
    if result == 'home':
        teamRatingCalculator = TeamRatingCalculator(home_players,away_players,1)
    elif result == 'away':
        teamRatingCalculator = TeamRatingCalculator(home_players,away_players,0)
    elif result == 'draw':
        teamRatingCalculator = TeamRatingCalculator(home_players,away_players,0.5)
    else:
        raise Exception('Invalid result')
    
    for player in away_players + home_players:
        updated_player = teamRatingCalculator.update_rating(player[0])
        webSocketRepo.update_user_rating(player[1],int(updated_player.rating),int(updated_player.rd),Decimal(str(updated_player.vol)))
        
    return {
        'statusCode': 200,
    }
