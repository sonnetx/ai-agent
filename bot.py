import os
import discord
import logging
import asyncio
import datetime
import json
import random

from discord.ext import commands
from dotenv import load_dotenv
from agent import MistralAgent, NewsAgent, DebateStatsTracker

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
stats_tracker = DebateStatsTracker()

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
        welcome_embed = discord.Embed(
            title="EchoBreaker Debate Bot",
            description="I'm here to help you sharpen your debate skills by challenging you with strong political viewpoints.",
            color=discord.Color.blue()
        )
        welcome_embed.add_field(
            name="How to start",
            value="Type `!debate [topic]` to begin a debate\nExample: `!debate climate change` or just `!debate` for a random topic",
            inline=False
        )
        welcome_embed.add_field(
            name="Difficulty levels",
            value="`!debate easy [topic]` - For beginners (0.8x points)\n"
                 "`!debate normal [topic]` - Standard difficulty (1.0x points)\n"
                 "`!debate hard [topic]` - For experienced debaters (1.2x points)",
            inline=False
        )
        welcome_embed.add_field(
            name="Commands",
            value="`!stats` - View your debate statistics\n"
                 "`!leaderboard` - See top debaters\n"
                 "`!enddebate` - End current debate session",
            inline=False
        )
        welcome_embed.add_field(
            name="Earning Points",
            value="• Longer debates earn more points (up to 30 base points)\n"
                 "• Longer, thoughtful responses get bonus points\n"
                 "• Complete debates daily to build your streak\n"
                 "• Earn achievements to showcase your skills",
            inline=False
        )
        
        await channel.send("Hello, I'm EchoBreaker! Ready to debate?", embed=welcome_embed)

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
        
        # Update message count and award points for each message
        debate_info = active_debates[message.author.id]
        debate_info["messages_count"] += 1
        
        # Track total characters for averaging later
        message_length = len(message.content)
        if "total_chars" not in debate_info:
            debate_info["total_chars"] = 0
        debate_info["total_chars"] += message_length
        
        # Award points based on message quality (length)
        if message_length > 300:
            quality_points = 3
        elif message_length > 150:
            quality_points = 2
        elif message_length > 50:
            quality_points = 1
        else:
            quality_points = 0
            
        debate_info["points_accumulated"] += quality_points
        
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
@bot.command(name="debate", help="Start a political debate with the bot. Optionally specify a topic and difficulty.")
async def debate(ctx, difficulty="normal", *, topic=None):
    """Start a debate session with the bot using a current news article."""
    user_id = ctx.author.id
    
    # Extract difficulty and topic if both are provided
    if difficulty not in ["easy", "normal", "hard"] and topic is None:
        topic = difficulty
        difficulty = "normal"
    
    # Check if user is already in a debate
    if user_id in active_debates:
        await ctx.send("You're already in an active debate! Type `!enddebate` to end it first.")
        return
    
    # Inform user about difficulty level
    difficulty_factor = {"easy": 0.8, "normal": 1.0, "hard": 1.2}
    difficulty_desc = {
        "easy": "I'll take it easy on you and be more willing to concede points.",
        "normal": "I'll present a balanced debate with moderate intensity.",
        "hard": "I'll aggressively defend my position and challenge your arguments thoroughly."
    }
    
    # Display difficulty selection
    await ctx.send(f"**Difficulty: {difficulty.upper()}**\n{difficulty_desc[difficulty]}\n" +
                   f"Point multiplier: {difficulty_factor[difficulty]}x")
    
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
        content=f"Take a strong political position on this news article: {title}. {description} " +
                f"Difficulty level: {difficulty}",
        author=ctx.author
    )
    
    # Get the AI's opening position
    opening_position = await debate_agent.run(setup_message)
    
    # Truncate if too long
    if len(opening_position) > 1500:
        opening_position = opening_position[:1497] + "..."
    
    # Send the debate prompt with gamification info
    await ctx.send(f"**Let's begin our debate!**\n\n{opening_position}\n\n" +
                   f"What's your position on this? I'll defend my viewpoint, and you try to convince me otherwise.\n" +
                   f"(You're now in an active debate - all your messages will be part of the debate until you type `!enddebate`)\n\n" +
                   f"**Debate Tips:**\n" +
                   f"• Longer, thoughtful responses earn more points\n" +
                   f"• Present evidence to support your arguments\n" +
                   f"• Address my key points directly")
    
    # Mark user as in an active debate
    active_debates[user_id] = {
        "article": top_article,
        "start_time": datetime.datetime.now(),
        "difficulty": difficulty,
        "points_accumulated": 0,
        "messages_count": 0
    }

