import pandas as pd
import sqlite3

print("Starting IPL pipeline...")

# ── STEP 1: INGEST ────────────────────────────────────────────────────────────
print("Step 1: Loading raw data...")

matches = pd.read_csv('data/matches.csv')
deliveries = pd.read_csv('data/deliveries.csv')

print(f"  Matches loaded: {matches.shape[0]} rows")
print(f"  Deliveries loaded: {deliveries.shape[0]} rows")

# ── STEP 2: CLEAN ─────────────────────────────────────────────────────────────
print("Step 2: Cleaning data...")

# Standardise team names
team_name_map = {
    'Delhi Daredevils': 'Delhi Capitals',
    'Kings XI Punjab': 'Punjab Kings',
    'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
    'Rising Pune Supergiant': 'Rising Pune Supergiants',
    'Deccan Chargers': 'Sunrisers Hyderabad'
}

for col in ['team1', 'team2', 'toss_winner', 'winner']:
    matches[col] = matches[col].replace(team_name_map)

for col in ['batting_team', 'bowling_team']:
    deliveries[col] = deliveries[col].replace(team_name_map)

# Normalise season to start year
def normalize_season(season):
    return int(str(season).split('/')[0])

matches['season'] = matches['season'].apply(normalize_season)

# Fill nulls
matches['city'] = matches['city'].fillna('Unknown')

for col in ['extras_type', 'player_dismissed', 'dismissal_kind', 'fielder']:
    deliveries[col] = deliveries[col].fillna('none')

print("  Cleaning complete")

# ── STEP 3: MODEL ─────────────────────────────────────────────────────────────
print("Step 3: Building dimensional model...")

# dim_player
all_players = pd.concat([
    deliveries['batter'],
    deliveries['bowler'],
    deliveries['non_striker'],
    deliveries['fielder']
]).unique()
all_players = [p for p in all_players if p != 'none']

dim_player = pd.DataFrame({
    'player_id': range(1, len(all_players) + 1),
    'player_name': sorted(all_players)
})

# dim_team
all_teams = pd.concat([
    deliveries['batting_team'],
    deliveries['bowling_team']
]).unique()

dim_team = pd.DataFrame({
    'team_id': range(1, len(all_teams) + 1),
    'team_name': sorted(all_teams)
})

# dim_match
dim_match = matches[['id', 'season', 'date', 'city', 'venue', 'team1', 'team2',
                      'toss_winner', 'toss_decision', 'winner', 'result',
                      'result_margin']].copy()
dim_match = dim_match.rename(columns={'id': 'match_id'})

# fact_deliveries
player_lookup = dict(zip(dim_player['player_name'], dim_player['player_id']))
team_lookup = dict(zip(dim_team['team_name'], dim_team['team_id']))

fact_deliveries = deliveries.copy()
fact_deliveries['batter_id'] = fact_deliveries['batter'].map(player_lookup)
fact_deliveries['bowler_id'] = fact_deliveries['bowler'].map(player_lookup)
fact_deliveries['non_striker_id'] = fact_deliveries['non_striker'].map(player_lookup)
fact_deliveries['fielder_id'] = fact_deliveries['fielder'].map(player_lookup)
fact_deliveries['batting_team_id'] = fact_deliveries['batting_team'].map(team_lookup)
fact_deliveries['bowling_team_id'] = fact_deliveries['bowling_team'].map(team_lookup)
fact_deliveries['fielder_id'] = fact_deliveries['fielder_id'].fillna(0).astype(int)
fact_deliveries['delivery_id'] = range(1, len(fact_deliveries) + 1)

fact_deliveries_final = fact_deliveries[[
    'delivery_id', 'match_id', 'inning', 'over', 'ball',
    'batting_team_id', 'bowling_team_id',
    'batter_id', 'bowler_id', 'non_striker_id', 'fielder_id',
    'batsman_runs', 'extra_runs', 'total_runs',
    'extras_type', 'is_wicket', 'dismissal_kind'
]].copy()

print(f"  dim_player: {dim_player.shape[0]} rows")
print(f"  dim_team: {dim_team.shape[0]} rows")
print(f"  dim_match: {dim_match.shape[0]} rows")
print(f"  fact_deliveries: {fact_deliveries_final.shape[0]} rows")

# ── STEP 4: LOAD ──────────────────────────────────────────────────────────────
print("Step 4: Loading into SQLite...")

conn = sqlite3.connect('ipl_pipeline.db')

dim_player.to_sql('dim_player', conn, if_exists='replace', index=False)
dim_team.to_sql('dim_team', conn, if_exists='replace', index=False)
dim_match.to_sql('dim_match', conn, if_exists='replace', index=False)
fact_deliveries_final.to_sql('fact_deliveries', conn, if_exists='replace', index=False)

conn.close()

print("Step 4: Database loaded successfully")
print("Pipeline complete. Database: ipl_pipeline.db")