import httpx

def postScore(data):
    urls = []

    for url in data["urls"]:
        urls.append(url["_url"])

    gameData = data["gameData"]

    print(urls)
    print(gameData)

    for url in urls:
        res = httpx.post(url, json={"username": gameData["username"], "guessesRemaining": gameData["guesses"], "won": gameData["win"]})
