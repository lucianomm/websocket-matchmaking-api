import copy
import random
import glicko2
import matplotlib.pyplot as plt
import numpy as np
import math
from scipy.stats import norm

plt.ion()  # Turn on interactive mode

# Constants
INITIAL_RATING = 1500
INITIAL_RD = 350
NORMAL_RD = 70
TEAM_SIZE = 5
MATCH_SIZE = TEAM_SIZE * 2
PLACEMENT_MATCHES = 3 # Number of matches to play before setting the user's rating for match-by-match updates
THREE_QUARTS_WIN_POINTS = 20 # point difference which represent a 75% chance of team 1 winning
TOTAL_ROUNDS_TO_SIMULATE = 200

class User:
    def __init__(self, user_id, rating:int, rd:int, actual_rating:int, placement:bool = False):
        self.user_id = str(user_id)
        self.glicko_user = glicko2.Player(rating, rd)
        self.actual_rating = actual_rating
        self.glicko_rating_history = [rating]
        self.auto_rating_history = [rating]
        self.match_history:list[Match] = []
        self.matches_to_evaluate:list[Match] = []
        self.max_matchup_delta = rd * 2
        self.matches_played = 0
        self.placement = placement
    
    def MaxMatchupRating(self):
        return int(self.glicko_user.rating + self.max_matchup_delta)

    def MinMatchupRating(self):
        return int(self.glicko_user.rating - self.max_matchup_delta)
    
    def Deviance(self):
        return self.glicko_user.rd/173.7178
    
    def Variance(self):
        return self.Deviance()*self.Deviance()
        
class Match:
    def __init__(self, opponent_rating, opponent_rd, win:bool):
        self.opponent_rating = opponent_rating
        self.opponent_rd = opponent_rd
        self.win = win
        
class Queue_Info:
    def __init__(self, user_info:User, timestamp):
        self.user_info = user_info
        self.timestamp = timestamp
        
# Data structures
queue:list[User] = []
users:list[User] = []
start_users:list[User] = []

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

def assemble_match():
    global users
    global queue

    for user in queue:
        potential_match_players = [user] + [teammate for teammate in queue 
                                   if teammate != user 
                                   and abs(user.glicko_user.rating - teammate.glicko_user.rating) <= user.max_matchup_delta]
        
        match_players = find_intersecting_players(potential_match_players)
        if match_players:
            match_players.sort(key=lambda player: player.glicko_user.rating)
            team1 = [player for i, player in enumerate(match_players) if i % 2 == 0]
            team2 = [player for i, player in enumerate(match_players) if i % 2 == 1]
            for player in match_players:
                queue.remove(player)
            return team1,team2
    return None

def predict_outcome(team1:list[User], team2:list[User]):
    avg_rating_team1 = sum(player.actual_rating for player in team1) / TEAM_SIZE
    avg_rating_team2 = sum(player.actual_rating for player in team2) / TEAM_SIZE
    rating_difference = avg_rating_team1 - avg_rating_team2
    
    scaling_factor = THREE_QUARTS_WIN_POINTS / norm.ppf(0.75) # TWO_THIRDS_WIN_POINTS points difference represent a 75% chance of team 1 winning
    z_score = rating_difference / scaling_factor
    win_probability_team1 = norm.cdf(z_score)
    
    team1Wins = random.random() < float(win_probability_team1)
    
    return team1Wins

def update_match_history(team1:list[User], team2:list[User], team1Win: bool):
    
    global users
    # Calculate the average rating and RD of each team
    avg_rating_team1 = sum(player.glicko_user.rating for player in team1) / TEAM_SIZE
    avg_rating_team2 = sum(player.glicko_user.rating for player in team2) / TEAM_SIZE
    var_team1 = sum(player.Variance() for player in team1)
    dev_team1 = math.sqrt(var_team1)
    rd_team_1 = dev_team1 * 173.7178
    var_team2 = sum(player.Variance() for player in team2)
    dev_team2 = math.sqrt(var_team2)
    rd_team_2 = dev_team2 * 173.7178

    rating_delta_team1 = avg_rating_team2 - avg_rating_team1
    rating_delta_team2 = -(rating_delta_team1)

    for player1 in team1:
        player1.matches_played += 1
        player_index = users.index(player1)
        
        player1.match_history.append(Match(player1.glicko_user.rating + rating_delta_team1, rd_team_1, team1Win))
        player1.matches_to_evaluate.append(Match(player1.glicko_user.rating + rating_delta_team1, rd_team_1, team1Win))
        users[player_index] = player1
        
    for player2 in team2:
        player2.matches_played += 1
        player_index = users.index(player2)
        
        player2.match_history.append(Match(player2.glicko_user.rating + rating_delta_team2, rd_team_2, not team1Win))
        player2.matches_to_evaluate.append(Match(player2.glicko_user.rating + rating_delta_team2, rd_team_2, not team1Win))
        users[player_index] = player2
        
