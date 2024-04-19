# run_bot.py
#
# Copyright (c) 2023 - 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from typing import Any

import os

import httpx
from interactions import (
    Client,
    Intents,
    OptionType,
    SlashContext,
    listen,
    slash_command,
    slash_option,
)
from loguru import logger


class ImproperlyConfigured(Exception):
    """
    Raised when required tokens are missing from the environment.
    """

    pass


discord_token: str | None = os.environ.get("BOT_TOKEN", default=None)
qs_token: str | None = os.environ.get("QS_TOKEN", default=None)
maintenance_mode: str | None = os.environ.get("MAINTENANCE_MODE", default=None)

maintenance_msg = "This bot is currently in maintenance mode while our crack team of invisible monkeys hammer on the server. Thank you for your patience."

if discord_token is None or qs_token is None:
    raise ImproperlyConfigured(
        "You must define 'BOT_TOKEN' and 'QS_TOKEN' in your environment!"
    )

qs_headers: dict[str, str] = {"Authorization": f"Token {qs_token}"}

bot = Client(intents=Intents.DEFAULT)


def in_maintenance_mode() -> bool:
    """
    Checks to see if the is in maintenance mode with the environment variable and return
    the determination.
    """
    if maintenance_mode is not None and maintenance_mode not in (
        "",
        "False",
        "0",
        "false",
        "no",
    ):
        return True
    return False


def form_citation_text(quote: dict[str, Any]) -> str:
    """
    Given the data from a quote serializer, form the text to be used for attribution.

    Args:
        quote: The dict representation of the quote from the remote server.
    Returns:
        The formatted citation text to include in the discord response.
    """
    logger.debug(f"Attempting to form citation text for quote object: {quote}")
    name = f"--- {quote['source']['name']}"
    cite_str = ""
    if quote["citation"] is not None or quote["citation_url"] is not None:
        if quote["citation_url"]:
            if quote["citation"] is not None:
                cite_str = f"[{quote['citation']}]({quote['citation_url']})"
            else:
                cite_str = f"[{quote['citation_url']}]({quote['citation_url']})"
        else:
            cite_str = quote["citation"]
    if cite_str != "":
        return f"{name}, {cite_str}"
    return name


@slash_command(name="listew", description="List available characters to query.")
async def list_ew_characters(ctx: SlashContext) -> None:
    """
    Gets the list of characters from the server and sends the message to discord.

    Args:
        ctx: The command context
    """
    if in_maintenance_mode():
        await ctx.send(maintenance_msg, ephemeral=True)
        return
    logger.info("Received a request for the list of available characters.")
    response = httpx.get(
        "https://quoteservice.andrlik.org/api/sources/?group=ew&format=json",
        headers=qs_headers,
    )
    if response.status_code == 200:
        characters = response.json()
        message_text = """The following characters were found:"""
        for character in characters:
            message_text += f"""
            {character['name']}: {character['slug'][3:]}"""  # Strip the obvious ew tag off.
        await ctx.send(message_text)
    else:
        await ctx.send(
            "Terribly sorry. An error has occurred requesting data from the server. Please try again later."
        )


@slash_command(
    name="random_quote",
    description="Get a random quote",
)
@slash_option(
    name="character",
    description="Optional: The specific character you want a quote from.",
    required=False,
    opt_type=OptionType.STRING,
)
async def random_quote(ctx: SlashContext, character: str | None = None) -> None:
    """
    Gets a random quote from the remote server and sends it to discord.

    Args:
        ctx: The command context.
        character: Optionally provided to restrict results to a specific character.
    """
    if in_maintenance_mode():
        await ctx.send(maintenance_msg, ephemeral=True)
        return
    if character is not None:
        # Attempt to retrieve the character listed.
        logger.info(f"Received a request to fetch a quote for character {character}")
        r = httpx.get(
            f"https://quoteservice.andrlik.org/api/sources/ew-{character.lower()}/get_random_quote/",
            headers=qs_headers,
        )
        if r.status_code == 404:
            await ctx.send(
                f"{character} not found! Did you spell it correctly? You can use /list_characters to see valid options."
            )
        else:
            quote = r.json()
            cite_str = form_citation_text(quote)
            await ctx.send(f"> {quote['quote']}\n> {cite_str}")
    else:
        logger.info("Received a request to get a random quote.")
        r = httpx.get(
            "https://quoteservice.andrlik.org/api/groups/ew/get_random_quote/",
            headers=qs_headers,
        )
        if r.status_code == 200:
            quote = r.json()
            cite_str = form_citation_text(quote)
            await ctx.send(f"> {quote['quote']}\n> {cite_str}")
        else:
            await ctx.send(f"The following error occurred: {r.json()['error']}")


@slash_command(
    name="generate_sentence",
    description="Bot generated sentence based on existing quotes.",
)
@slash_option(
    name="character",
    description="Optional: base this on a specified character.",
    required=False,
    opt_type=OptionType.STRING,
)
async def generate_sentence(ctx: SlashContext, character: str | None = None) -> None:
    """
    Generate a sentence using a Markov chain and send it to discord.
    Args:
        ctx: The command context.
        character: Optionally the character to base the sentence upon.
    """
    if in_maintenance_mode():
        await ctx.send(maintenance_msg, ephemeral=True)
        return
    if character is not None:
        logger.info(f"Received a request to generate a sentence based on {character}")
        r = httpx.get(
            f"https://quoteservice.andrlik.org/api/sources/ew-{character.lower()}/generate_sentence/",
            headers=qs_headers,
        )
        if r.status_code == 200:
            sentence = r.json()["sentence"]
            await ctx.send(f"> {sentence}\n> ---{character}Bot")
        else:
            logger.error(r.json()["error"])
            await ctx.send(f"Error: {r.json()['error']}")
    else:
        logger.info("Received a request to generate a sentence.")
        r = httpx.get(
            "https://quoteservice.andrlik.org/api/groups/ew/generate_sentence/",
            headers=qs_headers,
        )
        results = r.json()
        if r.status_code == 200:
            await ctx.send(f"> {results['sentence']}\n ---EWBot")
        else:
            logger.error(results["error"])
            await ctx.send(f"Error: {results['error']}")


@listen()
async def on_ready():
    """
    Tells us when the bot is ready to receive commands.
    """
    logger.info("Ready to receive commands.")


@listen()
async def on_startup():
    """
    Gives us the commands that are registered for this.
    """
    logger.info(
        f"Launching bot with the following commands: {bot.application_commands}"
    )


if __name__ == "__main__":
    if discord_token is not None and qs_token is not None:
        bot.start(discord_token)
    else:
        raise ImproperlyConfigured
