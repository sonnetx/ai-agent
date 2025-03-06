import os
from mistralai import Mistral
import discord
import requests
import datetime
import json
import os.path
from urllib.parse import quote

MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = """You are EchoBreaker, a debate bot that takes VERY STRONG political positions to engage users in thoughtful debate.

When a debate starts:
1. Choose either a strongly conservative/right-leaning OR strongly liberal/left-leaning position on the news topic
2. Present your position clearly and assertively (under 1000 characters)
3. Include 2-3 bold supporting points for your position
4. End with just ONE provocative question to engage the user

During the debate:
1. Maintain your extreme political stance consistently - do not moderate your views
2. Respond to user arguments firmly and confidently
3. Challenge their points with powerful counterarguments
4. Keep responses under 1000 characters
5. Never concede major points or switch sides - your goal is to defend your position vigorously
6. Be somewhat dismissive of opposing viewpoints, like a passionate political commentator

Your purpose is to help users practice debating against strong viewpoints they disagree with, providing a challenging but educational sparring partner."""

class NewsAgent:
    def __init__(self):
        NEWS_API_KEY = os.getenv("NEWS_API_KEY")
        self.NEWS_API_KEY = NEWS_API_KEY   

    def get_top_article(self):
        url = ('https://newsapi.org/v2/top-headlines?'
            'country=us&'
            'from=' + (datetime.date.today() - datetime.timedelta(days=7)).isoformat() + '&'
            'sortBy=popularity&'
            f'apiKey={self.NEWS_API_KEY}')
        
        response = requests.get(url).json()
        
        """
        response
        {
            "articles": [
                {
                    "source": {
                        "id": "the-verge",
                        "name": "The Verge"
                    },
                    "author": "Victoria Song",
                    "title": "NHL officials will start wearing Apple Watches on ice",
                    "description": "The Apple Watch is now the smartwatch of choice for National Hockey League officials. Apple and the NHL just announced a collaboration where on-ice officials will wear Apple Watches that are running special software to receive important in-game information. U…",
                    "url": "https://www.theverge.com/news/621004/nhl-watch-comms-apple-watch-wearables-smartwatch",
                    "urlToImage": "https://platform.theverge.com/wp-content/uploads/sites/2/2025/02/2.-Apple-NHL-Watch-Comms-App-Officials-Image-Getty-Images.png?quality=90&strip=all&crop=0%2C10.737197040292%2C100%2C78.525605919415&w=1200",
                    "publishedAt": "2025-02-28T14:21:51Z",
                    "content": "The NHL Watch Comms app aims to help on-ice officials stay aware of their surroundings.\r\nThe NHL Watch Comms app aims to help on-ice officials stay aware of their surroundings.\r\nThe Apple Watch is no… [+2492 chars]"
                },
                ...
            ]
        }
        """
        
        # Check if articles exist in the response
        if 'articles' in response and len(response['articles']) > 0:
            return response['articles'][0]
        else:
            return {
                "title": "No articles found",
                "author": "Unknown",
                "description": "Could not retrieve articles at this time.",
                "url": "",
                "content": ""
            }
    
    def get_related_articles(self, keyword):
        url = ('https://newsapi.org/v2/everything?'
            f'q={keyword}&'
            'from=' + (datetime.date.today() - datetime.timedelta(days=7)).isoformat() + '&'
            'sortBy=popularity&'
            f'apiKey={self.NEWS_API_KEY}')
        
        response = requests.get(url).json()
        
        if 'articles' in response:
            return response['articles']
        else:
            return []

    def get_article_by_topic(self, topic):
        """Get a news article related to the specified topic."""
        url = ('https://newsapi.org/v2/everything?'
            f'q={topic}&'
            'from=' + (datetime.date.today() - datetime.timedelta(days=7)).isoformat() + '&'
            'sortBy=popularity&'
            f'apiKey={self.NEWS_API_KEY}')
        
        response = requests.get(url).json()
        
        # Check if articles exist in the response
        if 'articles' in response and len(response['articles']) > 0:
            return response['articles'][0]
        else:
            # If no articles found on the topic, return a default message
            return {
                "title": f"No articles found about '{topic}'",
                "author": "Unknown",
                "description": f"Could not find recent articles about '{topic}'. Let's discuss this topic anyway based on our general knowledge.",
                "url": "",
                "content": ""
            }