def update_player_ratings_automatically(is_glicko_placement: bool):
    for player in users:
        if not is_glicko_placement:
            player.placement = False
        
        opponent_ratings = [match.opponent_rating for match in player.matches_to_evaluate]
        opponent_rds = [match.opponent_rd for match in player.matches_to_evaluate]
        outcomes = [match.win for match in player.matches_to_evaluate]
        
        if not player.placement and len(player.matches_to_evaluate) >= 1:
                wins = len([wins for wins in outcomes if wins == True])
                losses = len([losses for losses in outcomes if losses == False])
                player.glicko_user.rating += wins*10 # award 10 points for each win
                player.glicko_user.rating -= losses*10 # deduct 10 points for each loss
                player.auto_rating_history.append(player.glicko_user.rating)
                player.matches_to_evaluate.clear()
                
        if player.placement and len(player.matches_to_evaluate) >= PLACEMENT_MATCHES:
            player.glicko_user.update_player(opponent_ratings, opponent_rds, outcomes)
            player.auto_rating_history.append(player.glicko_user.rating)
            player.matches_to_evaluate.clear()
            player.placement = False
            
            error = player.glicko_user.rating - player.actual_rating
            print('PLACEMENT MATCH DONE')
            print(
                f'Player {player.user_id} | '
                f'Rating: {player.glicko_user.rating:<8.2f} | '
                f'Actual Rating: {player.actual_rating:<8.2f} | '
                f'Rating Delta: {error:<8.2f} | '
                f'RD: {player.glicko_user.rd:<8.2f} | '
                f'Matches Played: {player.matches_played} | '
            )
        
def update_player_ratings_glicko(is_glicko_placement:bool):
    global users

    for player in users:
        if not is_glicko_placement:
            player.placement = False
        
        opponent_ratings = [match.opponent_rating for match in player.matches_to_evaluate]
        opponent_rds = [match.opponent_rd for match in player.matches_to_evaluate]
        outcomes = [match.win for match in player.matches_to_evaluate]
        
        if not player.placement and len(player.matches_to_evaluate) >= 1:
            player.glicko_user.update_player(opponent_ratings, opponent_rds, outcomes)
            player.glicko_rating_history.append(player.glicko_user.rating)
            player.matches_to_evaluate.clear()
        if player.placement and len(player.matches_to_evaluate) >= PLACEMENT_MATCHES:
            player.glicko_user.update_player(opponent_ratings, opponent_rds, outcomes)
            player.glicko_rating_history.append(player.glicko_user.rating)
            player.matches_to_evaluate.clear()
            player.placement = False
            
            error = player.glicko_user.rating - player.actual_rating
            print('PLACEMENT MATCH DONE')
            print(
                f'Player {player.user_id} | '
                f'Rating: {player.glicko_user.rating:<8.2f} | '
                f'Actual Rating: {player.actual_rating:<8.2f} | '
                f'Rating Delta: {error:<8.2f} | '
                f'RD: {player.glicko_user.rd:<8.2f} | '
                f'Matches Played: {player.matches_played} | '
            )
            
        player.max_matchup_delta = player.glicko_user.rd * 2
    
    
def restart_users():
    global users
    global start_users
    global queue
    
    queue.clear()
    users = copy.deepcopy(start_users)

def create_players(num_players, min_rating, max_rating):
    global users
    global start_users
    for i in range(num_players):
        rating = int(np.random.normal((max_rating + min_rating)/2, (max_rating - min_rating)/3))
        rating = max(0, rating)  # Ensure the rating is not negative
        user_to_add = User(i, rating, NORMAL_RD, rating)
        users.append(user_to_add)
        
