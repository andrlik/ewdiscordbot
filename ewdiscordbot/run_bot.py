#
# run_bot.py
#
# Copyright (c) 2023 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
#

from __future__ import annotations

from typing import Any

import os

import httpx
from interactions import (
    Client,
    Intents,
    OptionType,
    SlashContext,
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

if discord_token is None or qs_token is None:
    raise ImproperlyConfigured(
        "You must define 'BOT_TOKEN' and 'QS_TOKEN' in your environment!"
    )

qs_headers: dict[str, str] = {"Authorization": f"Token {qs_token}"}

bot = Client(intents=Intents.DEFAULT)


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
    if character is not None:
        # Attempt to retrieve the character listed.
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
    if character is not None:
        r = httpx.get(
            f"https://quoteservice.andrlik.org/api/sources/ew-{character.lower()}/generate_sentence/",
            headers=qs_headers,
        )
        if r.status_code == 200:
            sentence = r.json()["sentence"]
            await ctx.send(f"> {sentence}\n> ---{character}Bot")
        else:
            await ctx.send(f"Error: {r.json()['error']}")
    else:
        r = httpx.get(
            "https://quoteservice.andrlik.org/api/groups/ew/generate_sentence/",
            headers=qs_headers,
        )
        results = r.json()
        if r.status_code == 200:
            await ctx.send(f"> {results['sentence']}\n ---EWBot")
        else:
            await ctx.send(f"Error: {results['error']}")


if __name__ == "__main__":
    if discord_token is not None and qs_token is not None:
        bot.start(discord_token)
    else:
        raise ImproperlyConfigured
