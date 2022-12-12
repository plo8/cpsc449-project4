import dataclasses
import collections
from operator import itemgetter
import databases
from quart import Quart, g, request, jsonify, abort
from quart_schema import validate_request, RequestSchemaValidationError, QuartSchema
import redis


app = Quart(__name__)
QuartSchema(app)

@dataclasses.dataclass
class scoreData:
    username: str
    guesses: int
    win: bool


@app.errorhandler(401)
def unauthorized(e):
    return {"error": str(e).split(':', 1)[1][1:]}, 401, {"WWW-Authenticate": "Basic realm"}

@app.errorhandler(404)
def unauthorized(e):
    return {"error": str(e).split(':', 1)[1][1:]}, 404

#------------POSTING NEW SCORE-----------------#

@app.route("/add-score", methods=["POST"])
@validate_request(scoreData)
async def add_score(data):
    r = redis.Redis(
    host='127.0.0.1',
    port=6379,
    password='')
    # GLOABAL VARIABLES
    table = 'leaderboard'

    if (int(data.guesses) < 0 or int(data.guesses) > 6):
        return {"Error": "Invalid Score"}, 401

    scoreRange = [6,5,4,3,2,1,0]

    if (r.exists(data.username) == 1):
        if data.win == False:
            score = 0
        else:
            score = scoreRange[5 - data.guesses]
        r.zincrby(table, score, data.username)
        r.incrby(data.username, 1)
        print(r.get(data.username))
    else:
        if data.win == False:
            score = 0
        else:
            score = scoreRange[5 - data.guesses]
        dict = {}
        dict[data.username] = score
        r.set(data.username, 1)
        r.zadd(table,dict)
        print(r.get(data.username))

    return {"Success": "Added Score"}, 200


#------------RETRIEVE TOP 10 SCORES-----------------#

@app.route("/get-scores", methods=["GET"])
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
            break;


    return {"Top10leaderboard": output}, 200