def simulate_matches(num_matches, is_glicko_rating = True, is_glicko_placement = True):
    global queue
    global users
    # Simulate matches
    match_count = 0
    while match_count < num_matches:
        print(f'Match count: {match_count}')
        
        queue_to_reinsert = [user for user in users if user not in queue]
        random.shuffle(queue_to_reinsert)
        queue = queue + queue_to_reinsert # Shuffle queue to prevent bias (keep players that haven't left the queue in priority)
        match = assemble_match()
        while match is not None:
            team1, team2 = match
            team1Win = predict_outcome(team1, team2)
            update_match_history(team1, team2, team1Win)
            if is_glicko_rating:
                update_player_ratings_glicko(is_glicko_placement)
            else:
                update_player_ratings_automatically(is_glicko_placement)
            match = assemble_match()
        match_count += 1

def print_player_ratings():
    global users
    players = users.copy()
    rating_error_sum = 0
    big_error_count = 0
    for player in players:
        error = player.glicko_user.rating - player.actual_rating
        print(
            f'Player {player.user_id} | '
            f'Rating: {player.glicko_user.rating:<8.2f} | '
            f'Actual Rating: {player.actual_rating:<8.2f} | '
            f'Rating Delta: {error:<8.2f} | '
            f'RD: {player.glicko_user.rd:<8.2f} | '
            f'Matches Played: {player.matches_played} | '
        ,end="")
        if abs(error) > 100:
            print('!!!!!!!!!!!! |',end="")
            big_error_count += 1
        if player.matches_played < 2:
            print('???????????? |',end="")
        print()
        rating_error_sum += abs(error)
    print(f'Average rating error: {rating_error_sum / len(players)}')
    print(f'Big error percentage: {big_error_count / len(players) * 100:.2f}%')

def plot_reference_user_rating_history(players: list[User], is_glicko_rating = True):
    reference_users = [player for player in players if "REFERENCE USER" in player.user_id]

    fig, ax = plt.subplots()
    for user in reference_users:
        if is_glicko_rating:
            ax.plot(user.glicko_rating_history, label=f'{user.user_id} (Actual Rating: {user.actual_rating}, RD: {user.glicko_user.rd:<8.2f})')
        else:
            ax.plot(user.auto_rating_history, label=f'{user.user_id} (Actual Rating: {user.actual_rating})')
        ax.axhline(user.actual_rating, linestyle='--', color='gray', alpha=0.5)  # Add a dotted line for actual rating

    ax.set_xlabel('Matches Played')
    ax.set_ylabel('Rating')
    if is_glicko_rating:
        ax.set_title('Rating History of Reference Users (Glicko Rating)')
    else:
        ax.set_title('Rating History of Reference Users (Automatically Updated Rating)')
    ax.legend()
    plt.draw()
    plt.pause(0.001)

def plot_rating_error_distribution(players: list[User], is_glicko_rating = True):
    rating_errors = [player.glicko_user.rating - player.actual_rating for player in players]

    fig, ax = plt.subplots()
    ax.hist(rating_errors, bins=20, edgecolor='black')
    ax.set_xlabel('Rating Error')
    ax.set_ylabel('Frequency')
    if is_glicko_rating:
        ax.set_title('Rating Error Distribution (Glicko Rating)')
    else:
        ax.set_title('Rating Error Distribution (Automatically Updated Rating)')
    plt.draw()
    plt.pause(0.001)

create_players(num_players=100, min_rating=1200, max_rating=1800)
users.append(User("REFERENCE USER 1", INITIAL_RATING, INITIAL_RD, 1700, placement=True))
users.append(User("REFERENCE USER 2", INITIAL_RATING, INITIAL_RD, 1300, placement=True))

start_users = copy.deepcopy(users)

# run simulation without using glicko
simulate_matches(num_matches=TOTAL_ROUNDS_TO_SIMULATE, is_glicko_rating=False, is_glicko_placement=False)
plot_reference_user_rating_history(users, is_glicko_rating=False)
plot_rating_error_distribution(users, is_glicko_rating=False)
print_player_ratings()

# run simulation using glicko
restart_users()
simulate_matches(num_matches=TOTAL_ROUNDS_TO_SIMULATE, is_glicko_rating=True, is_glicko_placement=True)
plot_reference_user_rating_history(users, is_glicko_rating=True)
plot_rating_error_distribution(users, is_glicko_rating=True)
print_player_ratings()

# restart_users()
# simulate_matches(num_matches=100, is_glicko_rating=False, is_glicko_placement=True)
# plot_reference_user_rating_history(users, is_glicko_rating=False)
# plot_rating_error_distribution(users, is_glicko_rating=False)
# print_player_ratings()

plt.ioff()
plt.show()