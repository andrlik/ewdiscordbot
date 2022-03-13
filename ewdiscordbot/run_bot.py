import os
from typing import Any, Dict, Optional

import interactions
import requests
from loguru import logger

discord_token = os.environ.get("BOT_TOKEN", default=None)
qs_token = os.environ.get("QS_TOKEN", default=None)

qs_headers = {"Authorization": f"Token {qs_token}"}

if discord_token is not None and qs_token is not None:
    bot = interactions.Client(discord_token)


def form_citation_text(quote: Dict[str, Any]) -> str:
    """
    Given the data from a quote serializer, form the text to be used for attribution.

    :param quote: A dict representing a Quote object.
    :return: str
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


@bot.command(name="listew", description="List available characters to query.")
async def list_ew_characters(ctx: interactions.CommandContext):
    response = requests.get(
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


@bot.command(
    name="random_quote",
    description="Get a random quote",
    options=[
        interactions.Option(
            name="character",
            description="Optional: The name of the character you want the quote from, e.g. Nix.",
            type=interactions.OptionType.STRING,
            required=False,
        )
    ],
)
async def random_quote(
    ctx: interactions.CommandContext, character: Optional[str] = None
):
    if character is not None:
        # Attempt to retrieve the character listed.
        r = requests.get(
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
        r = requests.get(
            "https://quoteservice.andrlik.org/api/groups/ew/get_random_quote/",
            headers=qs_headers,
        )
        if r.status_code == 200:
            quote = r.json()
            cite_str = form_citation_text(quote)
            await ctx.send(f"> {quote['quote']}\n> {cite_str}")
        else:
            await ctx.send(f"The following error occurred: {quote['error']}")


@bot.command(
    name="generate_sentence",
    description="Bot generated sentence based on existing quotes.",
    options=[
        interactions.Option(
            name="character",
            description="Optional: base it on a single specified character",
            type=interactions.OptionType.STRING,
            required=False,
        )
    ],
)
async def generate_sentence(
    ctx: interactions.CommandContext, character: Optional[str] = None
) -> str:
    if character is not None:
        r = requests.get(
            f"https://quoteservice.andrlik.org/api/sources/ew-{character.lower()}/generate_sentence/",
            headers=qs_headers,
        )
        if r.status_code == 200:
            sentence = r.json()["sentence"]
            await ctx.send(f"> {sentence}\n> ---{character}Bot")
        else:
            await ctx.send(f"Error: {r.json()['error']}")
    else:
        r = requests.get(
            "https://quoteservice.andrlik.org/api/groups/ew/generate_sentence/",
            headers=qs_headers,
        )
        results = r.json()
        if r.status_code == 200:
            await ctx.send(f"> {results['sentence']}\n ---EWBot")
        else:
            await ctx.send(f"Error: {results['error']}")


class ImproperlyConfigured(Exception):
    pass


if __name__ == "__main__":
    if discord_token is not None and qs_token is not None:
        bot.start()
    else:
        raise ImproperlyConfigured
