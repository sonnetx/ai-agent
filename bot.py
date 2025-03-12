import os
import discord
import logging
import asyncio
import datetime
import json
import random
from collections import defaultdict
import re

from discord.ext import commands
from dotenv import load_dotenv
from agent import MistralAgent, NewsAgent, DebateStatsTracker, EmailManager

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
active_debates = {}  # Maps initiator_id -> debate_info
debate_participants = defaultdict(set)  # Maps debate_id -> set of participant user IDs
user_current_debate = {}  # Maps user_id -> debate_id they're participating in
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
            value="Type `!debate [topic]` to begin a debate\n• I'll find a current news article on your topic for us to discuss\n• Example: `!debate climate change` or just `!debate` for a random trending topic",
            inline=False
        )
        welcome_embed.add_field(
            name="Debate Levels",
            value="`!debate beginner [topic]` - Simpler language & gentler arguments (0.8x points)\n"
                 "`!debate intermediate [topic]` - Standard level (1.0x points)\n"
                 "`!debate advanced [topic]` - Complex language & aggressive arguments (1.2x points)\n"
                 "Type `!levels` for more details",
            inline=False
        )
        welcome_embed.add_field(
            name="Fact-Checking",
            value="• Your factual claims are automatically verified using Perplexity AI\n"
                  "• Accurate claims earn bonus points\n"
                  "• Look for the fact-check results after bot responses\n"
                  "• Type `!factcheck` to learn more about this feature",
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
        welcome_embed.add_field(
            name="Commands",
            value="`!stats` - View your debate statistics\n"
                 "`!leaderboard` - See top debaters\n"
                 "`!enddebate` - End current debate session\n"
                 "`!enddebate email` - End debate and receive summary by email\n"
                 "`!join @user` - Join another user's debate\n"
                 "`!leave` - Leave a debate you've joined",
            inline=False
        )
        welcome_embed.add_field(
            name="Email Features",
            value="• Get detailed debate summaries sent to your inbox\n"
                 "• Receive coach-like feedback and performance analysis\n"
                 "• Use `!email set youremail@example.com` to register\n"
                 "• Type `!emailhelp` for more information",
            inline=False
        )
        welcome_embed.add_field(
            name="Historical Figures",
            value="`!figures` - View available historical figures\n"
                  "`!figure [name]` - View details about a figure\n"
                  "`!customfigure [name]` - Create any historical figure\n"
                  "`!debate [figure] [level] [topic]` - Debate as a historical figure",
            inline=False
        )
        welcome_embed.add_field(
            name="Multi-User Debates",
            value="• Start a debate that others can join\n"
                  "• Join ongoing debates with `!join @username`\n"
                  "• See active debates with `!debates`\n"
                  "• Compete for highest scores in group debates",
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

    # First check if user is a direct initiator of a debate
    is_initiator = message.author.id in active_debates
    
    # Then check if user is a participant in any debate
    is_participant = message.author.id in user_current_debate
    
    # Process the message if user is in any debate
    if is_initiator or is_participant:
        logger.info(f"Processing debate message from {message.author}: {message.content}")
        
        # Get the appropriate debate info
        if is_initiator:
            debate_info = active_debates[message.author.id]
            participant_data = debate_info["participants"][str(message.author.id)]
        else:
            # Get initiator ID from the debate the user is participating in
            debate_id = user_current_debate[message.author.id]
            initiator_id = int(debate_id.split('-')[1])
            debate_info = active_debates[initiator_id]
            participant_data = debate_info["participants"][str(message.author.id)]
        
        # Update message count and award points for each message
        participant_data["messages_count"] += 1
        debate_info["messages_count"] = sum(p["messages_count"] for p in debate_info["participants"].values())
        
        # Track total characters for averaging later
        message_length = len(message.content)
        if "total_chars" not in participant_data:
            participant_data["total_chars"] = 0
        participant_data["total_chars"] += message_length
        
        # Award points based on message quality (length)
        if message_length > 300:
            quality_points = 3
        elif message_length > 150:
            quality_points = 2
        elif message_length > 50:
            quality_points = 1
        else:
            quality_points = 0
            
        participant_data["points_accumulated"] += quality_points
        
        # Reinforce the historical figure persona if one is being used
        debate_agent.reinforce_persona(message.author.id)
        
        # Use the enhanced fact-checking response method
        response_data = await debate_agent.fact_check_and_respond(message)
        response = response_data["response"]
        fact_check = response_data["fact_check"]
        
        # Award bonus points for accurate claims
        if fact_check and "✅" in fact_check:
            participant_data["points_accumulated"] += 2
            fact_check += "\n*+2 points awarded for accurate claims!*"
        
        # Send the response
        if len(response) <= 2000:
            await message.reply(response)
        else:
            # Split the response into chunks of 1900 characters
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            for i, chunk in enumerate(chunks):
                await message.channel.send(f"**Part {i+1}/{len(chunks)}**: {chunk}")
        
        # If there's a fact check, send it as a separate embed
        if fact_check:
            fact_check_embed = discord.Embed(
                title="Fact Check Results",
                description=fact_check,
                color=discord.Color.blue()
            )
            fact_check_embed.set_footer(text="Powered by Perplexity AI")
            await message.channel.send(embed=fact_check_embed)

# Commands
@bot.command(name="debate", help="Start a political debate with the bot. Optional: [figure] [level] [topic]")
async def debate(ctx, arg1=None, arg2=None, *, topic=None):
    """
    Start a debate session with the bot.
    
    Can be used in multiple ways:
    !debate - Start debate with random topic
    !debate topic - Start debate on specific topic
    !debate figure topic - Start debate as historical figure
    !debate level topic - Start debate with specific level
    !debate figure level topic - Full specification
    """
    user_id = ctx.author.id
    
    # Check if user is already in a debate
    if user_id in active_debates:
        await ctx.send("You're already in an active debate! Type `!enddebate` to end it first.")
        return
    
    # Parse the arguments
    figure = None
    level = "intermediate"  # Default level
    
    # Process arguments
    if arg1:
        # Check if arg1 is a figure name
        if debate_agent.historical_figures.get_figure_details(arg1):
            figure = arg1
        # Check if arg1 is a level
        elif arg1.lower() in ["beginner", "intermediate", "advanced"]:
            level = arg1.lower()
        # Otherwise it's part of the topic
        else:
            if topic:
                topic = f"{arg1} {arg2} {topic}"
            elif arg2:
                topic = f"{arg1} {arg2}"
            else:
                topic = arg1
            arg1 = None
            arg2 = None
    
    # Process second argument if first was used
    if arg1 and arg2:
        # If we already have a figure, check for level
        if figure and arg2.lower() in ["beginner", "intermediate", "advanced"]:
            level = arg2.lower()
        # Otherwise it's part of the topic
        else:
            if topic:
                topic = f"{arg2} {topic}"
            else:
                topic = arg2
    
    # Set the debate level for this specific user
    debate_agent.set_debate_level(level, ctx.author.id)
    level_info = debate_agent.get_debate_level_description(ctx.author.id)
    
    # Set historical figure for this specific user if specified
    figure_desc = ""
    if figure:
        figure_details = debate_agent.historical_figures.get_figure_details(figure)
        debate_agent.set_historical_figure(figure, ctx.author.id)
        figure_desc = f"**Debating as: {figure_details['name']}**\n{figure_details['description']}\n\n"
    else:
        debate_agent.reset_persona(ctx.author.id)
    
    # Display settings
    settings_embed = discord.Embed(
        title="Debate Settings",
        color=discord.Color.blue()
    )
    
    if figure:
        settings_embed.add_field(
            name="Historical Figure",
            value=f"{figure_details['name']} ({figure_details['era']})",
            inline=False
        )
    
    settings_embed.add_field(
        name="Level",
        value=f"{level_info['name']} (x{level_info['point_multiplier']} points)",
        inline=True
    )
    
    settings_embed.add_field(
        name="Difficulty",
        value=level_info['difficulty'],
        inline=False
    )
    
    settings_embed.add_field(
        name="Complexity",
        value=level_info['complexity'],
        inline=False
    )
    
    await ctx.send("Debate settings:", embed=settings_embed)
    
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
                f"Difficulty level: {level}",
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
    
    # Create a unique debate ID
    debate_id = f"debate-{ctx.author.id}"
    
    # Mark user as in an active debate
    active_debates[ctx.author.id] = {
        "article": top_article,
        "start_time": datetime.datetime.now(),
        "level": level,
        "points_accumulated": 0,
        "messages_count": 0,
        "channel_id": ctx.channel.id,  # Record the channel where the debate is happening
        "participants": {
            str(ctx.author.id): {
                "messages_count": 0, 
                "total_chars": 0,
                "points_accumulated": 0,
                "join_time": datetime.datetime.now()
            }
        }
    }
    
    # Add initiator to the debate participants
    debate_participants[debate_id] = {ctx.author.id}
    user_current_debate[ctx.author.id] = debate_id
    
    # Send information about joining the debate
    await ctx.send("\n\n👥 **Others can join this debate by typing `!join @" + ctx.author.name + "`**")

@bot.command(name="enddebate", help="End your current debate session.")
async def enddebate(ctx, send_email: str = None):
    """
    End the current debate session and award points to all participants.
    Optionally send a debate summary email.
    
    Usage:
    !enddebate - End debate without email
    !enddebate email - End debate and send summary to your registered email
    """
    user_id = ctx.author.id
    
    # Only the initiator can end the debate
    if user_id not in active_debates:
        # Check if they're a participant trying to end someone else's debate
        if user_id in user_current_debate:
            debate_id = user_current_debate[user_id]
            initiator_id = int(debate_id.split('-')[1])
            initiator = await bot.fetch_user(initiator_id)
            await ctx.send(f"Only the debate initiator ({initiator.name}) can end this debate. You can leave with `!leave`.")
        else:
            await ctx.send("You don't have an active debate session.")
        return
    
    # Check if user wants to send email
    send_email_summary = False
    if send_email and send_email.lower() in ["email", "sendemail", "email=true", "true"]:
        # Check if user has an email address registered
        if debate_agent.email_manager.get_user_email(user_id):
            send_email_summary = True
        else:
            # Inform user they need to set an email address
            await ctx.send("You haven't registered an email address. Use `!email set youremail@example.com` to register, then try again.")
            # Continue with ending the debate without email
    
    debate_info = active_debates[user_id]
    debate_id = f"debate-{user_id}"
    debate_topic = debate_info["article"]["title"]
    
    # Get all participants
    all_participants = list(debate_participants.get(debate_id, {user_id}))
    
    # Determine the winner
    winner_id, total_scores, category_scores, winning_reasons = determine_debate_winner(debate_info, all_participants)
    
    # Get winner name
    if winner_id == "bot":
        winner_name = "EchoBreaker AI"
        winner_info = {"name": winner_name, "is_bot": True}
    else:
        try:
            winner_user = await bot.fetch_user(int(winner_id))
            winner_name = winner_user.name
            winner_info = {"name": winner_name, "is_bot": False, "user": winner_user}
        except:
            winner_name = "Unknown Debater"
            winner_info = {"name": winner_name, "is_bot": False}
    
    # Announce the winner dramatically
    await announce_winner(ctx, winner_id, winner_name, winning_reasons, debate_topic)
    
    # Create an aggregate summary embed with scores
    summary_embed = discord.Embed(
        title="Debate Results",
        description=f"The debate on **{debate_topic}** has concluded.",
        color=discord.Color.gold()
    )
    
    # Add a scoreboard section
    scoreboard = ""
    sorted_scores = sorted([(pid, score) for pid, score in total_scores.items()], key=lambda x: x[1], reverse=True)
    
    for i, (pid, score) in enumerate(sorted_scores, 1):
        if pid == "bot":
            name = "EchoBreaker AI"
        else:
            try:
                user = await bot.fetch_user(int(pid))
                name = user.name
            except:
                name = f"User {pid}"
        
        # Add crown for the winner
        prefix = "👑 " if pid == winner_id else ""
        scoreboard += f"{i}. {prefix}**{name}**: {score:.1f} points\n"
    
    summary_embed.add_field(name="Scoreboard", value=scoreboard, inline=False)
    
    # Add a field for judge's notes
    judges_notes = []
    for category, description in {"engagement": "Engagement", "depth": "Depth", "insight": "Insight", 
                                  "evidence": "Evidence", "rhetoric": "Rhetoric", "audience": "Audience Impact"}.items():
        # Find who scored highest in this category
        best_pid = max(category_scores.keys(), key=lambda pid: category_scores[pid].get(category, 0))
        best_score = category_scores[best_pid].get(category, 0)
        
        if best_pid == "bot":
            best_name = "EchoBreaker AI"
        else:
            try:
                best_user = await bot.fetch_user(int(best_pid))
                best_name = best_user.name
            except:
                best_name = f"User {best_pid}"
        
        judges_notes.append(f"**{description}**: {best_name} ({best_score:.1f}/10)")
    
    summary_embed.add_field(name="Judge's Notes", value="\n".join(judges_notes), inline=False)
    
    # Reset agent's persona for each participant
    for participant_id in all_participants:
        debate_agent.reset_persona(participant_id)
    
    # Award bonus points to the winner (if a human won)
    winner_bonus = 0
    if winner_id != "bot":
        winner_bonus = 20  # Bonus points for winning
        # Add note about the winner bonus
        summary_embed.add_field(name="Winner Bonus", value=f"**{winner_name}** earned a **+{winner_bonus} point** victory bonus!", inline=False)
    
    # Generate debate feedback for each participant
    feedback = generate_debate_feedback(debate_info)
    
    # Process results for each participant
    participant_results = []
    email_sent_status = []
    
    for participant_id in all_participants:
        try:
            participant = await bot.fetch_user(participant_id)
            participant_data = debate_info["participants"].get(str(participant_id), 
                                                             {"messages_count": 0, "total_chars": 0, "points_accumulated": 0})
            
            # Calculate debate duration for this participant
            join_time = participant_data.get("join_time", debate_info["start_time"])
            duration = (datetime.datetime.now() - join_time).total_seconds()
            
            # Skip participants who didn't actually send any messages
            if participant_data["messages_count"] == 0:
                continue
                
            # Get difficulty multiplier
            level = debate_info["level"]
            level_info = debate_agent.get_debate_level_description(participant_id)
            
            # Award points and update stats
            result = stats_tracker.complete_debate(participant_id, int(duration))
            points_earned = result["points_earned"]
            adjusted_points = int(points_earned * level_info['point_multiplier'])
            
            # Add bonus points based on message count
            message_count = participant_data["messages_count"]
            message_bonus = min(10, message_count)  # Cap at 10 bonus points
            total_points = adjusted_points + message_bonus
            
            # Add any accumulated points from fact checking, etc.
            total_points += participant_data.get("points_accumulated", 0)
            
            # Add winner bonus if applicable
            if str(participant_id) == winner_id:
                total_points += winner_bonus
            
            # Update final stats
            stats = stats_tracker.add_points(participant_id, total_points)
            
            # Add participant results to summary
            participant_results.append({
                "name": participant.name,
                "points": total_points,
                "messages": message_count,
                "level": stats['level'],
                "id": participant_id,
                "stats": stats
            })
            
            # Send email if requested by the debate initiator
            if send_email_summary and (participant_id == user_id or debate_agent.email_manager.get_user_email(participant_id)):
                # Only send email to the initiator or participants who have emails registered
                is_initiator = participant_id == user_id
                has_email = debate_agent.email_manager.get_user_email(participant_id) is not None
                
                if is_initiator or has_email:
                    # Try to send email
                    email_success, email_message = debate_agent.email_manager.send_debate_summary(
                        participant_id, debate_info, stats, participant, feedback, winner_info
                    )
                    
                    # Add to status report
                    if email_success:
                        email_sent_status.append(f"✅ Email summary sent to {participant.name}")
                    else:
                        email_sent_status.append(f"❌ Failed to send email to {participant.name}: {email_message}")
            
            # Remove from participant tracking
            if participant_id in user_current_debate:
                del user_current_debate[participant_id]
            
            # If this is not the initiator, send them a direct message with their results
            if participant_id != user_id:
                try:
                    stats_embed = create_stats_embed(participant, stats)
                    # Mention if they won in the DM
                    if str(participant_id) == winner_id:
                        await participant.send(f"🏆 Congratulations! You WON the debate and earned {total_points} points (including {winner_bonus} bonus points)!", embed=stats_embed)
                    else:
                        await participant.send(f"The debate you were participating in has ended. You earned {total_points} points!", embed=stats_embed)
                except discord.errors.Forbidden:
                    # Can't DM this user
                    pass
                
        except Exception as e:
            logger.error(f"Error processing debate results for user {participant_id}: {e}")
    
    # Add participant results to summary embed
    for result in participant_results:
        summary_embed.add_field(
            name=f"{result['name']}'s Results",
            value=f"• **Points Earned**: {result['points']}\n"
                  f"• **Messages**: {result['messages']}\n"
                  f"• **Level**: {result['level']}",
            inline=True
        )
    
    # Clean up debate tracking
    if debate_id in debate_participants:
        del debate_participants[debate_id]
    del active_debates[user_id]
    
    # Send the summary
    await ctx.send("Full debate results:", embed=summary_embed)
    
    # Show email sent status if any
    if email_sent_status:
        email_status_embed = discord.Embed(
            title="Email Summary Status",
            description="\n".join(email_sent_status),
            color=discord.Color.blue()
        )
        
        email_status_embed.add_field(
            name="Set Email Address",
            value="To receive debate summaries via email, use the `!email set youremail@example.com` command",
            inline=False
        )
        
        await ctx.send(embed=email_status_embed)
    
    # Show initiator's stats
    initiator_stats = stats_tracker.get_user_stats(user_id)
    stats_embed = create_stats_embed(ctx.author, initiator_stats)
    await ctx.send("Your updated stats:", embed=stats_embed)
    
    # Generate and show debate feedback
    feedback_embed = discord.Embed(
        title="Debate Feedback",
        description="Here's some feedback to help improve your debating skills:",
        color=discord.Color.purple()
    )
    
    for i, tip in enumerate(feedback):
        feedback_embed.add_field(name=f"Tip {i+1}", value=tip, inline=False)
        
    await ctx.send(embed=feedback_embed)

    # At the end of the enddebate command, if email wasn't used, add this:
    if not send_email_summary:
        await ctx.send("📧 **Pro Tip**: Next time, try `!enddebate email` to get a detailed coach analysis sent to your inbox!\nRegister your email with `!email set youremail@example.com`")
    
    # Add welcome instructions again after debate ends
    welcome_embed = discord.Embed(
        title="EchoBreaker Debate Bot",
        description="I'm here to help you sharpen your debate skills by challenging you with strong political viewpoints.",
        color=discord.Color.blue()
    )
    welcome_embed.add_field(
        name="How to start",
        value="Type `!debate [topic]` to begin a debate\n• I'll find a current news article on your topic for us to discuss\n• Example: `!debate climate change` or just `!debate` for a random trending topic",
        inline=False
    )
    welcome_embed.add_field(
        name="Debate Levels",
        value="`!debate beginner [topic]` - Simpler language & gentler arguments (0.8x points)\n"
             "`!debate intermediate [topic]` - Standard level (1.0x points)\n"
             "`!debate advanced [topic]` - Complex language & aggressive arguments (1.2x points)\n"
             "Type `!levels` for more details",
        inline=False
    )
    welcome_embed.add_field(
        name="Fact-Checking",
        value="• Your factual claims are automatically verified using Perplexity AI\n"
              "• Accurate claims earn bonus points\n"
              "• Look for the fact-check results after bot responses\n"
              "• Type `!factcheck` to learn more about this feature",
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
    welcome_embed.add_field(
        name="Commands",
        value="`!stats` - View your debate statistics\n"
             "`!leaderboard` - See top debaters\n"
             "`!enddebate` - End current debate session\n"
             "`!enddebate email` - End debate and receive summary by email\n"
             "`!join @user` - Join another user's debate\n"
             "`!leave` - Leave a debate you've joined",
        inline=False
    )
    welcome_embed.add_field(
        name="Email Features",
        value="• Get detailed debate summaries sent to your inbox\n"
             "• Receive coach-like feedback and performance analysis\n"
             "• Use `!email set youremail@example.com` to register\n"
             "• Type `!emailhelp` for more information",
        inline=False
    )
    welcome_embed.add_field(
        name="Historical Figures",
        value="`!figures` - View available historical figures\n"
              "`!figure [name]` - View details about a figure\n"
              "`!customfigure [name]` - Create any historical figure\n"
              "`!debate [figure] [level] [topic]` - Debate as a historical figure",
        inline=False
    )
    welcome_embed.add_field(
        name="Multi-User Debates",
        value="• Start a debate that others can join\n"
              "• Join ongoing debates with `!join @username`\n"
              "• See active debates with `!debates`\n"
              "• Compete for highest scores in group debates",
        inline=False
    )
    
    await ctx.send("Ready for another debate? Here's what you can do:", embed=welcome_embed)

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

@bot.command(name="factcheck", help="Explains how the fact-checking feature works")
async def explain_factcheck(ctx):
    """Explains the fact-checking feature to users."""
    embed = discord.Embed(
        title="Fact-Checking in Debates",
        description="EchoBreaker uses AI-powered fact-checking to verify claims made during debates.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="How it works",
        value="When you make factual claims in your arguments, the bot will:\n"
              "1. Detect potential factual statements\n"
              "2. Verify them using Perplexity's search capabilities\n"
              "3. Display the results alongside the bot's response",
        inline=False
    )
    
    embed.add_field(
        name="Verdicts",
        value="✅ **True**: Claim is accurate based on reliable sources\n"
              "⚠️ **Partly True** or **Needs Context**: Claim has some accuracy but is missing important context\n"
              "❌ **False**: Claim contradicts reliable sources",
        inline=False
    )
    
    embed.add_field(
        name="Benefits",
        value="• Earn bonus points for accurate claims\n"
              "• Learn to distinguish facts from opinions\n"
              "• Improve your research and argumentation skills",
        inline=False
    )
    
    embed.set_footer(text="Fact-checking powered by Perplexity AI")
    
    await ctx.send(embed=embed)

@bot.command(name="figures", aliases=["historicalfigures", "personas"], help="List available historical figures for debates")
async def list_figures(ctx):
    """Show a list of historical figures the bot can debate as."""
    figures = debate_agent.historical_figures.get_figure_names()
    
    embed = discord.Embed(
        title="Available Historical Figures",
        description="Choose a historical figure for your next debate using `!debate [figure] [level] [topic]`\nExample: `!debate churchill democracy`",
        color=discord.Color.gold()
    )
    
    for figure_id in figures:
        figure = debate_agent.historical_figures.get_figure_details(figure_id)
        embed.add_field(
            name=figure["name"],
            value=f"**Era:** {figure['era']}\n"
                  f"**Style:** {figure['style']}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name="figure", help="Get details about a specific historical figure")
async def figure_details(ctx, figure_id):
    """Show detailed information about a specific historical figure."""
    figure = debate_agent.historical_figures.get_figure_details(figure_id)
    
    if not figure:
        await ctx.send(f"Historical figure '{figure_id}' not found. Use `!figures` to see available options.")
        return
    
    embed = discord.Embed(
        title=figure["name"],
        description=figure["description"],
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Era", value=figure["era"], inline=True)
    embed.add_field(name="Debate Style", value=figure["style"], inline=False)
    embed.add_field(name="Key Beliefs", value=figure["beliefs"], inline=False)
    embed.add_field(
        name="Usage",
        value=f"Start a debate with this figure using:\n`!debate {figure_id.lower()} [level] [topic]`",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name="customfigure", aliases=["custom"], help="Create a custom historical figure to debate as")
async def create_custom_figure(ctx, *, figure_name):
    """
    Create a custom historical figure to debate as.
    
    Args:
        figure_name: The name of the historical figure to create
    """
    if not figure_name:
        await ctx.send("Please provide the name of a historical figure. Example: `!customfigure Napoleon Bonaparte`")
        return
    
    # Show typing indicator while generating
    async with ctx.typing():
        await ctx.send(f"Generating debate persona for {figure_name}... This might take a moment.")
        
        # Generate the custom figure
        figure_key, figure_data = await debate_agent.historical_figures.generate_custom_figure(
            figure_name, debate_agent.client
        )
        
        if not figure_key:
            await ctx.send(f"Sorry, I couldn't generate a persona for {figure_name}. Please try a different figure.")
            return
    
    # Create an embed to display the new figure
    embed = discord.Embed(
        title=f"New Historical Figure: {figure_data['name']}",
        description=figure_data['description'],
        color=discord.Color.purple()
    )
    
    embed.add_field(name="Era", value=figure_data["era"], inline=True)
    embed.add_field(name="Debate Style", value=figure_data["style"], inline=False)
    embed.add_field(name="Key Beliefs", value=figure_data["beliefs"], inline=False)
    embed.add_field(
        name="Usage",
        value=f"Start a debate with this figure using:\n`!debate {figure_key} [level] [topic]`",
        inline=False
    )
    
    await ctx.send(f"✅ Successfully created a debate persona for **{figure_data['name']}**!", embed=embed)

@bot.command(name="helpfigures", help="Learn how to use the historical figures feature")
async def help_figures(ctx):
    """Show help information about the historical figures feature."""
    embed = discord.Embed(
        title="Historical Figures in Debates",
        description="Debate with the bot as if you were talking to historical figures from throughout time.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Pre-defined Figures",
        value="Use `!figures` to see the list of pre-defined historical figures\n"
              "Use `!figure [name]` to see details about a specific figure\n"
              "Example: `!figure churchill`",
        inline=False
    )
    
    embed.add_field(
        name="Creating Custom Figures",
        value="You can create any historical figure with:\n"
              "`!customfigure [full name]`\n"
              "Examples:\n"
              "• `!customfigure Napoleon Bonaparte`\n"
              "• `!customfigure Queen Elizabeth I`\n"
              "• `!customfigure Genghis Khan`",
        inline=False
    )
    
    embed.add_field(
        name="Starting a Debate",
        value="Start a debate with a historical figure:\n"
              "`!debate [figure] [level] [topic]`\n"
              "Examples:\n"
              "• `!debate aristotle ethics`\n"
              "• `!debate churchill hard democracy`\n"
              "• `!debate napoleon_bonaparte war`",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name="myfigures", help="List the custom historical figures you've created")
async def list_custom_figures(ctx):
    """Show a list of custom historical figures created by users."""
    # Get all figures
    all_figures = debate_agent.historical_figures.figures
    
    # Filter to likely custom figures (those with underscores in keys)
    custom_figures = {k: v for k, v in all_figures.items() if "_" in k and " " not in k}
    
    if not custom_figures:
        await ctx.send("No custom historical figures have been created yet. Create one with `!customfigure [name]`!")
        return
    
    embed = discord.Embed(
        title="Custom Historical Figures",
        description="Here are the custom historical figures that have been created:",
        color=discord.Color.purple()
    )
    
    for figure_id, figure in custom_figures.items():
        embed.add_field(
            name=figure["name"],
            value=f"**Era:** {figure['era']}\n"
                  f"**Usage:** `!debate {figure_id} [level] [topic]`",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name="complexity", help="Explains the available linguistic complexity levels")
async def explain_complexity(ctx):
    """Explains the linguistic complexity levels to users."""
    embed = discord.Embed(
        title="Debate Complexity Levels",
        description="Choose the linguistic and argumentative complexity that matches your skill level:",
        color=discord.Color.blue()
    )
    
    # Get descriptions from the agent
    highschool = debate_agent.set_complexity("highschool")
    highschool_info = debate_agent.get_complexity_description()
    
    college = debate_agent.set_complexity("college")
    college_info = debate_agent.get_complexity_description()
    
    professor = debate_agent.set_complexity("professor")
    professor_info = debate_agent.get_complexity_description()
    
    # Reset to default
    debate_agent.set_complexity("college")
    
    # Add fields for each level
    embed.add_field(
        name="🏫 High School Level",
        value=highschool_info["description"] + "\n\n**Features:**\n• " + "\n• ".join(highschool_info["features"]),
        inline=False
    )
    
    embed.add_field(
        name="🎓 College Level",
        value=college_info["description"] + "\n\n**Features:**\n• " + "\n• ".join(college_info["features"]),
        inline=False
    )
    
    embed.add_field(
        name="👨‍🏫 Professor Level",
        value=professor_info["description"] + "\n\n**Features:**\n• " + "\n• ".join(professor_info["features"]),
        inline=False
    )
    
    embed.add_field(
        name="Usage",
        value="Set the complexity when starting a debate:\n"
              "`!debate highschool [topic]`\n"
              "`!debate college [topic]`\n"
              "`!debate professor [topic]`\n\n"
              "You can combine with other options:\n"
              "`!debate churchill professor democracy`\n"
              "`!debate hard highschool climate change`",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name="levels", help="Explains the available debate levels")
async def explain_levels(ctx):
    """Explains the debate levels to users."""
    embed = discord.Embed(
        title="Debate Levels",
        description="Choose the debate level that matches your skill and experience:",
        color=discord.Color.blue()
    )
    
    # Get descriptions from the agent
    beginner = debate_agent.set_debate_level("beginner")
    beginner_info = debate_agent.get_debate_level_description()
    
    intermediate = debate_agent.set_debate_level("intermediate")
    intermediate_info = debate_agent.get_debate_level_description()
    
    advanced = debate_agent.set_debate_level("advanced")
    advanced_info = debate_agent.get_debate_level_description()
    
    # Reset to default
    debate_agent.set_debate_level("intermediate")
    
    # Add fields for each level
    embed.add_field(
        name="🔰 Beginner Level",
        value=f"**Difficulty**: {beginner_info['difficulty']}\n"
              f"**Complexity**: {beginner_info['complexity']}\n"
              f"**Point Multiplier**: {beginner_info['point_multiplier']}x\n\n"
              f"**Features:**\n• " + "\n• ".join(beginner_info["features"]),
        inline=False
    )
    
    embed.add_field(
        name="🏆 Intermediate Level",
        value=f"**Difficulty**: {intermediate_info['difficulty']}\n"
              f"**Complexity**: {intermediate_info['complexity']}\n"
              f"**Point Multiplier**: {intermediate_info['point_multiplier']}x\n\n"
              f"**Features:**\n• " + "\n• ".join(intermediate_info["features"]),
        inline=False
    )
    
    embed.add_field(
        name="⚔️ Advanced Level",
        value=f"**Difficulty**: {advanced_info['difficulty']}\n"
              f"**Complexity**: {advanced_info['complexity']}\n"
              f"**Point Multiplier**: {advanced_info['point_multiplier']}x\n\n"
              f"**Features:**\n• " + "\n• ".join(advanced_info["features"]),
        inline=False
    )
    
    embed.add_field(
        name="Usage",
        value="Set the level when starting a debate:\n"
              "`!debate beginner [topic]`\n"
              "`!debate intermediate [topic]`\n"
              "`!debate advanced [topic]`\n\n"
              "You can combine with historical figures:\n"
              "`!debate churchill advanced democracy`",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name="join", help="Join an ongoing debate")
async def join_debate(ctx, initiator: discord.Member = None):
    """Join an ongoing debate started by another user."""
    user_id = ctx.author.id
    
    # Check if user is already in a debate
    if user_id in user_current_debate:
        await ctx.send("You're already in an active debate! Type `!leave` to leave it first.")
        return
    
    # If no initiator specified, try to find an active debate in the channel
    if not initiator:
        # Look for active debates in the current channel
        channel_debates = []
        for init_id, debate_info in active_debates.items():
            if "channel_id" in debate_info and debate_info["channel_id"] == ctx.channel.id:
                channel_debates.append((init_id, debate_info))
        
        if not channel_debates:
            await ctx.send("No active debates found in this channel. Start one with `!debate [topic]` or specify a user to join their debate.")
            return
        
        # If only one debate in channel, join that one
        if len(channel_debates) == 1:
            initiator_id = channel_debates[0][0]
            debate_info = channel_debates[0][1]
        else:
            # If multiple debates, ask which one to join
            debate_list = "\n".join([f"{i+1}. {bot.get_user(init_id).name}'s debate on: {debate_info['article']['title']}" 
                                   for i, (init_id, debate_info) in enumerate(channel_debates)])
            await ctx.send(f"Multiple debates found in this channel. Please specify which user's debate to join:\n{debate_list}")
            return
    else:
        # User specified an initiator to join
        initiator_id = initiator.id
        if initiator_id not in active_debates:
            await ctx.send(f"{initiator.name} doesn't have an active debate. Start your own with `!debate [topic]`.")
            return
        
        debate_info = active_debates[initiator_id]
    
    # Add user to the debate
    debate_id = f"debate-{initiator_id}"
    debate_participants[debate_id].add(user_id)
    user_current_debate[user_id] = debate_id
    
    # Initialize stats for this participant
    if "participants" not in debate_info:
        debate_info["participants"] = {}
    
    debate_info["participants"][str(user_id)] = {
        "messages_count": 0,
        "total_chars": 0,
        "points_accumulated": 0,
        "join_time": datetime.datetime.now()
    }
    
    # Get debate information for welcome message
    article_title = debate_info["article"]["title"]
    
    # Notify everyone
    await ctx.send(f"📢 {ctx.author.mention} has joined the debate on **{article_title}**! They can now participate in the discussion.")
    
    # Send the user a brief summary of the current debate
    summary_embed = discord.Embed(
        title="Debate Summary",
        description=f"You've joined a debate about: {article_title}",
        color=discord.Color.green()
    )
    
    summary_embed.add_field(
        name="Debate Level", 
        value=f"{debate_info['level'].capitalize()} difficulty", 
        inline=True
    )
    
    initiator_name = bot.get_user(initiator_id).name
    summary_embed.add_field(
        name="Initiator", 
        value=initiator_name, 
        inline=True
    )
    
    participant_count = len(debate_participants[debate_id])
    summary_embed.add_field(
        name="Participants", 
        value=f"{participant_count} debaters", 
        inline=True
    )
    
    await ctx.send(embed=summary_embed)

@bot.command(name="leave", help="Leave the current debate you're participating in")
async def leave_debate(ctx):
    """Leave a debate you've joined."""
    user_id = ctx.author.id
    
    # Check if user is in a debate
    if user_id not in user_current_debate:
        await ctx.send("You're not currently in any debate.")
        return
    
    debate_id = user_current_debate[user_id]
    
    # Remove user from debate tracking
    debate_participants[debate_id].remove(user_id)
    del user_current_debate[user_id]
    
    # If this is an empty set now, clean it up
    if not debate_participants[debate_id]:
        del debate_participants[debate_id]
    
    # Find initiator's debate info and clean up participant data if needed
    initiator_id = int(debate_id.split('-')[1])
    if initiator_id in active_debates:
        debate_info = active_debates[initiator_id]
        if "participants" in debate_info and str(user_id) in debate_info["participants"]:
            # Calculate partial points based on participation time
            participant_data = debate_info["participants"][str(user_id)]
            join_time = participant_data["join_time"]
            duration = (datetime.datetime.now() - join_time).total_seconds()
            
            # Award partial points (could be scaled down since they left early)
            message_count = participant_data["messages_count"]
            if message_count > 0:  # Only award points if they participated
                # Get level multiplier
                level = debate_info["level"]
                level_info = debate_agent.get_debate_level_description(user_id)
                point_multiplier = level_info["point_multiplier"]
                
                # Calculate points - scale based on time spent (max 15 points for leaving early)
                base_points = min(int(duration // 60), 15)
                message_bonus = min(5, message_count)  # Cap at 5 bonus points for leavers
                total_points = int((base_points + message_bonus) * point_multiplier)
                
                # Add points to user stats
                stats_tracker.add_points(user_id, total_points)
                
                # Notify about points earned
                await ctx.send(f"You've earned {total_points} points for your partial participation in the debate.")
            
            # Remove participant data
            del debate_info["participants"][str(user_id)]
    
    await ctx.send(f"{ctx.author.mention} has left the debate.")

@bot.command(name="debates", help="List active debates you can join")
async def list_debates(ctx):
    """List all active debates that users can join."""
    if not active_debates:
        await ctx.send("There are no active debates currently. Start one with `!debate [topic]`!")
        return
    
    embed = discord.Embed(
        title="Active Debates",
        description="Here are the ongoing debates you can join:",
        color=discord.Color.blue()
    )
    
    for initiator_id, debate_info in active_debates.items():
        try:
            initiator = await bot.fetch_user(initiator_id)
            debate_id = f"debate-{initiator_id}"
            participant_count = len(debate_participants.get(debate_id, set()))
            channel = bot.get_channel(debate_info.get("channel_id", 0))
            channel_name = channel.name if channel else "Unknown channel"
            
            embed.add_field(
                name=f"{initiator.name}'s Debate ({participant_count} participants)",
                value=f"**Topic**: {debate_info['article']['title']}\n"
                      f"**Level**: {debate_info['level'].capitalize()}\n"
                      f"**Channel**: {channel_name}\n"
                      f"**Join**: `!join @{initiator.name}`",
                inline=False
            )
        except Exception as e:
            logger.error(f"Error adding debate to list: {e}")
    
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
    
    # Add historical figure feedback if applicable
    if debate_info.get("figure"):
        figure_name = debate_info["figure"].get("name", "the historical figure")
        feedback.append(f"You debated against {figure_name}. Consider researching more about their historical positions and rhetorical style to better counter their arguments next time.")
    
    # Return the feedback list
    return feedback

# Add this new function to determine the debate winner
def determine_debate_winner(debate_info, participants):
    """
    Determine the winner of a debate based on various metrics.
    Returns a tuple of (winner_id, scores, winning_reasons)
    """
    # Track scores for each participant including the bot
    scores = {"bot": 0}
    for participant_id in participants:
        scores[str(participant_id)] = 0
    
    # Define scoring categories
    categories = {
        "engagement": "Number of messages sent",
        "depth": "Average message length",
        "insight": "Interesting points made",
        "evidence": "Use of facts and evidence",
        "rhetoric": "Persuasiveness and style",
        "audience": "Audience impact" 
    }
    
    # Get participant data
    participant_metrics = {}
    for participant_id in participants:
        p_id_str = str(participant_id)
        if p_id_str in debate_info["participants"]:
            data = debate_info["participants"][p_id_str]
            message_count = data.get("messages_count", 0)
            total_chars = data.get("total_chars", 0)
            avg_length = total_chars / max(message_count, 1)
            
            participant_metrics[p_id_str] = {
                "message_count": message_count,
                "avg_length": avg_length,
                "points_accumulated": data.get("points_accumulated", 0)
            }
    
    # Category scores for each participant
    category_scores = {p_id: {} for p_id in scores.keys()}
    
    # Score for engagement (message count)
    max_messages = max([metrics.get("message_count", 0) for metrics in participant_metrics.values()] + [3])  # Minimum 3 for scaling
    for p_id, metrics in participant_metrics.items():
        engagement_score = min(10, (metrics["message_count"] / max_messages) * 10)
        category_scores[p_id]["engagement"] = round(engagement_score, 1)
        scores[p_id] += engagement_score
    
    # Score for depth (average message length)
    for p_id, metrics in participant_metrics.items():
        # Score 0-10 based on average length (0-50: 1-2, 50-100: 3-4, 100-200: 5-6, 200-300: 7-8, 300+: 9-10)
        avg_len = metrics["avg_length"]
        depth_score = min(10, max(1, avg_len / 40))
        category_scores[p_id]["depth"] = round(depth_score, 1)
        scores[p_id] += depth_score
    
    # Score for insight, evidence, rhetoric, audience (partially random but weighted by previous metrics)
    for p_id in scores.keys():
        if p_id == "bot":
            # Bot has predetermined advantages in some categories
            category_scores[p_id]["insight"] = random.uniform(7, 9)
            category_scores[p_id]["evidence"] = random.uniform(7, 9.5)
            category_scores[p_id]["rhetoric"] = random.uniform(6, 9)
            category_scores[p_id]["audience"] = random.uniform(5, 8)
        else:
            # Human participants get scores influenced by their measurable metrics
            base_quality = min(10, participant_metrics.get(p_id, {}).get("points_accumulated", 0) / 3)
            
            # Add some randomness to make it interesting
            category_scores[p_id]["insight"] = round(min(10, base_quality + random.uniform(-2, 4)), 1)
            category_scores[p_id]["evidence"] = round(min(10, base_quality + random.uniform(-1, 3)), 1)
            category_scores[p_id]["rhetoric"] = round(min(10, base_quality + random.uniform(-2, 5)), 1)
            category_scores[p_id]["audience"] = round(min(10, base_quality + random.uniform(-3, 6)), 1)
        
        # Add these scores to the total
        for category in ["insight", "evidence", "rhetoric", "audience"]:
            scores[p_id] += category_scores[p_id][category]
    
    # Determine the winner
    winner_id = max(scores.items(), key=lambda x: x[1])[0]
    
    # Identify the top reasons why the winner won
    winner_categories = category_scores[winner_id]
    top_categories = sorted(winner_categories.items(), key=lambda x: x[1], reverse=True)[:2]
    
    winning_reasons = []
    for category, score in top_categories:
        if score > 6:  # Only mention strong categories
            winning_reasons.append(f"impressive {categories[category].lower()}")
    
    if not winning_reasons:
        winning_reasons = ["overall debate performance"]
    
    return winner_id, scores, category_scores, winning_reasons

# Add this function for creating the animated winner announcement
async def announce_winner(ctx, winner_id, winner_name, winning_reasons, debate_topic):
    """Create a dramatic, animated announcement of the debate winner"""
    
    # Dramatic pause and drum roll
    drum_roll = await ctx.send("🥁 The judges are tallying the scores... 🥁")
    await asyncio.sleep(2)
    
    # Countdown animation
    for i in range(3, 0, -1):
        await drum_roll.edit(content=f"🥁 The winner will be announced in {i}... 🥁")
        await asyncio.sleep(1)
    
    # Dramatic winner reveal
    await drum_roll.edit(content="🎉 **AND THE WINNER IS...** 🎉")
    await asyncio.sleep(1.5)
    
    # Trophy and winner announcement with confetti
    trophy_emojis = ["🏆", "👑", "🎖️", "🥇", "⭐"]
    emoji = random.choice(trophy_emojis)
    
    reasons_text = " and ".join(winning_reasons)
    win_message = (
        f"{emoji} {emoji} {emoji} **{winner_name}** {emoji} {emoji} {emoji}\n\n"
        f"🎊 Congratulations on your victory in the debate about **{debate_topic}**! 🎊\n\n"
        f"The judges were particularly impressed by your {reasons_text}!"
    )
    
    await ctx.send(win_message)

# Add this command to manage email settings
@bot.command(name="email", help="Manage your email settings for debate summaries")
async def manage_email(ctx, action=None, email_address=None):
    """
    Manage email settings for debate summaries.
    
    Usage:
    !email set youremail@example.com - Set your email address
    !email get - View your current email address
    !email remove - Remove your email address
    !email help - Show email command help
    """
    # Create a direct message channel with the user
    if ctx.guild is not None:  # If command was used in a server
        await ctx.send(f"{ctx.author.mention}, I'll send you information about email settings in a direct message for privacy.")
        
    try:
        # Get the user's DM channel
        dm_channel = await ctx.author.create_dm()
        
        if action is None or action.lower() == "help":
            # Help information
            embed = discord.Embed(
                title="Email Settings Help",
                description="Manage your email address for receiving debate summaries",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Set Email Address",
                value="`!email set youremail@example.com`\nRegisters your email to receive debate summaries",
                inline=False
            )
            
            embed.add_field(
                name="View Current Email",
                value="`!email get`\nShows your currently registered email address",
                inline=False
            )
            
            embed.add_field(
                name="Remove Email",
                value="`!email remove`\nRemoves your email address from our records",
                inline=False
            )
            
            embed.add_field(
                name="Privacy Note",
                value="Your email is stored securely and used only for sending debate summaries when requested. It will never be shared with third parties.",
                inline=False
            )
            
            await dm_channel.send(embed=embed)
            return
            
        elif action.lower() == "set":
            if not email_address:
                await dm_channel.send("Please provide an email address. Usage: `!email set youremail@example.com`")
                return
                
            # Validate email format
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email_address):
                await dm_channel.send("Invalid email format. Please provide a valid email address.")
                return
                
            # Set the email in the email manager
            debate_agent.email_manager.set_user_email(ctx.author.id, email_address)
            await dm_channel.send(f"✅ Your email address has been set to `{email_address}`.\n\nYou'll now have the option to receive debate summaries via email after your debates.")
            
        elif action.lower() == "get":
            # Get the current email
            current_email = debate_agent.email_manager.get_user_email(ctx.author.id)
            if current_email:
                await dm_channel.send(f"Your currently registered email address is: `{current_email}`")
            else:
                await dm_channel.send("You don't have an email address registered. Use `!email set youremail@example.com` to set one.")
                
        elif action.lower() == "remove":
            # Remove the email
            if debate_agent.email_manager.remove_user_email(ctx.author.id):
                await dm_channel.send("✅ Your email address has been removed from our records.")
            else:
                await dm_channel.send("You don't have an email address registered.")
                
        else:
            await dm_channel.send("Unknown action. Use `!email help` to see available commands.")
            
    except discord.Forbidden:
        await ctx.send("I couldn't send you a direct message. Please check your privacy settings and try again.")

@bot.command(name="emailhelp", help="Get help with the email summary feature")
async def email_help(ctx):
    """Provides detailed help about the email summary feature."""
    embed = discord.Embed(
        title="Email Summary Feature",
        description="Get personalized debate summaries and coach feedback delivered to your inbox",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Setting Up",
        value="1. Register your email with `!email set youremail@example.com`\n"
              "2. Your email is stored securely and used only for sending summaries",
        inline=False
    )
    
    embed.add_field(
        name="Getting Summaries",
        value="• End a debate with `!enddebate email` to send a summary\n"
              "• Only the debate initiator can request email summaries\n"
              "• Participants who've registered emails will also receive summaries",
        inline=False
    )
    
    embed.add_field(
        name="Summary Contents",
        value="• Detailed debate statistics\n"
              "• Personalized coach feedback\n"
              "• Argument analysis\n"
              "• Practice suggestions for improvement\n"
              "• Summary of your performance in key areas",
        inline=False
    )
    
    embed.add_field(
        name="Managing Your Email",
        value="• View current email: `!email get`\n"
              "• Remove your email: `!email remove`\n"
              "• Get help: `!email help`",
        inline=False
    )
    
    embed.set_footer(text="Your privacy matters - emails are only sent when you request them")
    
    await ctx.send(embed=embed)

# Start the bot, connecting it to the gateway
bot.run(token)
