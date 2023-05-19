import boto3
from decimal import Decimal
from glicko_team import Player
import time
from boto3.dynamodb.conditions import Key

INITIAL_RATING = 1500
INITIAL_RD = 350
VOLATILITY = Decimal('0.06')
TEAM_SIZE = 1
MATCH_SIZE = TEAM_SIZE * 2

class UserRegionNotFound(Exception):
    """
        Exception when user region is not found
    """
    def __init__(self, message="User region not found"):
        self.message = message

class UserNotFound(Exception):
    """
        Exception when user is not found
    """
    def __init__(self, message="User not found"):
        self.message = message
        
class UserExists(Exception):
    """
        Exception when user already exists in Matchmaking Data Table
    """
    def __init__(self, message="User already exists in Matchmaking Data Table"):
        self.message = message

class UserAlreadyInMatch(Exception):
    """
        Exception when user is already in a match
    """
    def __init__(self, message="User is already in a match"):
        self.message = message

class User:
    def __init__(self, user_id, rating:int, rd:int, vol:Decimal, region:str, joined_at:int = 0, connection_id:str = ""):
        self.user_id = str(user_id)
        self.rating = rating
        self.rd = rd
        self.vol = vol
        self.match_history:list[Match] = []
        self.matches_to_evaluate:list[Match] = []
        self.max_matchup_delta = rd * 2
        self.joined_at = joined_at
        self.region = region
        self.connection_id = connection_id
    
    def MaxMatchupRating(self):
        return int(self.rating + self.max_matchup_delta)

    def MinMatchupRating(self):
        return int(self.rating - self.max_matchup_delta)
    
    def Deviance(self):
        return self.rd/173.7178
    
    def Variance(self):
        return self.Deviance()*self.Deviance()
    
class Match:
    def __init__(self, team1:list[User], team2:list[User]):
        self.team1:list[User] = team1
        self.team2:list[User] = team2
        self.win:bool
        
    def set_result(self, win:bool):
        self.win = win
    
class _MatchmakingConnectionRepository:
    def __init__(
            self, 
            table_pk: str, 
            table_name:str, 
            user_id_attr: str, 
            rating_attr: str = "Rating", 
            rd_attr: str = "RD", 
            vol_attr: str = "Vol", 
            joined_at_attr: str = "JoinedAt", 
            region_attr: str = "Matchmaking_Region"
        ):
        self.table_pk = table_pk # connectionId
        
        self.user_id_attr = user_id_attr
        self.rating_attr = rating_attr
        self.rd_attr = rd_attr
        self.vol_attr = vol_attr
        self.joined_at_attr = joined_at_attr
        self.region_attr = region_attr
        
        self.table = boto3.resource('dynamodb').Table(table_name)
    
    def join_queue(self, connectionId: str, rating: int, rd: int, vol: Decimal, region: str):
        self.table.update_item(
            Key={
                self.table_pk: connectionId
            },
            UpdateExpression=f"SET {self.rating_attr} = :rating, {self.rd_attr} = :rd, {self.vol_attr} = :vol, {self.region_attr} = :region, {self.joined_at_attr} = :joined_at",
            ExpressionAttributeValues={
                ':rating': rating,
                ':rd': rd,
                ':vol': vol,
                ':region': region,
                ':joined_at': int(time.time())
            }
        )
        return

    def leave_queue(self, connectionId: str):
        self.table.update_item(
            Key={
                self.table_pk: connectionId
            },
            UpdateExpression=f"DELETE {self.rating_attr}, {self.rd_attr}, {self.vol_attr}, {self.region_attr}, {self.joined_at_attr}"
        )
        return
    
    def get_queue_users(self):
        response = self.table.scan()
        
        items = response['Items']
        while 'LastEvaluatedKey' in response:
            response = self.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])
        
        queue:dict[str,list[User]] = {}
        try:
            for item in items:
                user = (User(
                    connection_id = item[self.table_pk], # type: ignore
                    user_id = item[self.user_id_attr], # type: ignore
                    rating = int(item[self.rating_attr]), # type: ignore
                    rd = int(item[self.rd_attr]), # type: ignore
                    vol= Decimal(item[self.vol_attr]), # type: ignore
                    region= item[self.region_attr], # type: ignore
                    joined_at= int(item[self.joined_at_attr]) # type: ignore
                ))
                if queue.get(user.region,''):
                    queue[user.region].append(user)
                else:
                    queue[user.region] = [user]
        except KeyError:
            return queue
        
        for region in queue.keys():
            queue[region].sort(key=lambda user: user.joined_at)
        return queue
    
    def get_queue_user(self, connectionId: str):
        response = self.table.get_item(
            Key={
                self.table_pk: connectionId
            }
        )
        try:
            item = response['Item'] # type: ignore
            return User(
                connection_id = item[self.table_pk], # type: ignore
                user_id= item[self.user_id_attr], # type: ignore
                joined_at= int(item[self.joined_at_attr]), # type: ignore
                rating= int(item[self.rating_attr]), # type: ignore
                rd= int(item[self.rd_attr]), # type: ignore
                vol= Decimal(item[self.vol_attr]) # type: ignore
            )
        except KeyError:
            raise UserNotFound()
        
    def get_connection_user_id(self, connectionId: str):
        response = self.table.get_item(
            Key={
                self.table_pk: connectionId
            }
        )
        try:
            item = response['Item'] # type: ignore
            userId: str = item[self.user_id_attr] # type: ignore
            return userId
        except KeyError:
            raise UserNotFound()

