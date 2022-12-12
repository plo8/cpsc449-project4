from operator import itemgetter
import databases
from quart import Quart, g, request, jsonify, abort
from quart_schema import validate_request, RequestSchemaValidationError, QuartSchema
import sqlite3
import toml
import random
import uuid
from itertools import cycle

app = Quart(__name__)
QuartSchema(app)
app.config.from_file(f"./etc/{__name__}.toml", toml.load)

dbs = None

# async def _get_db():
#     db = getattr(g, "_sqlite_db", None)
#     if db is None:
#         db = g._sqlite_db = databases.Database(app.config["DATABASES"]["URL"])
#         # db = g._sqlite_db = databases.Database('sqlite+aiosqlite:/wordle.db')
#         await db.connect()
#     return db

# @app.teardown_appcontext
# async def close_connection(exception):
#     db = getattr(g, "_sqlite_db", None)
#     if db is not None:
#         await db.disconnect()

async def _get_db(primary = False):
    global dbs

    db_list = []

    primary_db = getattr(g, "_sqlite_db", None)
    if primary_db is None:
        primary_db = g._sqlite_db = databases.Database(app.config["DATABASES"]["PRIMARY_URL"])
        await primary_db.connect()
        db_list.append(primary_db)

    if primary:
        return primary_db

    replica_db1 = getattr(g, "_sqlite_db", None)
    if replica_db1 is None:
        replica_db1 = g._sqlite_db = databases.Database(app.config["DATABASES"]["REPLICA_URL1"])
        await replica_db1.connect()
        db_list.append(replica_db1)

    replica_db2 = getattr(g, "_sqlite_db", None)
    if replica_db2 is None:
        replica_db2 = g._sqlite_db = databases.Database(app.config["DATABASES"]["REPLICA_URL2"])
        await replica_db2.connect()
        db_list.append(replica_db1)

    if dbs is None:
        dbs = cycle(db_list)

    return next(dbs)

@app.teardown_appcontext
async def close_connection(exception):
    primary_db = getattr(g, "_sqlite_db", None)
    if primary_db is not None:
        await primary_db.disconnect()

    replica_db1 = getattr(g, "_sqlite_db", None)
    if replica_db1 is not None:
        await replica_db1.disconnect()

    replica_db2 = getattr(g, "_sqlite_db", None)
    if replica_db2 is not None:
        await replica_db2.disconnect()

@app.errorhandler(400)
def badRequest(e):
    return {"error": str(e).split(':', 1)[1][1:]}, 400

@app.errorhandler(401)
def unauthorized(e):
    return {"error": str(e).split(':', 1)[1][1:]}, 401, {"WWW-Authenticate": "Basic realm"}

@app.errorhandler(404)
def noGameFound(e):
    return {"error": str(e).split(':', 1)[1][1:]}, 404

# @app.route("/test", methods=["GET"])
# async def what():

#     return {"what": 1}

    
# ---------------GAME API---------------

# ---------------HELPERS----------------

def getGuessState(guess, secret):
    word = guess
    secretWord = secret

    matched = []
    valid = []

    for i in range(len(secretWord)):
        correct = word[i] == secretWord[i]
        valid.append({"inSecret": correct, "wrongSpot": False, "used": True if correct else False})
        matched.append(correct)

    for i in range(len(secretWord)):
        currentLetter = secretWord[i]
        for j in range(len(secretWord)):
            if i != j:
                if not(matched[i]) and not(valid[j].get("used")):
                    if word[j] == currentLetter:
                        valid[j].update({"inSecret": True, "wrongSpot": True, "used": True})
                        matched[i] = True

    data = []
    index = 0

    for i in word:
        d = {}
        del valid[index]["used"]
        d[i] = valid[index]
        data.append(d)
        index += 1

    return data

async def gameStateToDict(game):
    db = await _get_db()
    secretWord = await db.fetch_one("SELECT word FROM correct WHERE id=:id", values={"id": game[2]})
    secretWord = secretWord[0]

    state = {"guessesLeft": game[3], "finished": True if game[4] == 1 else False, "gussedWords": []}

    timeGuessed = 6 - game[3]
    guessedWords = []

    for i in range(timeGuessed):
        word = game[i + 5]
        wordState = {word: getGuessState(word, secretWord)}
        guessedWords.append(wordState)

    state["gussedWords"] = guessedWords

    return state

