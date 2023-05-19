
"""
Copyright (c) 2009 Ryan Kirkman

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
"""

import math

class Player:
    # Class attribute
    # The system constant, which constrains
    # the change in volatility over time.
    _tau = 0.5

    def getRating(self):
        return (self.__rating * 173.7178) + 1500 

    def setRating(self, rating):
        self.__rating = (rating - 1500) / 173.7178

    rating = property(getRating, setRating)

    def getRd(self):
        return self.__rd * 173.7178

    def setRd(self, rd):
        self.__rd = rd / 173.7178

    rd = property(getRd, setRd)
     
    def __init__(self, rating = 1500, rd = 350, vol = 0.06):
        # For testing purposes, preload the values
        # assigned to an unrated player.
        self.setRating(rating)
        self.setRd(rd)
        self.vol = vol
            
    def _preRatingRD(self):
        """ Calculates and updates the player's rating deviation for the
        beginning of a rating period.
        
        preRatingRD() -> None
        
        """
        self.__rd = math.sqrt(math.pow(self.__rd, 2) + math.pow(self.vol, 2))
        
    def update_player(self, rating_list, RD_list, outcome_list):
        """ Calculates the new rating and rating deviation of the player.
        
        update_player(list[int], list[int], list[bool]) -> None
        
        """
        # Convert the rating and rating deviation values for internal use.
        rating_list = [(x - 1500) / 173.7178 for x in rating_list]
        RD_list = [x / 173.7178 for x in RD_list]

        v = self._v(rating_list, RD_list)
        self.vol = self._newVol(rating_list, RD_list, outcome_list, v)
        self._preRatingRD()
        
        self.__rd = 1 / math.sqrt((1 / math.pow(self.__rd, 2)) + (1 / v))
        
        tempSum = 0
        for i in range(len(rating_list)):
            tempSum += self._g(RD_list[i]) * \
                       (outcome_list[i] - self._E(rating_list[i], RD_list[i]))
        self.__rating += math.pow(self.__rd, 2) * tempSum
        
    #step 5        
    def _newVol(self, rating_list, RD_list, outcome_list, v):
        """ Calculating the new volatility as per the Glicko2 system. 
        
        Updated for Feb 22, 2012 revision. -Leo
        
        _newVol(list, list, list, float) -> float
        
        """
        #step 1
        a = math.log(self.vol**2)
        eps = 0.000001
        A = a
        
        #step 2
        B = None
        delta = self._delta(rating_list, RD_list, outcome_list, v)
        tau = self._tau
        if (delta ** 2)  > ((self.__rd**2) + v):
          B = math.log(delta**2 - self.__rd**2 - v)
        else:        
          k = 1
          while self._f(a - k * math.sqrt(tau**2), delta, v, a) < 0:
            k = k + 1
          B = a - k * math.sqrt(tau **2)
        
        #step 3
        fA = self._f(A, delta, v, a)
        fB = self._f(B, delta, v, a)
        
        #step 4
        while math.fabs(B - A) > eps:
          #a
          C = A + ((A - B) * fA)/(fB - fA)
          fC = self._f(C, delta, v, a)
          #b
          if fC * fB < 0:
            A = B
            fA = fB
          else:
            fA = fA/2.0
          #c
          B = C
          fB = fC
        
        #step 5
        return math.exp(A / 2)
        
    def _f(self, x, delta, v, a):
      ex = math.exp(x)
      num1 = ex * (delta**2 - self.__rating**2 - v - ex)
      denom1 = 2 * ((self.__rating**2 + v + ex)**2)
      return  (num1 / denom1) - ((x - a) / (self._tau**2))
        
    def _delta(self, rating_list, RD_list, outcome_list, v):
        """ The delta function of the Glicko2 system.
        
        _delta(list, list, list) -> float
        
        """
        tempSum = 0
        for i in range(len(rating_list)):
            tempSum += self._g(RD_list[i]) * (outcome_list[i] - self._E(rating_list[i], RD_list[i]))
        return v * tempSum
        
    def _v(self, rating_list, RD_list):
        """ The v function of the Glicko2 system.
        
        _v(list[int], list[int]) -> float
        
        """
        tempSum = 0
        for i in range(len(rating_list)):
            tempE = self._E(rating_list[i], RD_list[i])
            tempSum += math.pow(self._g(RD_list[i]), 2) * tempE * (1 - tempE)
        return 1 / tempSum
        
    def _E(self, p2rating, p2RD):
        """ The Glicko E function.
        
        _E(int) -> float
        
        """
        return 1 / (1 + math.exp(-1 * self._g(p2RD) * \
                                 (self.__rating - p2rating)))
        
    def _g(self, RD):
        """ The Glicko2 g(RD) function.
        
        _g() -> float
        
        """
        return 1 / math.sqrt(1 + 3 * math.pow(RD, 2) / math.pow(math.pi, 2))
        
    def did_not_compete(self):
        """ Applies Step 6 of the algorithm. Use this for
        players who did not compete in the rating period.

        did_not_compete() -> None
        
        """
        self._preRatingRD()
    
    def Deviance(self):
        return self.rd/173.7178
    
    def Variance(self):
        return self.Deviance()*self.Deviance()
    
    
# Team Rating Calculator:
# Personal addition to the glicko rating system to allow for team based ratings
class TeamRatingCalculator:
    """
    Calculates the new rating and rating deviation of the player from a team based perspective
    """
    def __init__(self, team1:list[tuple[Player,str]], team2:list[tuple[Player,str]], team1Win: float):
        """
        team1win is a float that can be 0 on lose, 0.5 on draw, 1 on win
        team1 is a list of tuples of the form (Player(glicko), user_id)
        """
        self.team1 = team1
        self.team2 = team2
        self.team1Win = team1Win
        self.glicko_player_index = 0
        self.user_id_index = 1
        
        avg_rating_team1 = sum(player[self.glicko_player_index].rating for player in self.team1) / len(self.team1)
        avg_rating_team2 = sum(player[self.glicko_player_index].rating for player in self.team2) / len(self.team2)
        var_team1 = sum(player[self.glicko_player_index].Variance() for player in self.team1)
        dev_team1 = math.sqrt(var_team1)
        self.rd_team_1 = dev_team1 * 173.7178
        var_team2 = sum(player[self.glicko_player_index].Variance() for player in self.team2)
        dev_team2 = math.sqrt(var_team2)
        self.rd_team_2 = dev_team2 * 173.7178

        self.rating_delta_team1 = avg_rating_team2 - avg_rating_team1
        self.rating_delta_team2 = -(self.rating_delta_team1)
        
        
    def update_rating(self, player:Player):
        
        if player in [player[self.glicko_player_index] for player in self.team1]:
            opponent_assumed_rating = player.rating + self.rating_delta_team1
            rd = self.rd_team_2
            
            player.update_player([opponent_assumed_rating],[rd],[self.team1Win])
            
        elif player in [player[self.glicko_player_index] for player in self.team2]:
            opponent_assumed_rating = player.rating + self.rating_delta_team2
            rd = self.rd_team_1
            
            player.update_player([opponent_assumed_rating],[rd],[abs(1 - self.team1Win)])
        
        else:
            raise ValueError("Player not in either team")
        
        return player