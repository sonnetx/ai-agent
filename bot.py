import os
import discord
import logging
import asyncio
import datetime

from discord.ext import commands
from dotenv import load_dotenv
from agent import MistralAgent, NewsAgent

PREFIX = "!"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord")

# Load the environment variables
load_dotenv()

# Create the bot with all intents
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Import the Mistral agent from the agent.py file
news_agent = NewsAgent()
debate_agent = MistralAgent()

# Get the token from the environment variables
token = os.getenv("DISCORD_TOKEN")
print(f"Token loaded: {'Yes' if token else 'No'}")
print(f"Token length: {len(token) if token else 0}")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "123456789012345678"))

# Track active debates
active_debates = {}

# Add this class near the top of your bot.py file, after the imports
class FakeMessage:
    """A simple class to simulate a Discord message for the agent."""
    def __init__(self, content, author=None):
        self.content = content
        self.author = author

@bot.event
async def on_ready():
    """
    Called when the client is done preparing the data received from Discord.
    Prints message on terminal when bot successfully connects to discord.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_ready
    """
    logger.info(f"{bot.user} has connected to Discord!")
    
    # starts the conversation by greeting the user
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"Hello, I'm EchoBreaker! I'm here to help you learn about the world of politics through debate. Would you like to get started? Type `!debate` to begin.")

@bot.event
async def on_message(message: discord.Message):
    """
    Called when a message is sent in any channel the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message
    """
    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith("!"):
        return

    # Check if user is in an active debate
    if message.author.id in active_debates:
        logger.info(f"Processing debate message from {message.author}: {message.content}")
        
        # sends the user's message to the agent
        response = await debate_agent.run(message)
        
        # Split long responses into multiple messages
        if len(response) <= 2000:
            await message.reply(response)
        else:
            # Split the response into chunks of 1900 characters (leaving room for "Part X/Y: " prefix)
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            for i, chunk in enumerate(chunks):
                await message.channel.send(f"**Part {i+1}/{len(chunks)}**: {chunk}")

# Commands
@bot.command(name="debate", help="Start a political debate with the bot. Optionally specify a topic.")
async def debate(ctx, *, topic=None):
    """Start a debate session with the bot using a current news article."""
    user_id = ctx.author.id
    
    # Check if user is already in a debate
    if user_id in active_debates:
        await ctx.send("You're already in an active debate! Type `!enddebate` to end it first.")
        return
    
    if topic:
        await ctx.send(f"Let's start a debate about {topic}! I'll find a relevant news article for us to discuss...")
        # Get an article related to the specified topic
        top_article = news_agent.get_article_by_topic(topic)
    else:
        await ctx.send("Let's start a debate! I'll find a current news article for us to discuss...")
        # Pull a random top article from the news API
        top_article = news_agent.get_top_article()

    title = top_article["title"]
    author = top_article["author"] if top_article["author"] else "Unknown author"
    description = top_article["description"] if top_article["description"] else "No description available"
    url = top_article["url"]
    
    # Display the article to the user
    article_embed = discord.Embed(
        title=title,
        description=description,
        url=url,
        color=discord.Color.blue()
    )
    article_embed.set_author(name=author)
    article_embed.set_footer(text="Source: NewsAPI")
    
    await ctx.send("Here's a news article on this topic:", embed=article_embed)
    
    # Set up the debate agent with context about the article
    setup_message = FakeMessage(
        content=f"Take a strong political position on this news article: {title}. {description}",
        author=ctx.author
    )
    
    # Get the AI's opening position
    opening_position = await debate_agent.run(setup_message)
    
    # Truncate if too long
    if len(opening_position) > 1500:
        opening_position = opening_position[:1497] + "..."
    
    # Send the debate prompt
    await ctx.send(f"**Let's begin our debate!**\n\n{opening_position}\n\nWhat's your position on this? I'll defend my viewpoint, and you try to convince me otherwise. (You're now in an active debate - all your messages will be part of the debate until you type `!enddebate`)")
    
    # Mark user as in an active debate
    active_debates[user_id] = {
        "article": top_article,
        "start_time": datetime.datetime.now()
    }

@bot.command(name="enddebate", help="End your current debate session.")
async def enddebate(ctx):
    """End the current debate session."""
    user_id = ctx.author.id
    
    if user_id in active_debates:
        del active_debates[user_id]
        await ctx.send("Debate ended. Thanks for the discussion! Type `!debate` to start a new one.")
    else:
        await ctx.send("You don't have an active debate session.")

@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Pong!")
    else:
        await ctx.send(f"Pong! Your argument was {arg}")

# Start the bot, connecting it to the gateway
bot.run(token)