class _MatchmakingDataRepository:
    def __init__(self, table_name:str, table_pk: str):
        self.table_name = table_name
        self.table_pk = table_pk # user_id
        self.ratingAtt = "Rating"
        self.rdAtt = "RD"
        self.volAtt = "Vol"
        self.regionAtt = "Matchmaking_Region"
        self.playerInMatchAtt = "PlayerInMatch"
        self.ip = "MatchIp"
        
        self.table = boto3.resource('dynamodb').Table(self.table_name)
        
    def set_player_in_match(self, user_id: str, ip: str):
        self.table.update_item(
            Key={
                self.table_pk: user_id
            },
            UpdateExpression=f"SET {self.playerInMatchAtt} = :playerInMatch, {self.ip} = :ip",
            ExpressionAttributeValues={
                ':playerInMatch': True,
                ':ip': ip
            }
        )
        return
    
    def set_player_not_in_match(self, user_id: str):
        self.table.update_item(
            Key={
                self.table_pk: user_id
            },
            UpdateExpression=f"SET {self.playerInMatchAtt} = :playerInMatch REMOVE {self.ip}",
            ExpressionAttributeValues={
                ':playerInMatch': False
            }
        )
        return
        
    def get_user_data(self, user_id: str, connectionId: str):
        response = self.table.get_item(
            Key={
                self.table_pk: user_id
            }
        )
        
        try:
            item = response['Item'] # type: ignore
            user_data: User = User(
                connection_id=connectionId, # type: ignore
                user_id=user_id,
                rating=int(item[self.ratingAtt]), # type: ignore
                rd=int(item[self.rdAtt]), # type: ignore
                vol=Decimal(item[self.volAtt]), # type: ignore
                region=item[self.regionAtt] # type: ignore
            )
        except KeyError:
            raise UserNotFound()
        
        playerInMatch: bool
        try:
            playerInMatch = item[self.playerInMatchAtt] # type: ignore
        except KeyError:
            playerInMatch = False
        
        return user_data, playerInMatch
    
    def set_user_data(self,user_id: str, region: str, rating: int = INITIAL_RATING, rd: int = INITIAL_RD, vol: Decimal = VOLATILITY):
        """
            Sets user data
        """
        
        self.table.put_item(Item={
            self.table_pk: user_id,
            self.ratingAtt: rating,
            self.rdAtt: rd,
            self.volAtt: vol,
            self.regionAtt: region,
            self.playerInMatchAtt: False
        })
        
        return
    
    def set_user_region(self, user_id: str, region: str):
        self.table.update_item(
            Key={
                self.table_pk: user_id
            },
            UpdateExpression=f"SET {self.regionAtt} = :region",
            ExpressionAttributeValues={
                ':region': region
            }
        )
        return
    
    def get_user_region(self, user_id: str):
        response = self.table.get_item(
            Key={
                self.table_pk: user_id
            }
        )
        
        try:
            item = response['Item'] # type: ignore
            region:str = item[self.regionAtt] # type: ignore
            return region
        except KeyError:
            raise UserNotFound()
        
    def update_user_rating(self, user_id: str, rating: int, rd: int, vol: Decimal):
        self.table.update_item(
            Key={
                self.table_pk: user_id
            },
            UpdateExpression=f"SET {self.ratingAtt} = :rating, {self.rdAtt} = :rd, {self.volAtt} = :vol",
            ExpressionAttributeValues={
                ':rating': rating,
                ':rd': rd,
                ':vol': vol
            }
        )
        return
        