class FactChecker:
    def __init__(self):
        self.PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
        self.headers = {
            "Authorization": f"Bearer {self.PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
    
    async def check_claim(self, claim):
        """
        Use Perplexity API to check a factual claim.
        Returns a dict with verification results.
        """
        if not self.PERPLEXITY_API_KEY:
            return {"success": False, "error": "No API key found for Perplexity"}
        
        # Format the prompt for fact-checking
        prompt = f"Fact check the following claim and determine if it's accurate. Reply with:\n" \
                 f"1. Whether the claim is True, False, Partly True, or Needs Context\n" \
                 f"2. A brief explanation of your assessment\n" \
                 f"3. References to support your assessment\n\n" \
                 f"Claim: {claim}"
        
        try:
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=self.headers,
                json={
                    "model": "sonar-medium-online",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                fact_check_text = result["choices"][0]["message"]["content"]
                
                # Extract verdict and explanation
                verdict = "Needs verification"
                explanation = fact_check_text
                references = []
                
                # Simple parsing of the response
                if "True" in fact_check_text[:100]:
                    verdict = "True"
                elif "False" in fact_check_text[:100]:
                    verdict = "False"
                elif "Partly True" in fact_check_text[:100]:
                    verdict = "Partly True"
                elif "Needs Context" in fact_check_text[:100]:
                    verdict = "Needs Context"
                
                # Extract references if they exist
                if "References:" in fact_check_text:
                    refs_section = fact_check_text.split("References:")[1].strip()
                    # Simple parsing to extract references
                    references = [r.strip() for r in refs_section.split("\n") if r.strip()]
                
                return {
                    "success": True,
                    "verdict": verdict,
                    "explanation": explanation,
                    "references": references,
                    "raw_response": fact_check_text
                }
            else:
                return {
                    "success": False,
                    "error": f"API request failed with status code {response.status_code}",
                    "response": response.text
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def extract_claims(self, text):
        """
        Extract potential factual claims from a message.
        Returns a list of claim strings.
        """
        # This is a simplified approach - in production, you might use NLP models
        sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 20]
        claims = []
        
        # Heuristics to identify likely factual claims
        claim_indicators = [
            "according to", "studies show", "research indicates", "statistics show",
            "% of", "percent of", "data shows", "evidence suggests", "report",
            "survey", "poll", "analysis", "fact", "figures", "rates", "numbers",
            "in 2", "increase", "decrease", "rise", "fall", "grew", "declined"
        ]
        
        for sentence in sentences:
            # Check if the sentence contains any claim indicators
            if any(indicator in sentence.lower() for indicator in claim_indicators):
                claims.append(sentence)
        
        # Limit to 1-2 claims to avoid excessive API usage
        return claims[:2]

class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.conversation_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.fact_checker = FactChecker()

    async def fact_check_and_respond(self, message: discord.Message):
        """Check facts in user message, then respond with debate points"""
        # Extract claims from the user's message
        claims = self.fact_checker.extract_claims(message.content)
        fact_check_results = []
        fact_check_summary = ""
        
        # Perform fact checking if claims were found
        if claims:
            for claim in claims:
                result = await self.fact_checker.check_claim(claim)
                if result["success"]:
                    fact_check_results.append({
                        "claim": claim,
                        "verdict": result["verdict"],
                        "explanation": result["explanation"]
                    })
        
        # Create a fact check summary if we have results
        if fact_check_results:
            fact_check_summary = "\n\nFACT CHECK RESULTS:\n"
            for i, check in enumerate(fact_check_results, 1):
                fact_check_summary += f"Claim {i}: \"{check['claim']}\"\n"
                fact_check_summary += f"Verdict: {check['verdict']}\n\n"
        
        # Add the user message to conversation history
        self.conversation_history.append({"role": "user", "content": message.content})
        
        # If we have fact check results, add them as a system message
        if fact_check_results:
            system_msg = f"The user made some factual claims. Here are the fact check results you should consider in your response:\n"
            for i, check in enumerate(fact_check_results, 1):
                system_msg += f"Claim: \"{check['claim']}\"\n"
                system_msg += f"Verdict: {check['verdict']}\n"
                system_msg += f"Take this information into account when responding. If the claim is False or Partly True, " \
                              f"point this out politely but firmly in your response. If True, you may still challenge the " \
                              f"relevance or implications of the claim.\n\n"
            
            self.conversation_history.append({"role": "system", "content": system_msg})
        
        # Get response from Mistral
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=self.conversation_history,
        )
        
        # Extract the assistant's message
        assistant_message = response.choices[0].message
        
        # Add the assistant's response to conversation history
        self.conversation_history.append({"role": "assistant", "content": assistant_message.content})
        
        # If we have fact check results, prepare them for display
        fact_check_display = ""
        if fact_check_results:
            fact_check_display = "\n\n**Fact Check Results:**\n"
            for i, check in enumerate(fact_check_results, 1):
                fact_check_display += f"📊 **Claim {i}**: \"{check['claim']}\"\n"
                verdict_emoji = "✅" if check['verdict'] == "True" else "❌" if check['verdict'] == "False" else "⚠️"
                fact_check_display += f"{verdict_emoji} **Verdict**: {check['verdict']}\n\n"
        
        # Return both the bot's response and the fact check display
        return {
            "response": assistant_message.content,
            "fact_check": fact_check_display if fact_check_results else None
        }
    
    async def run(self, message: discord.Message):
        """Legacy method for compatibility"""
        result = await self.fact_check_and_respond(message)
        if result["fact_check"]:
            return result["response"] + "\n" + result["fact_check"]
        return result["response"]

class DebateStatsTracker:
    def __init__(self, file_path="debate_stats.json"):
        self.file_path = file_path
        self.stats = self._load_stats()
    
    def _load_stats(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_stats(self):
        with open(self.file_path, 'w') as f:
            json.dump(self.stats, f)
    
    def get_user_stats(self, user_id):
        user_id = str(user_id)  # Convert to string for JSON
        if user_id not in self.stats:
            self.stats[user_id] = {
                "debates_completed": 0,
                "points": 0,
                "streak": 0,
                "longest_streak": 0,
                "last_debate": None,
                "level": 1,
                "achievements": []
            }
            self._save_stats()
        return self.stats[user_id]
    
    def add_points(self, user_id, points):
        user_id = str(user_id)
        stats = self.get_user_stats(user_id)
        stats["points"] += points
        
        # Update level based on points
        new_level = 1 + stats["points"] // 100
        if new_level > stats["level"]:
            stats["level"] = new_level
            
        self._save_stats()
        return stats
    
    def complete_debate(self, user_id, duration_seconds):
        user_id = str(user_id)
        stats = self.get_user_stats(user_id)
        stats["debates_completed"] += 1
        
        # Calculate points based on debate duration (longer debates = more points)
        # Cap at 30 points max
        points = min(duration_seconds // 60, 30)
        stats["points"] += points
        
        # Update streak
        today = datetime.date.today().isoformat()
        if stats["last_debate"] != today:
            stats["streak"] += 1
            stats["longest_streak"] = max(stats["longest_streak"], stats["streak"])
        stats["last_debate"] = today
        
        # Update level
        new_level = 1 + stats["points"] // 100
        if new_level > stats["level"]:
            stats["level"] = new_level
        
        # Check for achievements
        self._check_achievements(user_id, stats)
        
        self._save_stats()
        return {
            "stats": stats,
            "points_earned": points
        }
    
    def _check_achievements(self, user_id, stats):
        # Define achievements
        achievements = [
            {"id": "first_debate", "name": "First Debate", "condition": stats["debates_completed"] >= 1},
            {"id": "debate_master", "name": "Debate Master", "condition": stats["debates_completed"] >= 10},
            {"id": "point_collector", "name": "Point Collector", "condition": stats["points"] >= 100},
            {"id": "streak_3", "name": "3-Day Streak", "condition": stats["streak"] >= 3},
            {"id": "high_level", "name": "Skilled Debater", "condition": stats["level"] >= 3}
        ]
        
        # Add new achievements
        new_achievements = []
        for achievement in achievements:
            if achievement["id"] not in stats["achievements"] and achievement["condition"]:
                stats["achievements"].append(achievement["id"])
                new_achievements.append(achievement["name"])
        
        return new_achievements
    
    def get_leaderboard(self, limit=10):
        # Convert to list of (id, stats) tuples, sort by points
        users = [(uid, data) for uid, data in self.stats.items()]
        top_users = sorted(users, key=lambda x: x[1]["points"], reverse=True)[:limit]
        return top_users