@bot.command(name="enddebate", help="End your current debate session.")
async def enddebate(ctx):
    """End the current debate session and award points."""
    user_id = ctx.author.id
    
    if user_id in active_debates:
        debate_info = active_debates[user_id]
        
        # Calculate debate duration and points
        start_time = debate_info["start_time"]
        duration = (datetime.datetime.now() - start_time).total_seconds()
        
        # Get difficulty multiplier
        difficulty = debate_info["difficulty"]
        difficulty_factor = {"easy": 0.8, "normal": 1.0, "hard": 1.2}
        
        # Award points and update stats
        result = stats_tracker.complete_debate(user_id, int(duration))
        points_earned = result["points_earned"]
        adjusted_points = int(points_earned * difficulty_factor[difficulty])
        
        # Add bonus points based on message count
        message_count = debate_info["messages_count"]
        message_bonus = min(10, message_count)  # Cap at 10 bonus points
        total_points = adjusted_points + message_bonus
        
        # Update final stats
        stats = stats_tracker.add_points(user_id, total_points)
        
        # Create an embed for the debate summary
        embed = discord.Embed(
            title="Debate Completed!",
            description=f"You've earned {total_points} points from this debate.",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="Base Points", value=f"{points_earned} pts", inline=True)
        embed.add_field(name="Difficulty Bonus", value=f"{difficulty.capitalize()} ({difficulty_factor[difficulty]}x)", inline=True)
        embed.add_field(name="Message Bonus", value=f"+{message_bonus} pts", inline=True)
        embed.add_field(name="Debate Duration", value=f"{int(duration // 60)} minutes", inline=True)
        embed.add_field(name="Messages Sent", value=str(message_count), inline=True)
        
        # Check for level ups
        old_level = (stats["points"] - total_points) // 100 + 1
        new_level = stats["level"]
        if new_level > old_level:
            embed.add_field(name="LEVEL UP!", value=f"You are now level {new_level}!", inline=False)
        
        # Check for new achievements
        new_achievements = stats_tracker._check_achievements(user_id, stats)
        if new_achievements:
            embed.add_field(name="New Achievements!", value="\n".join([f"• {ach}" for ach in new_achievements]), inline=False)
        
        await ctx.send(embed=embed)
        
        # Show overall stats
        stats_embed = create_stats_embed(ctx.author, stats)
        await ctx.send("Your updated stats:", embed=stats_embed)
        
        # Generate and show debate feedback
        feedback = generate_debate_feedback(debate_info)
        
        feedback_embed = discord.Embed(
            title="Debate Feedback",
            description="Here's some feedback to help improve your debating skills:",
            color=discord.Color.purple()
        )
        
        for i, tip in enumerate(feedback):
            feedback_embed.add_field(name=f"Tip {i+1}", value=tip, inline=False)
            
        await ctx.send(embed=feedback_embed)
        
        del active_debates[user_id]
    else:
        await ctx.send("You don't have an active debate session.")

@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Pong!")
    else:
        await ctx.send(f"Pong! Your argument was {arg}")

@bot.command(name="stats", help="View your debate statistics.")
async def show_stats(ctx, member: discord.Member = None):
    """Show debate statistics for yourself or another user."""
    target = member or ctx.author
    stats = stats_tracker.get_user_stats(target.id)
    
    embed = create_stats_embed(target, stats)
    await ctx.send(embed=embed)

