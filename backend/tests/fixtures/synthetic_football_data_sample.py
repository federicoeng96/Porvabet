"""A hand-written CSV sample matching football-data.co.uk's REAL verified column
layout (see DATA_SOURCES.md / app/providers/football_data_co_uk/provider.py —
including the "C" closing-odds columns confirmed against a real downloaded
2024/25 Premier League file and the live notes.txt), but with entirely
SYNTHETIC values — invented team names and results, not a real season. This
exists only to unit-test the parser's column handling (dates, generic
bookmaker discovery incl. pre-closing vs. closing, missing columns across
"seasons") without needing network access to the live site on every test run.
It must never be treated as real match data.
"""

SYNTHETIC_FOOTBALL_DATA_CSV = """Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Referee,HS,AS,HST,AST,HC,AC,HF,AF,HY,AY,HR,AR,B365H,B365D,B365A,PSH,PSD,PSA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,B365>2.5,B365<2.5,Max>2.5,Max<2.5,Avg>2.5,Avg<2.5,B365CH,B365CD,B365CA,PSCH,PSCD,PSCA,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5
E0,12/08/2023,15:00,Synthetic United,Synthetic City,2,1,H,1,0,H,A. Referee,14,9,6,3,7,4,10,12,2,3,0,0,1.90,3.60,4.20,1.95,3.55,4.10,2.00,3.70,4.30,1.92,3.58,4.15,1.85,1.95,1.90,2.00,1.87,1.93,1.88,3.65,4.10,1.93,3.50,4.05,1.83,1.97,1.86,1.94
E0,19/08/2023,17:30,Synthetic Rovers,Synthetic Athletic,0,0,D,0,0,D,B. Whistle,8,11,2,5,3,6,11,9,3,1,0,0,2.50,3.20,2.90,2.55,3.15,2.85,2.60,3.25,2.95,2.52,3.18,2.88,2.10,1.75,2.15,1.78,2.11,1.76,2.45,3.25,2.95,2.50,3.20,2.90,2.05,1.80,2.08,1.78
E0,26/08/2023,15:00,Synthetic Town,Synthetic Wanderers,3,2,H,2,1,H,A. Referee,17,13,8,6,9,5,8,10,1,2,0,1,1.70,3.80,5.00,1.72,3.75,4.90,1.75,3.90,5.10,1.71,3.82,4.95,1.60,2.30,1.65,2.35,1.61,2.28,1.68,3.85,5.05,1.70,3.80,4.95,1.58,2.32,1.59,2.30
"""