async def updateGameState(game, word, db, finished = 0):
    numGuesses = game[3]
    nthGuess = 6 - numGuesses + 1

    sql = "UPDATE game SET guesses=:numGuess, finished=:finished, "
    suffix = "guess" + str(nthGuess) + "=:guess, won=:won" + " WHERE id=:id"

    # finished = 1 only when game is won
    won = finished
    gameFinished = finished
    
    if numGuesses - 1 == 0:
        gameFinished = 1
    
    await db.execute(sql + suffix, values={"numGuess": numGuesses - 1, "id": game[0], "finished": gameFinished, "guess": word, "won": won })

# ---------------CREATE NEW GAME---------------

@app.route("/game", methods=["POST"])
async def newGame():
    db = await _get_db()

    auth = request.authorization

    if not(auth) or not(auth.username):
        abort(401, "Please provide the username")

    username = auth.username

    words = await db.fetch_all("SELECT * FROM correct")
    num = random.randrange(0, len(words), 1)

    gameId = str(uuid.uuid4())
    data = {"gameId": gameId, "wordId": words[num][0], "username": username}

    primary_db = await _get_db(True)

    await primary_db.execute(
        """
        INSERT INTO game(id, wordId, username)
        VALUES(:gameId, :wordId, :username)
        """,
        data)

    res = {"gameId": gameId, "guesses": 6}
    return res, 201

# ---------------GUESS A WORD---------------

@app.route("/game/<string:gameId>", methods=["PATCH"])
async def guess(gameId):
    db = await _get_db()

    auth = request.authorization

    if not(auth) or not(auth.username):
        abort(401, "Please provide the username")

    username = auth.username

    body = await request.get_json()
    word = body.get("word").lower()

    if not(word):
        abort(400, "Please provide the guess word")

    game = await db.fetch_one("SELECT * FROM game WHERE id=:id", values={"id": gameId})

    # Check if game exists
    if not(game):
        abort(404, "Could not find a game with this id")

    if username != game[1]:
        abort(400, "This game does not belong to this user")

    # Check if game is finished
    if game[4] == 1:
        abort(400, "This game has already ended")

    # Check if word is valid
    if len(word) != 5:
        abort(400, "This is not a valid guess")

    wordIsValid = False

    # check if word is in correct table
    correct = await db.fetch_one("SELECT word FROM correct WHERE word=:word", values={"word": word})

    if not(correct):
        valid = await db.fetch_one("SELECT word FROM valid WHERE word=:word", values={"word": word})
        wordIsValid = valid is not None

    # invalid guess
    if not(wordIsValid) and not(correct):
        abort(400, "Guess word is invalid")

    # Not correct but valid
    secretWord = await db.fetch_one("SELECT word FROM correct WHERE id=:id", values={"id": game[2]})
    secretWord = secretWord[0]

    primary_db = await _get_db(True)

    # guessed correctly
    if word == secretWord:
        await updateGameState(game, word, primary_db, 1)

        return {"word": {"input": word, "valid": True, "correct": True}, 
        "numGuesses": game[3] - 1}

    # guessed incorrectly
    await updateGameState(game, word, primary_db, 0)

    data = getGuessState(word, secretWord)

    return {"word": {"input": word, "valid": True, "correct": False}, 
        "gussesLeft": game[3] - 1, 
        "data": data}

# ---------------LIST GAMES FOR A USER---------------

@app.route("/my-games", methods=["GET"])
async def myGames():
    db = await _get_db()

    auth = request.authorization

    if not(auth) or not(auth.username):
        abort(401, "Please provide the username")

    username = auth.username

    games = await db.fetch_all("SELECT * FROM game WHERE username=:username", values={"username": username})

    gamesList = list(map(dict, games))
    res = []

    for game in gamesList:
        res.append({"gameId": game.get("id"),
            "guessesLeft": game.get("guesses"), 
            "finished": True if game.get("finished") == 1 else False,
            "won": True if game.get("won") == 1 else False})

    return res

# @app.errorhandler(401)
# def unauthorized(e):
#     return {"error": str(e).split(':', 1)[1][1:]}, 401

# ---------------GET GAME STATE---------------

@app.route("/game/<string:gameId>", methods=["GET"])
async def getGame(gameId):
    db = await _get_db()

    game = await db.fetch_one("SELECT * FROM game WHERE id=:id", values={"id": gameId})

    if not(game):
        return {"message": "No game found with this id"}, 404
    
    return await gameStateToDict(game)

# game
# 0 = id
# 1 = userId
# 2 = wordId
# 3 = guesses
# 4 = finished
# 5 = guess1
# 6 = guess2
# 7 = guess3
# 8 = guess4
# 9 = guess5
# 10 = guess6
# 11 = won