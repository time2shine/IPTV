from googleapiclient.discovery import build

keys = [
    "AIzaSyBX_LlRNOxBzT5eAWzRiCWNjFS000uqsBQ",  # allmybooks
    "AIzaSyCgJaZsz-tsyAaIJRLc5NRYQyC-vnTCwAI",  # rokonmagura
    "AIzaSyA7ySJB3-FKUUWFpcT6PpCcF578936a8jQ",  # deshirambo11
    "AIzaSyA_58ry30FZ2qUQFNiJXJgNXJfCYj-0-9k",  # deshirambo12
    "AIzaSyDYyv5PWLhOCRxAwMkiaH9VY_BXwMi3VzM",  # deshirambo13
    "AIzaSyDJ5CkvzxGaJL99SdGqENypUVcm0nFaKEQ",  # deshirambo14
    "AIzaSyDO8JaYU6HbD8PdypJhG-EkFi4nojq0hrE",  # deshirambo15
    "AIzaSyCxklIr0fXmsjmiwzoDfBBT0DxtMpWQS68"  # deshirambo16
]

for key in keys:
    try:
        youtube = build("youtube", "v3", developerKey=key)
        req = youtube.channels().list(part="snippet", id="UC_x5XG1OV2P6uZZ5FSM9Ttw") # Google Developers
        res = req.execute()
        print(f"✅ Working: {key}")
    except Exception as e:
        print(f"❌ Bad: {key} - {e}")
