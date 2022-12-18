import dataclasses
from quart import Quart, g, request, jsonify, abort
from quart_schema import validate_request, RequestSchemaValidationError, QuartSchema
import redis
import os
import socket
import httpx
import asyncio

app = Quart(__name__)
QuartSchema(app)

@app.errorhandler(401)
def unauthorized(e):
    return {"error": str(e).split(':', 1)[1][1:]}, 401, {"WWW-Authenticate": "Basic realm"}

@app.errorhandler(404)
def unauthorized(e):
    return {"error": str(e).split(':', 1)[1][1:]}, 404

#------------SUBSCRIBE SCORE URL-----------------#
async def subscribeToGame():
    print("subscribing to game service. This may take several seconds...")

    task = asyncio.create_task(sendRequest())
    await task

async def sendRequest():
    url = "http://127.0.0.1:" + os.environ["PORT"] + "/scores"
    gameUrl = "http://" + socket.getfqdn() + "/score-url"

    while True:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(gameUrl, json = {"url": url})

                if res.status_code != 200 and res.status_code != 201:
                    raise Exception()
                else:
                    print("successfully subscribed to game service...")
                    break

        except Exception as e:
            await asyncio.sleep(1.5)

asyncio.run(subscribeToGame())

# @app.route("/testscore", methods=["GET"])
# async def testscore():

#     return {"what": 1}

#------------POSTING NEW SCORE-----------------#

@app.route("/scores", methods=["POST"])
async def add_score():
    r = redis.Redis(
    host='127.0.0.1',
    port=6379,
    password='')
    # GLOABAL VARIABLES
    table = 'leaderboard'

    data = await request.get_json()

    if data is None or data["guessesRemaining"] is None or data["username"] is None or data["won"] is None:
        return {"Error": "Please provide guessesRemaining, username, and won"}, 400

    guessesRemaing = int(data["guessesRemaining"])

    # guesses represents guesses remaining
    if (guessesRemaing < 0 or guessesRemaing > 6):
        return {"Error": "Invalid Score"}, 400

    scoreRange = [6,5,4,3,2,1,0]

    score = 0 if data["won"] == False else scoreRange[5 - guessesRemaing]

    if (r.exists(data["username"]) == 1):
        r.zincrby(table, score, data["username"])
        r.incrby(data["username"], 1)
    else:
        dict = {}
        dict[data["username"]] = score
        r.set(data["username"], 1)
        r.zadd(table,dict)

    return {"data": {"username": data["username"], "score": score}}, 201


#------------RETRIEVE TOP 10 SCORES-----------------#

@app.route("/scores/top-10", methods=["GET"])
async def get_scores():
    r = redis.Redis(
    host='127.0.0.1',
    port=6379,
    password='')
    # GLOABAL VARIABLES
    table = 'leaderboard'

    output = []
    top10data = r.zrevrange(table, 0, -1, withscores=True)

    for i in range(len(top10data)):
        name = top10data[i][0].decode()
        num_of_games = r.get(name).decode()
        finalScore = top10data[i][1]/int(num_of_games)
        if (i < 10):
            r.get(name).decode()
            output.append({"place": str(i + 1), "username": name, "score": str(round(finalScore, 2))})
        else:
            break

    return {"Top10leaderboard": output}, 200
