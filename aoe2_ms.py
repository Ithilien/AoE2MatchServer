import itertools
import os

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from flask import Flask

SPREADSHEET_ID = '1c2Kvc3y1GrF9EFqAKvPoRU8NmFV_exCrAeCTrmDct2Y'
ELOS_RANGE = 'Prod!A2:ZZ12'
TEAMS_RANGE = 'Prod!A16:ZZ26'

app = Flask(__name__);

class Player(object):
    def __init__(self, name, score):
        self.name = name
        self.score = score

    def __eq__(self, other):
      return self.name == other.name

    def __hash__(self):
      return hash(self.name)

    def __str__(self):
      return self.name

class Team(object):
    def __init__(self, players, score):
        self.players = frozenset(players)
        self.score = score

    def __eq__(self, other):
      return self.players == other.players

    def __hash__(self):
      return hash(self.players)

    def __str__(self):
      p = list(self.players)
      p.sort(key=lambda x: x.name)
      return ",".join([str(self.score)] + [str(player) for player in p])

class Match(object):
    def __init__(self, unfairness, teams):
        self.unfairness = unfairness
        self.teams = frozenset(teams)

    def __eq__(self, other):
      return self.teams == other.teams

    def __hash__(self):
      return hash(self.teams)

    def __str__(self):
      return ",".join(sorted([str(team) for team in self.teams]))
        
class Sheets(object):
    def __init__(self, api_key):
        service = build('sheets', 'v4', developerKey=api_key)
        self._sheets = service.spreadsheets()

    def get_players(self):
        result = self._sheets.values().get(spreadsheetId=SPREADSHEET_ID,
                                           range=ELOS_RANGE).execute()
        values = result.get('values', [])
        if not values:
            raise RuntimeError('No elo data found.')
        elos = {}
        for row in values:
            name = row[0]
            elos[name] = Player(name, int(row[-1]))
        return elos

    def get_current_player_names(self):
        """Returns the list of players to calculate teams for.
        This is determined by looking at the "Team" rows of the
        spreadsheet, and choosing all players with a "?" in the
        last column.
        """
        result = self._sheets.values().get(spreadsheetId=SPREADSHEET_ID,
                                           range=TEAMS_RANGE).execute()
        values = result.get('values', [])
        if not values:
            raise RuntimeError('No team data found.')
        players = []
        last_column = max(len(row) for row in values) - 1
        for row in values:
            if last_column < len(row) and row[last_column] == '?':
                players.append(row[0])
        return players

class TeamChooser(object):
    def team_score(self, players):
        return sum(p.score for p in players)
    def best_teams(self, players, num_teams=2, results_to_show=3):
        results = set()  # (team_score_difference, team_1, team_2)
        for order in itertools.permutations(players.values()):
            # Choose teams by deciding positions at which to split the permutation
            for inds in itertools.combinations(range(len(players)), num_teams-1):
                inds = (0,) + inds + (len(players),)
                teams = [ order[inds[i]:inds[i+1]] for i in range(num_teams) ]
                teams = [ Team(team, self.team_score(team)) for team in teams ]
                scores = [ self.team_score(team.players) for team in teams ]
                mean = sum(scores) / len(scores)
                unfairness = sum(abs(score-mean) for score in scores)
                results.add((unfairness, Match(unfairness, teams)))
        results = list(results)
        results.sort(key=lambda x: (x[0], str(x[1])))
        return [ match for (_, match) in (results[:results_to_show]) ]

@app.route('/')
def run():
    api_key = os.environ['API_KEY']
    sheets = Sheets(api_key)
    all_players = sheets.get_players()
    current = sheets.get_current_player_names()
    players = { k: v for k, v in all_players.items() if k in current }
    chooser = TeamChooser()
    matches = chooser.best_teams(players, 2)

    style = """
<style>
.container {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  font-family: Helvetica;
  font-weight: 400;
  font-size: 18px;
  color: #828282;
}

.team {
  margin: 12px 0 24px;
}

.name {
  margin-top: 12px;
}

.title, .chaos {
  font-family: Impact;
  color: #333333;
  font-weight: 900;
}

.chaos {
  color: #4f4f4f;
}

.title {
  font-size: 24px;
}

.roster {
  display: flex;
  width: 360px;
}

.column {
  flex-grow: 1;
  text-align: center;
}

.score {
  font-size: 14px;
}
</style>
"""
    s = '<body>\n'
    s += style
    s += '<div class="container">\n'
    s += '<div class="title">Wilkinsapian AOE Team Generator</div>\n'
    for i, match in enumerate(matches):
        teams = list(match.teams)
        teams.sort(key=lambda x: x.score)
        s += '<div class="team">\n'
        team1, team2 = teams
        s += '<div class="chaos">Option {}: {} vs {}</div>\n'.format(i+1, team1.score, team2.score, team1.score - team2.score)
        s += '<div class="roster">\n'
        for team in teams:
            s += '<div class="column">\n'
            players = list(team.players)
            players.sort(key=lambda x: x.score)
            for player in players:
                s += '<div class="name">{}</div>\n'.format(player.name)
                s += '<div class="score">{}</div>\n'.format(player.score)
            s += '</div>\n'
        s += '</div>\n'
        s += '</div>\n'
    s += '</div>\n'
    s += '</body>\n'
    return s
