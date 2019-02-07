import asyncio
import codecs
import json
import logging
import os
import re

import aiohttp
from bs4 import BeautifulSoup
from fpl import FPL
from fpl.utils import position_converter, team_converter
from pymongo import MongoClient, ReplaceOne

client = MongoClient()
database = client.fpl
logger = logging.getLogger("FPLbot")


def create_logger():
    """Creates a logger object for use in logging across all files.

    See: https://docs.python.org/3/howto/logging-cookbook.html
    """
    dirname = os.path.dirname(os.path.realpath(__file__))

    logger = logging.getLogger("FPLbot")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(f"{dirname}/FPLbot.log")
    fh.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - "
                                  "%(message)s")

    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()


async def understat_general_player_data():
    """Returns a dict containing general player data retrieved from
    https://understat.com/.
    """
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, "https://understat.com/league/EPL/")

    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script")
    pattern = re.compile(r"var\s+playersData\s+=\s+JSON.parse\(\'(.*?)\'\);")

    for script in scripts:
        match = re.search(pattern, script.string)
        if match:
            break

    byte_data = codecs.escape_decode(match.group(1))
    player_data = json.loads(byte_data[0].decode("utf-8"))

    return player_data


async def update_players():
    """Updates all players in the database."""
    async with aiohttp.ClientSession() as session:
        fpl = FPL(session)
        players = await fpl.get_players(include_summary=True, return_json=True)

    requests = [ReplaceOne({"id": player["id"]}, player, upsert=True)
                for player in players]

    logger.info("Updating players in database.")
    database.players.bulk_write(requests)


def get_player_table(players, risers=True):
    """Returns the table used in the player price change posts on Reddit."""
    table_header = ("|Name|Team|Position|Ownership|Price|∆|Form|\n"
                    "|:-|:-|:-|:-:|:-:|:-:|:-:|\n")

    table_body = "\n".join([
            f"|{player.web_name}|"
            f"{team_converter(player.team)}|"
            f"{position_converter(player.element_type)}|"
            f"{player.selected_by_percent}%|"
            f"£{player.now_cost / 10.0:.1f}|"
            f"{'+' if risers else '-'}£{abs(player.cost_change_event / 10.0):.1f}|"
            f"{sum([fixture['total_points'] for fixture in player.history[-5:]])}|"
            for player in players])

    return table_header + table_body


if __name__ == "__main__":
    try:
        asyncio.run(update_players())
    except AttributeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(update_players())
        loop.close()