import json
import os
import re

from constants import fpl_team_names
from discord.ext.commands import Bot
from pymongo import MongoClient
from utils import create_logger, player_vs_team_table, to_fpl_team

dirname = os.path.dirname(os.path.realpath(__file__))
logger = create_logger()

db_client = MongoClient()
db = db_client.fpl

bot_prefix = ["!fpl "]
bot = Bot(command_prefix=bot_prefix)
RE_PLAYER_VS_TEAM = re.compile(r"([^\W\d]+(?:[\s-][^\W\d]+)*)\s+(?:vs.|vs)\s+([a-zA-Z ]+)(\d+)?")


@bot.command(name="pvt",
             description="Prints table with player's performance against a team.",
             brief="Player's performance against a team.",
             usage="different usage",
             help=f"{bot_prefix[0]}pvt <player> vs <team> [<max_items>]",
             aliases=["player_vs_team"])
async def player_vs_team(*, content: str):
    match = RE_PLAYER_VS_TEAM.search(content.lower())

    if not match:
        await bot.say("No match")
        return

    player_name = match.group(1).lower().strip()
    opponent_name = match.group(2).lower().replace(".", "").strip()
    number = match.group(3)

    fpl_team = to_fpl_team(opponent_name)
    if fpl_team not in fpl_team_names:
        await bot.say("Unknown opponent")
        return

    players = list(db.players.find(
        {"$text": {"$search": player_name}},
        {"score": {"$meta": "textScore"}}
    ).sort([("score", {"$meta": "textScore"})]))

    if not players:
        await bot.say("Unknown player name")
        return

    player = players[0]
    fixture_count = 0
    relevant_fixtures = []
    if not number or int(number) < 1:
        number = len(player["understat_history"])
    for fixture in player["understat_history"]:
        if fixture_count >= int(number):
            break

        if (opponent_name != fixture["h_team"].lower()
                and opponent_name != fixture["a_team"].lower()):
            continue

        fixture_count += 1
        relevant_fixtures.append(fixture)

    table = player_vs_team_table(relevant_fixtures, table_format="grid", highlight=False)
    await bot.say(f"{player_name} vs {opponent_name}\n```{table}```")


@bot.event
async def on_ready():
    print("Ready to work")


if __name__ == "__main__":
    config = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'config.json')))
    bot.run(config["DISCORD_BOT_TOKEN"])