@bot.command(name="leaderboard", aliases=["lb"], help="View the debate points leaderboard.")
async def leaderboard(ctx):
    """Show the top 10 users by debate points."""
    top_users = stats_tracker.get_leaderboard(10)
    
    embed = discord.Embed(
        title="Debate Leaderboard",
        description="Top debaters ranked by points",
        color=discord.Color.gold()
    )
    
    for i, (user_id, user_stats) in enumerate(top_users, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            username = user.name
        except:
            username = f"User {user_id}"
        
        embed.add_field(
            name=f"{i}. {username}",
            value=f"Level {user_stats['level']} • {user_stats['points']} pts • {user_stats['debates_completed']} debates",
            inline=False
        )
    
    await ctx.send(embed=embed)

# Add this helper function after the FakeMessage class
def create_stats_embed(user, stats):
    """Creates an embed to display a user's debate stats."""
    embed = discord.Embed(
        title=f"{user.name}'s Debate Stats",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    
    # Calculate XP to next level
    xp_to_next = (stats["level"] * 100) - stats["points"]
    
    embed.add_field(name="Level", value=f"{stats['level']} ({stats['points']} points)", inline=True)
    embed.add_field(name="Next Level", value=f"{xp_to_next} points needed", inline=True)
    embed.add_field(name="Debates Completed", value=str(stats["debates_completed"]), inline=True)
    embed.add_field(name="Current Streak", value=f"{stats['streak']} days", inline=True)
    embed.add_field(name="Longest Streak", value=f"{stats['longest_streak']} days", inline=True)
    
    # Add achievements if any
    if stats["achievements"]:
        achievements_list = "\n".join([
            "• First Debate" if "first_debate" in stats["achievements"] else "",
            "• Debate Master" if "debate_master" in stats["achievements"] else "",
            "• Point Collector" if "point_collector" in stats["achievements"] else "",
            "• 3-Day Streak" if "streak_3" in stats["achievements"] else "",
            "• Skilled Debater" if "high_level" in stats["achievements"] else ""
        ])
        embed.add_field(name="Achievements", value=achievements_list, inline=False)
    
    return embed

# Add this new function near the stats embed function
def generate_debate_feedback(debate_info):
    """Generates constructive feedback for the user based on their debate performance."""
    message_count = debate_info["messages_count"]
    avg_message_length = debate_info.get("total_chars", 0) / max(message_count, 1)
    duration_minutes = (datetime.datetime.now() - debate_info["start_time"]).total_seconds() / 60
    
    # Generate appropriate feedback based on metrics
    feedback = []
    
    # Engagement feedback
    if message_count < 3:
        feedback.append("Try to engage more deeply in the debate. Aim for at least 3-4 exchanges to develop your arguments fully.")
    elif message_count > 8:
        feedback.append("Great engagement level! You maintained a sustained conversation.")
    
    # Message length feedback
    if avg_message_length < 100:
        feedback.append("Your responses were quite brief. Try to elaborate more on your arguments with examples and evidence.")
    elif avg_message_length > 300:
        feedback.append("You provided detailed responses, which is excellent for presenting thorough arguments.")
    
    # Debate duration feedback
    if duration_minutes < 5:
        feedback.append("Consider spending more time developing your arguments. Longer debates allow for deeper exploration of topics.")
    elif duration_minutes > 15:
        feedback.append("You demonstrated strong commitment by sustaining a lengthy debate. This shows dedication to the topic.")
    
    # Add random debate tips
    debate_tips = [
        "When countering an argument, first acknowledge it before presenting your rebuttal.",
        "Using specific examples strengthens your arguments more than general statements.",
        "Try the 'steel man' technique: present your opponent's argument in its strongest form before countering it.",
        "Focus on addressing the strongest points in your opponent's argument, not just the weakest ones.",
        "Maintaining a respectful tone makes your arguments more persuasive than aggressive language.",
        "Cite specific sources when possible to add credibility to your claims.",
        "Use questions strategically to expose flaws in your opponent's reasoning.",
        "Connect abstract principles to concrete impacts to make your arguments more relatable.",
        "Consider the practical implications of your position to strengthen its real-world relevance.",
        "Structure your arguments clearly with a main claim followed by supporting evidence."
    ]
    
    # Add 2 random tips
    feedback.extend(random.sample(debate_tips, 2))
    
    return feedback

# Start the bot, connecting it to the gateway
bot.run(token)
