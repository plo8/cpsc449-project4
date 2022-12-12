auth: hypercorn auth --reload --debug --bind auth.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG
game_1: hypercorn game --reload --debug --bind game.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG
game_2: hypercorn game --reload --debug --bind game.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG
game_3: hypercorn game --reload --debug --bind game.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG
score: hypercorn score --reload --debug --bind score.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG
primary: ./bin/litefs -config ./etc/primary.yml
secondary1: ./bin/litefs -config ./etc/secondary1.yml
secondary2: ./bin/litefs -config ./etc/secondary2.yml
