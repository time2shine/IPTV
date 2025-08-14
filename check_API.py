from googleapiclient.discovery import build

keys = [
    "AIzaSyCgJaZsz-tsyAaIJRLc5NRYQyC-vnTCwAI",  # rokonmagura
    "AIzaSyBX_LlRNOxBzT5eAWzRiCWNjFS000uqsBQ",  # allmybooks
    "AIzaSyBQYlMpMxV9tmKl9GmrxldwZhOrf7NCfs4",  # farzanazamanmunia
    "AIzaSyDm19wlhqTIThL6FTfMRKSgs0jIq689nQU", # deshirambo17
    "AIzaSyC4KNVzGqbfgikRGM63R3LCt4CRwAtRdYU", # deshirambo18
    "AIzaSyCzk9DwsciObuhF3sNUbX1BdBBt0sNRwOw", # deshirambo19
]

for key in keys:
    try:
        youtube = build("youtube", "v3", developerKey=key)
        req = youtube.channels().list(part="snippet", id="UC_x5XG1OV2P6uZZ5FSM9Ttw") # Google Developers
        res = req.execute()
        print(f"✅ Working: {key}")
    except Exception as e:
        print(f"❌ Bad: {key} - {e}")