class WebSocketRepository:
        
    def __init__(self, connection_table_name: str, connection_table_pk: str, data_table_name: str, data_table_pk: str):
        self._connection_table_name = connection_table_name
        self._connection_table_pk = connection_table_pk
        self._data_table_name = data_table_name
        self._data_table_pk = data_table_pk
        
        self._eos_id_attr = "UserId"

        self._table = boto3.resource('dynamodb').Table(self._connection_table_name)
        self._matchMakingConnectionRepo = _MatchmakingConnectionRepository(table_pk = self._connection_table_pk, table_name=self._connection_table_name, user_id_attr=self._eos_id_attr)
        self._matchMakingDataRepo = _MatchmakingDataRepository(table_name = self._data_table_name, table_pk = self._data_table_pk)

    def connect(self, connectionId: str, user_id: str):
        self._table.put_item(Item={
            self._connection_table_pk: connectionId,
            self._eos_id_attr: user_id
        })
        
    def join_queue(self, connectionId: str):
        
        userId = self._matchMakingConnectionRepo.get_connection_user_id(connectionId)
        user_data, playerInMatch = self._matchMakingDataRepo.get_user_data(userId, connectionId)
        if playerInMatch:
            raise UserAlreadyInMatch()
        
        self._matchMakingConnectionRepo.join_queue(
            connectionId,
            user_data.rating,
            user_data.rd,
            user_data.vol,
            user_data.region
        )
        
    def get_queue_users(self):
        """
        Returns a dict of users in queue where the key is the region and the value is the list of users in that region
        """
        return self._matchMakingConnectionRepo.get_queue_users()
    
    def get_user_data(self,user_id:str, connection_id:str=""):
        user_data, playerInMatch = self._matchMakingDataRepo.get_user_data(user_id,connection_id)
        return user_data
    
    def get_user_region(self, user_id: str):
        return self._matchMakingDataRepo.get_user_region(user_id)
    
    def get_user_id(self, connectionId: str):
        return self._matchMakingConnectionRepo.get_connection_user_id(connectionId)
    
    def add_new_user(self, user_id: str, region: str):
        self._matchMakingDataRepo.set_user_data(user_id, region)
        
    def set_user_region(self, userId: str, region: str):
        self._matchMakingDataRepo.set_user_region(userId, region)
        
    def disconnect(self, connectionId: str):
        self._table.delete_item(Key={
            self._connection_table_pk: connectionId
        })
    
    def leave_queue(self, connectionId: str):
        self._matchMakingConnectionRepo.leave_queue(connectionId)

    def set_user_in_match(self, user_id:str, ip: str):
        self._matchMakingDataRepo.set_player_in_match(user_id, ip)
        
    def set_user_not_in_match(self, user_id: str):
        self._matchMakingDataRepo.set_player_not_in_match(user_id)
        
    def update_user_rating(self, user_id: str, rating: int, rd: int, vol: Decimal):
        self._matchMakingDataRepo.update_user_rating(user_id, rating, rd, vol)