"""One-time generator for sql/team_name_map.sql.

Not run by the pipeline — this script was used once, by hand, to build the static
mapping table checked into sql/team_name_map.sql. Kept in the repo so the mapping's
origin is auditable (how "Man United" became team_id 985, etc.) and so it can be
re-run if more leagues/seasons are added later.

Input: /tmp/tm_teams_ids.csv, produced with:
  docker compose exec -T db psql -U team -d calcio -t -A -F'|' -c "
    SELECT DISTINCT competition_id, team_name, team_id FROM champagne_results
    WHERE competition_id IN ('GB1','ES1','IT1','L1','FR1') AND season_key >= 2021
    ORDER BY competition_id, team_name;" > /tmp/tm_teams_ids.csv
"""
import csv

# football-data.co.uk short name -> Transfermarkt team_name, per league.
# Built by hand: both sides have the exact same club count per league for 2021-2025
# (27/26/27/25/25), so this is a verified 1:1 pairing, not fuzzy matching.
NAME_MAP = {
    "E0": {
        "Arsenal": "Arsenal FC", "Aston Villa": "Aston Villa",
        "Bournemouth": "AFC Bournemouth", "Brentford": "Brentford FC",
        "Brighton": "Brighton & Hove Albion", "Burnley": "Burnley FC",
        "Chelsea": "Chelsea FC", "Crystal Palace": "Crystal Palace",
        "Everton": "Everton FC", "Fulham": "Fulham FC", "Ipswich": "Ipswich Town",
        "Leeds": "Leeds United", "Leicester": "Leicester City",
        "Liverpool": "Liverpool FC", "Luton": "Luton Town",
        "Man City": "Manchester City", "Man United": "Manchester United",
        "Newcastle": "Newcastle United", "Norwich": "Norwich City",
        "Nott'm Forest": "Nottingham Forest", "Sheffield United": "Sheffield United",
        "Southampton": "Southampton FC", "Sunderland": "Sunderland AFC",
        "Tottenham": "Tottenham Hotspur", "Watford": "Watford FC",
        "West Ham": "West Ham United", "Wolves": "Wolverhampton Wanderers",
    },
    "SP1": {
        "Alaves": "Deportivo Alavés", "Almeria": "UD Almería",
        "Ath Bilbao": "Athletic Bilbao", "Ath Madrid": "Atlético de Madrid",
        "Barcelona": "FC Barcelona", "Betis": "Real Betis Balompié",
        "Cadiz": "Cádiz CF", "Celta": "Celta de Vigo", "Elche": "Elche CF",
        "Espanol": "RCD Espanyol Barcelona", "Getafe": "Getafe CF",
        "Girona": "Girona FC", "Granada": "Granada CF",
        "Las Palmas": "UD Las Palmas", "Leganes": "CD Leganés",
        "Levante": "Levante UD", "Mallorca": "RCD Mallorca",
        "Osasuna": "CA Osasuna", "Oviedo": "Real Oviedo",
        "Real Madrid": "Real Madrid", "Sevilla": "Sevilla FC",
        "Sociedad": "Real Sociedad", "Valencia": "Valencia CF",
        "Valladolid": "Real Valladolid CF", "Vallecano": "Rayo Vallecano",
        "Villarreal": "Villarreal CF",
    },
    "I1": {
        "Atalanta": "Atalanta BC", "Bologna": "Bologna FC 1909",
        "Cagliari": "Cagliari Calcio", "Como": "Como 1907",
        "Cremonese": "US Cremonese", "Empoli": "FC Empoli",
        "Fiorentina": "ACF Fiorentina", "Frosinone": "Frosinone Calcio",
        "Genoa": "Genoa CFC", "Inter": "Inter Milan", "Juventus": "Juventus FC",
        "Lazio": "SS Lazio", "Lecce": "US Lecce", "Milan": "AC Milan",
        "Monza": "AC Monza", "Napoli": "SSC Napoli",
        "Parma": "Parma Calcio 1913", "Pisa": "Pisa Sporting Club",
        "Roma": "AS Roma", "Salernitana": "US Salernitana 1919",
        "Sampdoria": "UC Sampdoria", "Sassuolo": "US Sassuolo",
        "Spezia": "Spezia Calcio", "Torino": "Torino FC",
        "Udinese": "Udinese Calcio", "Venezia": "Venezia FC",
        "Verona": "Hellas Verona",
    },
    "D1": {
        "Augsburg": "FC Augsburg", "Bayern Munich": "Bayern Munich",
        "Bielefeld": "Arminia Bielefeld", "Bochum": "VfL Bochum",
        "Darmstadt": "SV Darmstadt 98", "Dortmund": "Borussia Dortmund",
        "Ein Frankfurt": "Eintracht Frankfurt", "FC Koln": "1.FC Köln",
        "Freiburg": "SC Freiburg", "Greuther Furth": "SpVgg Greuther Fürth",
        "Hamburg": "Hamburger SV", "Heidenheim": "1.FC Heidenheim 1846",
        "Hertha": "Hertha BSC", "Hoffenheim": "TSG 1899 Hoffenheim",
        "Holstein Kiel": "Holstein Kiel", "Leverkusen": "Bayer 04 Leverkusen",
        "M'gladbach": "Borussia Mönchengladbach", "Mainz": "1.FSV Mainz 05",
        "RB Leipzig": "RB Leipzig", "Schalke 04": "FC Schalke 04",
        "St Pauli": "FC St. Pauli", "Stuttgart": "VfB Stuttgart",
        "Union Berlin": "1.FC Union Berlin", "Werder Bremen": "SV Werder Bremen",
        "Wolfsburg": "VfL Wolfsburg",
    },
    "F1": {
        "Ajaccio": "AC Ajaccio", "Angers": "Angers SCO", "Auxerre": "AJ Auxerre",
        "Bordeaux": "FC Girondins Bordeaux", "Brest": "Stade Brestois 29",
        "Clermont": "Clermont Foot 63", "Le Havre": "Le Havre AC",
        "Lens": "RC Lens", "Lille": "LOSC Lille", "Lorient": "FC Lorient",
        "Lyon": "Olympique Lyon", "Marseille": "Olympique Marseille",
        "Metz": "FC Metz", "Monaco": "AS Monaco",
        "Montpellier": "Montpellier HSC", "Nantes": "FC Nantes",
        "Nice": "OGC Nice", "Paris FC": "Paris FC",
        "Paris SG": "Paris Saint-Germain", "Reims": "Stade Reims",
        "Rennes": "Stade Rennais FC", "St Etienne": "AS Saint-Étienne",
        "Strasbourg": "RC Strasbourg Alsace", "Toulouse": "FC Toulouse",
        "Troyes": "ESTAC Troyes",
    },
}

