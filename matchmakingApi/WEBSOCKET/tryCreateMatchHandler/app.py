from glicko_team import Player
import random
from matchmakingTableRepository import WebSocketRepository, User, Match, MATCH_SIZE
from botocore.exceptions import ClientError
import os
import boto3

connection_table_name = os.environ['CONNECTION_TABLE_NAME']  # Replace with the actual table name
connection_table_pk = os.environ['CONNECTION_TABLE_PK']  # Replace with the actual primary key
data_table_name = os.environ['DATA_TABLE_NAME']  # Replace with the actual table name
data_table_pk = os.environ['DATA_TABLE_PK']  # Replace with the actual primary key

def find_intersecting_players(potential_match_players: list[User]):
    if len(potential_match_players) < MATCH_SIZE:
        return None

    next_candidate_index = MATCH_SIZE

    # Initialize the list of candidates
    candidates = potential_match_players[:MATCH_SIZE]

    while len(potential_match_players) >= MATCH_SIZE:
        lowest_maximum_player = min(candidates, key=lambda player: player.MaxMatchupRating()) # Lowest rating the match can have
        highest_minimum_player = max(candidates, key=lambda player: player.MinMatchupRating()) # Highest rating the match can have

        if lowest_maximum_player.MaxMatchupRating() >= highest_minimum_player.MinMatchupRating(): # Found a match, allowed ratings within the range of all players
            return candidates
        
        replaced_candidates = False
        while not replaced_candidates:
            if len(potential_match_players) < next_candidate_index + 1:
                return None
            next_candidate = potential_match_players[next_candidate_index]
            
            
            if next_candidate.MinMatchupRating() < highest_minimum_player.MinMatchupRating() and next_candidate.MaxMatchupRating() > lowest_maximum_player.MaxMatchupRating(): # Next candidate is a better fit
                
                if random.random() < 0.5: # Replace the highest minimum player
                    candidates.remove(highest_minimum_player)
                    potential_match_players.remove(highest_minimum_player)
                    candidates.append(next_candidate)
                else: # Replace the lowest maximum player
                    candidates.remove(lowest_maximum_player)
                    potential_match_players.remove(lowest_maximum_player)
                    candidates.append(next_candidate)
                
                replaced_candidates = True
            else:
                potential_match_players.remove(next_candidate)
    
def find_matches_from_queue(queue:list[User]):
    matches_created:list[Match] = []
    if len(queue) < MATCH_SIZE:
        return matches_created
    for user in queue:
        potential_match_players = [user] + [
            teammate for teammate in queue 
            if teammate != user 
            and abs(user.rating - teammate.rating) <= user.max_matchup_delta
        ]
    
        match_players = find_intersecting_players(potential_match_players)
        if match_players:
            match_players.sort(key=lambda player: player.rating)
            
            team1a = [player for i, player in enumerate(match_players) if i % 2 == 0] 
            team2a = [player for i, player in enumerate(match_players) if i % 2 == 1]
            
            team1b = [player for i, player in enumerate(match_players) if i % 4 <= 1]
            team2b = [player for i, player in enumerate(match_players) if i % 4 >= 2]
            
            avarage_a = abs(sum([player.rating for player in team1a]) - sum([player.rating for player in team2a]))/MATCH_SIZE
            avarage_b = abs(sum([player.rating for player in team1b]) - sum([player.rating for player in team2b]))/MATCH_SIZE
            
            if avarage_a < avarage_b:
                team1 = team1a
                team2 = team2a
            else:
                team1 = team1b
                team2 = team2b
                
            for player in match_players:
                queue.remove(player)
            matches_created.append(Match(team1, team2))
    return matches_created

def get_subnet_id_by_name(subnet_name:str, region_name:str):
    ec2_client = boto3.client('ec2', region_name=region_name)
    response = ec2_client.describe_subnets(
        Filters=[
            {
                'Name': 'tag:Name',
                'Values': [subnet_name]
            }
        ]
    )

    subnets = response['Subnets']
    if not subnets:
        raise ValueError(f"No subnet found with name '{subnet_name}'")
    return subnets[0]['SubnetId'] # type: ignore

def get_security_group_id_by_name(security_group_name, region_name):
    ec2 = boto3.client('ec2', region_name=region_name)
    
    filters = [
        {
            'Name': 'tag:Name',
            'Values': [security_group_name]
        }
    ]
    
    response = ec2.describe_security_groups(Filters=filters) # type: ignore
    
    if len(response['SecurityGroups']) == 0:
        raise Exception(f"Security group with name '{security_group_name}' not found in region '{region_name}'")
    elif len(response['SecurityGroups']) > 1:
        raise Exception(f"Multiple security groups with name '{security_group_name}' found in region '{region_name}'")

    return response['SecurityGroups'][0]['GroupId'] # type: ignore

def run_ecs_task(user_ids: list[str], connection_ids: list[str], region_name: str):
    ecs_client = boto3.client('ecs', region_name=region_name)
    
    user_ids_str = ','.join(str(uid) for uid in user_ids)
    connection_ids_str = ','.join(str(cid) for cid in connection_ids)

    response = ecs_client.run_task(
        cluster='MATCHMAKING-CLUSTER',
        taskDefinition='matchmaking-server',
        overrides={
            'containerOverrides': [
                {
                    'name': 'GameServerContainer',
                    'environment': [
                        {
                            'name': 'USER_IDS',
                            'value': user_ids_str
                        },
                        {
                            'name': 'CONNECTION_IDS',
                            'value': connection_ids_str
                        }
                    ]
                }
            ]
        },
        launchType='FARGATE',
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': [
                    get_subnet_id_by_name('MatchmakingSubnetA',region_name=region_name),
                ],
                'securityGroups': [
                    get_security_group_id_by_name(f'MATCHMAKING-CLUSTER-{region_name}-SecurityGroup', region_name=region_name),
                ],
                'assignPublicIp': 'ENABLED'
            }
        },
        count=1,
    )
    return response

def create_match(match: Match):
    user_ids = [user.user_id for user in match.team1 + match.team2]
    connection_ids = [user.connection_id for user in match.team1 + match.team2]
    run_ecs_task(user_ids=user_ids, connection_ids=connection_ids, region_name=match.team1[0].region)
    return

def try_alert_users(match: Match, apigw_client,message:str):
    """
    Sends a message to all users in a match.
    Returns True if all messages were sent successfully, False otherwise (indicating wss connection is closed/stale)
    """
    for user in match.team1 + match.team2:
        try:
            apigw_client.post_to_connection(
                ConnectionId=user.connection_id,
                Data=message
            )
        except Exception:
            return False
    return True

def lambda_handler(event, context):
    endpoint_url="https://"+f"{event['requestContext']['domainName']}"
    apigw_client = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)
    
    try:
        wssRepo = WebSocketRepository(connection_table_name, connection_table_pk, data_table_name, data_table_pk)
        queue = wssRepo.get_queue_users()
        for region in queue.keys():
            matches = find_matches_from_queue(queue[region])
            for match in matches:
                
                if not try_alert_users(match, apigw_client, "MATCH FOUND"):
                    try_alert_users(match, apigw_client, "ERROR: Error in match creation")
                    continue
                
                create_match(match)
                for user in match.team1 + match.team2:
                    wssRepo.set_user_in_match(user.user_id, 'ip_to_be_determined')
                
                for user in match.team1 + match.team2:
                    wssRepo.leave_queue(user.connection_id)
            return {
                'statusCode': 200,
            }
    except ClientError as e:
        return {
            'statusCode': 500,
            'body': f"Error: AWS CLIENT ERROR"
        }