LEAGUE_TO_COMPETITION = {"E0": "GB1", "SP1": "ES1", "I1": "IT1", "D1": "L1", "F1": "FR1"}


def load_tm_ids(path):
    by_comp_name = {}
    with open(path, newline="") as f:
        for competition_id, team_name, team_id in csv.reader(f, delimiter="|"):
            by_comp_name[(competition_id, team_name)] = int(team_id)
    return by_comp_name


def main():
    tm_ids = load_tm_ids("/tmp/tm_teams_ids.csv")
    rows = []
    missing = []
    for league_code, mapping in NAME_MAP.items():
        competition_id = LEAGUE_TO_COMPETITION[league_code]
        for source_name, tm_name in mapping.items():
            key = (competition_id, tm_name)
            if key not in tm_ids:
                missing.append((league_code, source_name, tm_name))
                continue
            rows.append((league_code, source_name, tm_ids[key], tm_name))

    if missing:
        raise SystemExit(f"Unresolved mappings: {missing}")

    print(f"-- {len(rows)} rows, generated by sql/seed_team_name_map.py")
    print("CREATE TABLE IF NOT EXISTS team_name_map (")
    print("    league_code TEXT NOT NULL,")
    print("    source_name TEXT NOT NULL,")
    print("    team_id INTEGER NOT NULL,")
    print("    team_name TEXT NOT NULL,")
    print("    PRIMARY KEY (league_code, source_name)")
    print(");")
    print("TRUNCATE team_name_map;")
    print("INSERT INTO team_name_map (league_code, source_name, team_id, team_name) VALUES")
    lines = [
        f"    ('{lc}', '{sn.replace(chr(39), chr(39)*2)}', {tid}, "
        f"'{tn.replace(chr(39), chr(39)*2)}')"
        for lc, sn, tid, tn in rows
    ]
    print(",\n".join(lines) + ";")


if __name__ == "__main__":
    main()
