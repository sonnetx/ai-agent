import os
from mistralai import Mistral
import discord
import requests
import datetime
import json
import os.path
from urllib.parse import quote
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import logging

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
        # Add these lines to the FactChecker class to enable logging
        self.logger = logging.getLogger("discord")
    
    async def check_claim(self, claim):
        """
        Use Perplexity API to check a factual claim.
        Returns a dict with verification results.
        """
        # Log the claim being checked
        self.logger.info(f"Checking claim: {claim}")
        
        if not self.PERPLEXITY_API_KEY:
            self.logger.error("No API key found for Perplexity")
            return {"success": False, "error": "No API key found for Perplexity"}
        
        # Format the prompt for fact-checking
        prompt = f"Fact check the following claim and determine if it's accurate. Reply with:\n" \
                 f"1. Whether the claim is True, False, Partly True, or Needs Context\n" \
                 f"2. A brief explanation of your assessment\n" \
                 f"3. References to support your assessment\n\n" \
                 f"Claim: {claim}"
        
        try:
            # Log API attempt
            self.logger.info(f"Sending request to Perplexity API")
            
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=self.headers,
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                }
            )
            
            # Log API response status
            self.logger.info(f"Perplexity API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                fact_check_text = result["choices"][0]["message"]["content"]
                
                # Log successful fact check
                self.logger.info(f"Fact check result: {fact_check_text[:100]}...")
                
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
                self.logger.error(f"API request failed with status code {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "error": f"API request failed with status code {response.status_code}",
                    "response": response.text
                }
        except Exception as e:
            self.logger.error(f"Exception during fact-checking: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def extract_claims(self, text):
        """
        Extract potential factual claims from a message.
        Returns a list of claim strings.
        """
        # Log the incoming text for debugging
        self.logger.info(f"Analyzing for factual claims: {text}")
        
        # Improved sentence splitting - handle both periods and exclamation/question marks
        sentences = []
        for sentence in re.split(r'[.!?]+', text):
            sentence = sentence.strip()
            if len(sentence) > 20:
                sentences.append(sentence)
        
        # Log the sentences found
        self.logger.info(f"Sentences found: {sentences}")
        
        claims = []
        
        # Comprehensive list of claim indicators
        claim_indicators = [
            # Research and data indicators
            "according to", "studies show", "research indicates", "statistics show",
            "data shows", "evidence suggests", "report", "survey", "poll", "analysis",
            "research", "study", "findings", "data", "evidence", "statistics",
            
            # Numerical indicators
            "% of", "percent of", "percentage", "figures", "rates", "numbers",
            "majority", "minority", "half", "third", "quarter", "fraction",
            
            # Time-based indicators
            "in 2", "last year", "this year", "decade", "century", "recently",
            "historically", "traditionally", "currently", "nowadays", "today",
            
            # Change indicators
            "increase", "decrease", "rise", "fall", "grew", "declined", "dropped",
            "went up", "went down", "surged", "plummeted", "skyrocketed", "collapsed",
            "doubled", "tripled", "quadrupled", "halved", "expanded", "contracted",
            
            # Economic indicators
            "stock", "price", "market", "economy", "economic", "financial", "fiscal",
            "gdp", "inflation", "recession", "growth", "deficit", "surplus", "debt",
            "investment", "revenue", "profit", "loss", "sales", "earnings", "dividend",
            "shareholders", "investors", "consumers", "customers", "industry", "sector",
            
            # Quantity indicators
            "billion", "million", "thousand", "hundred", "dozens", "numerous", "several",
            "many", "few", "countless", "abundant", "scarce", "rare", "common",
            
            # Reporting indicators
            "announced", "reported", "stated", "confirmed", "revealed", "disclosed",
            "claimed", "asserted", "declared", "mentioned", "noted", "cited",
            "published", "released", "issued", "documented", "verified",
            
            # Comparison indicators
            "more than", "less than", "higher than", "lower than", "greater than",
            "better than", "worse than", "compared to", "relative to", "versus",
            
            # Factual statement indicators
            "fact", "truth", "reality", "actually", "indeed", "certainly", "definitely",
            "undoubtedly", "indisputably", "objectively", "empirically", "factually",
            
            # Policy and law indicators
            "law", "policy", "regulation", "legislation", "rule", "mandate", "ban",
            "legal", "illegal", "constitutional", "unconstitutional", "prohibited",
            "required", "mandatory", "permitted", "allowed", "forbidden"
        ]
        
        # Expanded patterns for numerical claims
        numerical_patterns = [
            r'\d+%', r'\d+ percent', r'\$\d+', r'\d+ dollars', r'\d+ euros',
            r'\d+ people', r'\d+ million', r'\d+ billion', r'\d+ trillion',
            r'\d+th', r'\d+nd', r'\d+rd', r'\d+st', r'\d+ times', r'\d+-fold',
            r'increased by \d+', r'decreased by \d+', r'rose by \d+', r'fell by \d+',
            r'grew by \d+', r'declined by \d+', r'dropped by \d+', r'gained \d+',
            r'lost \d+', r'added \d+', r'subtracted \d+', r'multiplied by \d+',
            r'divided by \d+', r'factor of \d+', r'ratio of \d+', r'proportion of \d+',
            r'\d+ degrees', r'\d+ percent', r'\d+ percentage points'
        ]
        
        # Additional simple claims detection for short statements with numbers
        # This will catch things like "went up by 7%" without requiring longer sentences
        simple_number_pattern = r'\b\d+\s*%|\b\d+\s*percent'
        
        # First, check the entire text for simple numerical statements
        if re.search(simple_number_pattern, text, re.IGNORECASE):
            # Find the sentence containing the percentage
            for sentence in sentences:
                if re.search(simple_number_pattern, sentence, re.IGNORECASE):
                    claims.append(sentence)
                    self.logger.info(f"Found percentage claim: {sentence}")
        
        # Then do our normal claim detection for each sentence
        for sentence in sentences:
            sentence_lower = sentence.lower()
            # Check if the sentence contains any claim indicators
            if any(indicator in sentence_lower for indicator in claim_indicators):
                claims.append(sentence)
                self.logger.info(f"Found indicator-based claim: {sentence}")
            # Check for numerical patterns
            elif any(re.search(pattern, sentence, re.IGNORECASE) for pattern in numerical_patterns):
                claims.append(sentence)
                self.logger.info(f"Found pattern-based claim: {sentence}")
        
        # Deduplicate claims
        claims = list(set(claims))
        
        # Log the claims found
        self.logger.info(f"Claims detected: {claims}")
        
        # Limit to 1-2 claims to avoid excessive API usage
        return claims[:2]

class HistoricalFigures:
    """Manages historical figure personas for debates"""
    
    def __init__(self):
        # Dictionary of historical figures with their details
        self.figures = {
            "socrates": {
                "name": "Socrates",
                "era": "Ancient Greece (470–399 BCE)",
                "description": "Athenian philosopher known for the Socratic method of questioning.",
                "style": "Constantly questions assumptions, avoids making direct assertions, and leads others to their own contradictions.",
                "beliefs": "Valued wisdom, virtue, and the pursuit of truth. Believed that knowledge comes from questioning and self-examination.",
                "prompt": "You are debating as Socrates, the ancient Greek philosopher. Use the Socratic method by asking probing questions to lead the user to examine their own beliefs. Don't make direct assertions, but rather guide through questions. Begin responses with questions. Phrase things as 'Perhaps we should consider...' or 'What if we examined...' End with reflective questions."
            },
            "churchill": {
                "name": "Winston Churchill",
                "era": "British Statesman (1874-1965)",
                "description": "British Prime Minister who led the UK during World War II.",
                "style": "Eloquent, witty, and uses powerful rhetoric with memorable turns of phrase.",
                "beliefs": "Strong defender of democracy, liberty, and Western civilization against totalitarianism.",
                "prompt": "You are debating as Winston Churchill, the British statesman and wartime leader. Use powerful rhetoric, memorable phrases, and occasional wit or sarcasm. Be steadfast in your principles, particularly regarding freedom and democracy. Speak with unwavering resolve. Use British phrases and occasionally refer to historical events from WWII as analogies."
            },
            "mlk": {
                "name": "Martin Luther King Jr.",
                "era": "American Civil Rights Leader (1929-1968)",
                "description": "Minister and activist who led the civil rights movement.",
                "style": "Eloquent, inspiring, and morally persuasive with religious references.",
                "beliefs": "Advocated for racial equality, nonviolence, and social justice through peaceful protest.",
                "prompt": "You are debating as Martin Luther King Jr., the civil rights leader. Emphasize moral arguments, use religious references where appropriate, and focus on ideals of equality and justice. Speak with passion and conviction about human dignity. Use rhetorical devices like repetition and metaphor, and occasionally reference the American dream and constitutional principles."
            },
            "marx": {
                "name": "Karl Marx",
                "era": "Philosopher & Economist (1818-1883)",
                "description": "German philosopher and economist who developed communist theory.",
                "style": "Analytical, critical of capitalism, and focused on economic class dynamics.",
                "beliefs": "Advocated for workers' rights, criticized capitalism's exploitation, and promoted collective ownership.",
                "prompt": "You are debating as Karl Marx, the philosopher and economic theorist. Analyze issues through the lens of class struggle and economic systems. Critique capitalism frequently, emphasize the exploitation of workers, and advocate for collective solutions. Use terms like 'bourgeoisie,' 'proletariat,' and 'means of production.' Reference historical materialism and the inevitable progression of economic systems."
            },
            "thatcher": {
                "name": "Margaret Thatcher",
                "era": "British Prime Minister (1925-2013)",
                "description": "First female British PM known for conservative policies.",
                "style": "Direct, unyielding, and focused on individual responsibility and free markets.",
                "beliefs": "Strong supporter of free markets, reduced government spending, and traditional values.",
                "prompt": "You are debating as Margaret Thatcher, the former British Prime Minister. Be direct and unyielding in your arguments. Emphasize individualism, personal responsibility, and free market solutions. Express skepticism of government programs and state control. Use phrases like 'There is no alternative' or refer to the dangers of socialism. Occasionally mention your background as a grocer's daughter to emphasize your practical approach."
            },
            "gandhi": {
                "name": "Mahatma Gandhi",
                "era": "Indian Independence Leader (1869-1948)",
                "description": "Led India's independence movement through nonviolent resistance.",
                "style": "Gentle but firm, principled, and focused on moral arguments and nonviolence.",
                "beliefs": "Advocated for nonviolence, civil disobedience, self-reliance, and religious tolerance.",
                "prompt": "You are debating as Mahatma Gandhi, the Indian independence leader. Emphasize nonviolent approaches and moral principles. Speak simply but profoundly, occasionally referencing truth, love, and self-discipline. Advocate for self-reliance and principled resistance to unjust systems. Use gentle but firm language, and occasionally refer to your own experiences with civil disobedience."
            },
            "aristotle": {
                "name": "Aristotle",
                "era": "Ancient Greek Philosopher (384-322 BCE)",
                "description": "Influential philosopher who studied under Plato and tutored Alexander the Great.",
                "style": "Systematic, logical, and focused on practical wisdom and the golden mean.",
                "beliefs": "Believed in virtue ethics, moderation, and finding the middle ground between extremes.",
                "prompt": "You are debating as Aristotle, the ancient Greek philosopher. Approach arguments systematically, identify different categories of understanding, and emphasize balance and moderation (the 'golden mean'). Refer to virtues and the good life. Begin by analyzing the nature or essence of the topic. Occasionally reference your biological observations or political theories. Use logical structures and acknowledge complexity."
            },
            "roosevelt": {
                "name": "Franklin D. Roosevelt",
                "era": "US President (1882-1945)",
                "description": "US President who led during the Great Depression and WWII.",
                "style": "Optimistic, reassuring, and focused on government action to help citizens.",
                "beliefs": "Championed government programs to help ordinary people, regulate business, and ensure economic security.",
                "prompt": "You are debating as Franklin D. Roosevelt, the US President during the Great Depression and WWII. Express optimism even in difficult times, advocate for government programs to help ordinary citizens, and emphasize the role of government in ensuring economic security. Occasionally reference your New Deal programs or the fight against fascism. Use warm, reassuring language that conveys confidence."
            }
        }
    
    def get_figure_names(self):
        """Returns a list of available historical figures"""
        return sorted(self.figures.keys())
    
    def get_figure_details(self, figure_id):
        """Returns details about a specific historical figure"""
        if not figure_id:
            return None
            
        # Try different formats for the figure ID
        figure_id_variations = [
            figure_id.lower(),                       # original (lowercase)
            figure_id.lower().replace("_", " "),     # replace underscores with spaces
            figure_id.lower().replace(" ", "_")      # replace spaces with underscores
        ]
        
        # Try each variation
        for variation in figure_id_variations:
            if variation in self.figures:
                return self.figures[variation]
                
        return None
    
    def get_prompt_for_figure(self, figure_id):
        """Returns the specialized prompt for a historical figure"""
        figure_id = figure_id.lower()
        if figure_id in self.figures:
            # Get the base debate functionality but prioritize the historical figure's voice
            base_prompt = """You are participating in a political debate on a current topic.
Your primary role is to:
1. Take strong positions and defend them
2. Challenge the user's arguments with counterpoints
3. Keep responses concise (under 1000 characters)
4. Never concede major points or switch sides"""
            
            figure_prompt = self.figures[figure_id]["prompt"]
            
            # Create a combined prompt that emphasizes the historical figure's voice
            combined_prompt = f"""MOST IMPORTANT: {figure_prompt}

While maintaining the above historical persona completely, also incorporate these debate mechanics:
{base_prompt}

Remember, your primary identity is as {self.figures[figure_id]['name']} - your language, reasoning style, values, and worldview should consistently reflect this historical figure throughout the entire debate. Never break character."""
            
            return combined_prompt
        return SYSTEM_PROMPT  # Return default prompt if figure not found

    async def generate_custom_figure(self, figure_name, client):
        """
        Dynamically generate a persona for any historical figure requested by the user
        """
        # Use the Mistral API to generate a custom persona for the requested figure
        prompt = f"""Create a debate persona for the historical figure: {figure_name}.
        
        Format your response as JSON with these fields:
        - name: The historical figure's full name
        - era: When they lived (years and context)
        - description: A brief description of who they were
        - style: Their speaking/argument style
        - beliefs: Their key beliefs or positions
        - prompt: Instructions for an AI to emulate their debate style (be specific about tone, rhetoric, philosophical approach, and phrases they would use)
        
        Be historically accurate but focus on aspects that would be relevant in a modern debate.
        """
        
        try:
            response = await client.chat.complete_async(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract the response content
            content = response.choices[0].message.content
            
            # Find JSON content in the response (it might be wrapped in markdown code blocks)
            import re
            import json
            
            # Try to extract JSON from markdown code blocks first
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no code blocks, use the whole response
                json_str = content
            
            # Clean up the text to ensure it's valid JSON
            # Remove any non-JSON text before or after
            json_str = re.sub(r'^[^{]*', '', json_str)
            json_str = re.sub(r'[^}]*$', '', json_str)
            
            figure_data = json.loads(json_str)
            
            # Add to custom figures with consistent naming (both space and underscore versions)
            space_key = figure_name.lower()
            underscore_key = figure_name.lower().replace(" ", "_")
            
            self.figures[space_key] = figure_data
            if space_key != underscore_key:
                self.figures[underscore_key] = figure_data
            
            return underscore_key, figure_data  # Return underscore version for cleaner commands
        
        except Exception as e:
            print(f"Error generating custom figure: {e}")
            return None, {"error": str(e)}

class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        # Replace single conversation history with a dictionary keyed by user ID
        self.user_conversations = {}
        self.fact_checker = FactChecker()
        self.historical_figures = HistoricalFigures()
        # Replace single current_figure with a dictionary keyed by user ID
        self.user_figures = {}
        # Replace single debate_level with a dictionary keyed by user ID
        self.user_debate_levels = {}
        # Add email manager
        self.email_manager = EmailManager()
    
    def _get_user_conversation(self, user_id):
        """Get conversation history for a specific user, creating it if needed"""
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
        return self.user_conversations[user_id]
    
    def _get_user_figure(self, user_id):
        """Get current figure for a specific user"""
        return self.user_figures.get(user_id)
    
    def _get_user_debate_level(self, user_id):
        """Get debate level for a specific user, defaulting to 'intermediate'"""
        return self.user_debate_levels.get(user_id, "intermediate")
    
    def set_debate_level(self, level, user_id):
        """Set the unified debate level for a specific user"""
        valid_levels = ["beginner", "intermediate", "advanced"]
        if level.lower() in valid_levels:
            self.user_debate_levels[user_id] = level.lower()
            return True
        return False
    
    def get_debate_level_description(self, user_id=None):
        """Get a description of the current debate level for a user"""
        level = self.user_debate_levels.get(user_id, "intermediate") if user_id else "intermediate"
        
        descriptions = {
            "beginner": {
                "name": "Beginner",
                "difficulty": "Easy - I'll be more willing to concede points and use gentler counterarguments",
                "complexity": "High School level vocabulary and straightforward reasoning",
                "point_multiplier": 0.8,
                "features": [
                    "Simpler vocabulary and sentence structure",
                    "More willing to acknowledge your points",
                    "Clearer explanations with concrete examples",
                    "Less aggressive challenging of your arguments"
                ]
            },
            "intermediate": {
                "name": "Intermediate",
                "difficulty": "Normal - I'll present balanced arguments with moderate intensity",
                "complexity": "College level vocabulary and nuanced reasoning",
                "point_multiplier": 1.0,
                "features": [
                    "Moderate vocabulary and some specialized terms",
                    "Balanced approach to counterarguments",
                    "Mix of theoretical concepts and practical examples",
                    "Firm defense of position with occasional concessions"
                ]
            },
            "advanced": {
                "name": "Advanced",
                "difficulty": "Hard - I'll aggressively defend my position and thoroughly challenge yours",
                "complexity": "Professor level vocabulary with sophisticated reasoning",
                "point_multiplier": 1.2,
                "features": [
                    "Advanced vocabulary and complex sentence structures",
                    "Aggressive defense of position with minimal concessions",
                    "Sophisticated arguments drawing on multiple disciplines",
                    "Rigorous challenging of your arguments' premises and logic"
                ]
            }
        }
        return descriptions.get(level, descriptions["intermediate"])
    
    def _get_level_instructions(self, user_id):
        """Get system instructions for a user's current debate level"""
        level = self._get_user_debate_level(user_id)
        
        instructions = {
            "beginner": """
DEBATE LEVEL: BEGINNER
- Use vocabulary and sentence structures accessible to high school students
- Present your arguments clearly with straightforward reasoning
- Be somewhat willing to acknowledge the validity of the user's points
- Provide concrete examples and simple analogies
- Challenge the user's arguments gently, focusing on major flaws
- Keep sentences relatively short and direct
""",
            "intermediate": """
DEBATE LEVEL: INTERMEDIATE
- Use vocabulary and sentence structures appropriate for college-educated adults
- Present nuanced arguments that consider multiple perspectives
- Maintain your position firmly but acknowledge reasonable points
- Balance theoretical concepts with practical examples
- Challenge the user's arguments directly but respectfully
- Use moderately complex sentence structures and rhetorical techniques
""",
            "advanced": """
DEBATE LEVEL: ADVANCED
- Use advanced vocabulary, complex sentence structures, and sophisticated rhetorical techniques
- Present complex, multi-layered arguments drawing on interdisciplinary knowledge
- Aggressively defend your position with minimal concessions
- Make nuanced distinctions and address subtle counterarguments
- Rigorously challenge the premises and logic of the user's arguments
- Use abstract reasoning and hypothetical scenarios to strengthen your position
"""
        }
        return instructions.get(level, instructions["intermediate"])
    
    def set_historical_figure(self, figure_id, user_id):
        """Set the bot to speak as a historical figure for a specific user"""
        figure = self.historical_figures.get_figure_details(figure_id)
        if figure:
            # Update the system prompt with the historical figure's instructions
            new_prompt = self.historical_figures.get_prompt_for_figure(figure_id)
            # Reset this user's conversation with new prompt
            self.user_conversations[user_id] = [
                {"role": "system", "content": new_prompt}
            ]
            self.user_figures[user_id] = figure
            return True
        return False
    
    def reset_persona(self, user_id):
        """Reset to default debate persona for a specific user"""
        self.user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        if user_id in self.user_figures:
            del self.user_figures[user_id]
    
    async def fact_check_and_respond(self, message: discord.Message):
        """Check facts in user message, then respond with debate points"""
        user_id = message.author.id
        
        # Extract claims from the user's message
        claims = self.fact_checker.extract_claims(message.content)
        fact_check_results = []
        
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
        
        # Get user's conversation history
        conversation = self._get_user_conversation(user_id)
        
        # Add the user message to conversation history
        conversation.append({"role": "user", "content": message.content})
        
        # If we have fact check results, add them as a system message
        if fact_check_results:
            # Check if we're debating as a historical figure
            persona_reminder = ""
            user_figure = self._get_user_figure(user_id)
            if user_figure:
                persona_reminder = f"IMPORTANT: You are speaking as {user_figure['name']}. Maintain this historical figure's voice, style, and perspective completely while addressing these claims."
            
            # Add complexity reminder
            complexity_reminder = self._get_level_instructions(user_id)
            
            system_msg = f"{persona_reminder}\n{complexity_reminder}\nThe user made some factual claims. Here are the fact check results you should consider in your response:\n"
            for i, check in enumerate(fact_check_results, 1):
                system_msg += f"Claim: \"{check['claim']}\"\n"
                system_msg += f"Verdict: {check['verdict']}\n"
                system_msg += f"Address this claim in a way that's consistent with your character's worldview and knowledge. " \
                              f"If the claim is False or Partly True, challenge it. If True, you may still interpret it through your historical lens.\n\n"
            
            conversation.append({"role": "system", "content": system_msg})
        
        # Get response from Mistral
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=conversation,
        )
        
        # Extract the assistant's message
        assistant_message = response.choices[0].message
        
        # Add the assistant's response to conversation history
        conversation.append({"role": "assistant", "content": assistant_message.content})
        
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

    def reinforce_persona(self, user_id):
        """
        Reinforce the historical figure's persona during long debates
        to prevent character drift for a specific user
        """
        if user_id not in self.user_figures:
            return  # No persona to reinforce
        
        user_figure = self.user_figures[user_id]
        conversation = self._get_user_conversation(user_id)
        
        # Check if we have enough conversation history to need reinforcement
        if len(conversation) >= 6:  # After a few exchanges
            # Add a reminder to stay in character
            reminder = {
                "role": "system", 
                "content": f"IMPORTANT REMINDER: You are {user_figure['name']}. Continue to speak authentically as this historical figure would, using their characteristic language, rhetorical style, and expressing their worldview. Maintain this persona completely in your next response."
            }
            
            # Insert the reminder before the most recent user message
            conversation.insert(-1, reminder)
            
            # Keep conversation history from growing too large
            if len(conversation) > 10:
                # Keep the system prompts, plus the 4 most recent messages
                system_prompts = [msg for msg in conversation if msg["role"] == "system"]
                recent_messages = conversation[-4:]
                
                # Reconstruct conversation with system prompts and recent messages
                self.user_conversations[user_id] = []
                # First add the initial system prompt (the persona)
                self.user_conversations[user_id].append(system_prompts[0])
                # Then add the personality reminder
                self.user_conversations[user_id].append(reminder)
                # Then add recent messages
                self.user_conversations[user_id].extend(recent_messages)

class DebateStatsTracker:
    def __init__(self, file_path="debate_stats.json"):
        self.file_path = file_path
        self.stats = self._load_stats()
        # Add reference to email manager
        self.email_manager = EmailManager()
    
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

class EmailManager:
    """Manages sending debate summary emails to users"""
    
    def __init__(self):
        # Get email configuration from environment variables
        self.email_enabled = False
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
        self.sender_email = os.getenv("EMAIL_SENDER")
        self.sender_password = os.getenv("EMAIL_PASSWORD")
        
        # Check if email functionality is properly configured
        if self.sender_email and self.sender_password:
            self.email_enabled = True
        
        # Dictionary to store user email addresses
        self.user_emails = {}
        self._load_user_emails()
    
    def _load_user_emails(self):
        """Load saved user email addresses from file"""
        try:
            if os.path.exists("user_emails.json"):
                with open("user_emails.json", "r") as f:
                    self.user_emails = json.load(f)
        except Exception as e:
            print(f"Error loading user emails: {e}")
    
    def _save_user_emails(self):
        """Save user email addresses to file"""
        try:
            with open("user_emails.json", "w") as f:
                json.dump(self.user_emails, f)
        except Exception as e:
            print(f"Error saving user emails: {e}")
    
    def set_user_email(self, user_id, email):
        """Set a user's email address"""
        self.user_emails[str(user_id)] = email
        self._save_user_emails()
        return True
    
    def get_user_email(self, user_id):
        """Get a user's email address if saved"""
        return self.user_emails.get(str(user_id))
    
    def remove_user_email(self, user_id):
        """Remove a user's email address"""
        if str(user_id) in self.user_emails:
            del self.user_emails[str(user_id)]
            self._save_user_emails()
            return True
        return False
    
    def format_debate_email(self, debate_info, stats, participant, feedback, winner_info=None):
        """
        Format a debate summary email with coach-like feedback
        
        Args:
            debate_info: Dictionary with debate information
            stats: User's debate statistics
            participant: Discord user object for the participant
            feedback: List of feedback points
            winner_info: Optional winner information
            
        Returns:
            Tuple of (subject, plain_text, html)
        """
        debate_topic = debate_info["article"]["title"]
        debate_date = datetime.datetime.now().strftime("%B %d, %Y")
        
        # Create plain text version
        text = f"DEBATE SUMMARY - {debate_date}\n\n"
        text += f"Topic: {debate_topic}\n"
        text += f"Participant: {participant.name}\n"
        text += f"Duration: {int((datetime.datetime.now() - debate_info['start_time']).total_seconds() / 60)} minutes\n"
        
        if winner_info:
            text += f"Winner: {winner_info['name']}\n"
        
        # Add stats section
        text += "\n\nDEBATE STATISTICS\n"
        text += f"Messages sent: {debate_info['participants'][str(participant.id)]['messages_count']}\n"
        text += f"Points earned: {debate_info['participants'][str(participant.id)]['points_accumulated']}\n"
        text += f"Total debate level: {stats['level']} ({stats['points']} points)\n"
        text += f"Debate streak: {stats['streak']} days\n"
        
        # Add feedback section
        text += "\n\nDEBATE COACH FEEDBACK\n"
        for i, point in enumerate(feedback, 1):
            text += f"{i}. {point}\n"
        
        # Add argument analysis
        text += "\n\nARGUMENT ANALYSIS\n"
        
        # Calculate metrics based on available data
        avg_length = debate_info['participants'][str(participant.id)].get('total_chars', 0) / max(1, debate_info['participants'][str(participant.id)]['messages_count'])
        
        # Provide analysis based on message length
        if avg_length < 100:
            text += "- Your responses tended to be brief. Consider developing your arguments more fully.\n"
        elif avg_length > 300:
            text += "- You provided substantial responses, showing good depth in your arguments.\n"
        
        text += "- Key strengths: "
        if avg_length > 200:
            text += "argument development, "
        if debate_info['participants'][str(participant.id)]['messages_count'] > 5:
            text += "consistent engagement, "
        text += "willingness to engage with challenging viewpoints\n"
        
        text += "\n\nPRACTICE SUGGESTIONS\n"
        text += "1. Focus on developing counterarguments to opposing positions\n"
        text += "2. Practice identifying logical fallacies in arguments\n"
        text += "3. Work on providing specific evidence to support your claims\n"
        
        text += "\n\nThis email was sent by EchoBreaker Debate Bot. You can change your email settings with the !email command in Discord."
        
        # Create HTML version
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
                h1, h2 {{ color: #2c3e50; }}
                .stats {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .feedback {{ margin: 20px 0; }}
                .feedback-item {{ margin-bottom: 10px; }}
                .analysis {{ background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ font-size: 12px; color: #6c757d; margin-top: 30px; border-top: 1px solid #dee2e6; padding-top: 10px; }}
            </style>
        </head>
        <body>
            <h1>Debate Summary</h1>
            <p><strong>Date:</strong> {debate_date}</p>
            <p><strong>Topic:</strong> {debate_topic}</p>
            <p><strong>Participant:</strong> {participant.name}</p>
            <p><strong>Duration:</strong> {int((datetime.datetime.now() - debate_info['start_time']).total_seconds() / 60)} minutes</p>
        """
        
        if winner_info:
            html += f"<p><strong>Winner:</strong> {winner_info['name']}</p>"
        
        # Add stats section
        html += f"""
            <div class="stats">
                <h2>Debate Statistics</h2>
                <p><strong>Messages sent:</strong> {debate_info['participants'][str(participant.id)]['messages_count']}</p>
                <p><strong>Points earned:</strong> {debate_info['participants'][str(participant.id)]['points_accumulated']}</p>
                <p><strong>Total debate level:</strong> {stats['level']} ({stats['points']} points)</p>
                <p><strong>Debate streak:</strong> {stats['streak']} days</p>
            </div>
        """
        
        # Add feedback section
        html += f"""
            <div class="feedback">
                <h2>Debate Coach Feedback</h2>
        """
        
        for point in feedback:
            html += f'<div class="feedback-item">• {point}</div>'
        
        html += "</div>"
        
        # Add argument analysis
        html += """
            <div class="analysis">
                <h2>Argument Analysis</h2>
        """
        
        # Provide analysis based on message length
        if avg_length < 100:
            html += "<p>Your responses tended to be brief. Consider developing your arguments more fully.</p>"
        elif avg_length > 300:
            html += "<p>You provided substantial responses, showing good depth in your arguments.</p>"
        
        html += "<p><strong>Key strengths:</strong> "
        if avg_length > 200:
            html += "argument development, "
        if debate_info['participants'][str(participant.id)]['messages_count'] > 5:
            html += "consistent engagement, "
        html += "willingness to engage with challenging viewpoints</p>"
        
        html += """
                <h3>Practice Suggestions</h3>
                <ol>
                    <li>Focus on developing counterarguments to opposing positions</li>
                    <li>Practice identifying logical fallacies in arguments</li>
                    <li>Work on providing specific evidence to support your claims</li>
                </ol>
            </div>
            <div class="footer">
                This email was sent by EchoBreaker Debate Bot. You can change your email settings with the !email command in Discord.
            </div>
        </body>
        </html>
        """
        
        subject = f"Debate Summary: {debate_topic} - {debate_date}"
        
        return (subject, text, html)
    
    def send_debate_summary(self, user_id, debate_info, stats, participant, feedback, winner_info=None):
        """
        Send a debate summary email to a user
        
        Returns:
            tuple: (success, message)
        """
        if not self.email_enabled:
            return (False, "Email service is not configured properly")
        
        email = self.get_user_email(user_id)
        if not email:
            return (False, "No email address registered for this user")
        
        try:
            subject, text, html = self.format_debate_email(debate_info, stats, participant, feedback, winner_info)
            
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = email
            
            # Add plain text and HTML parts
            part1 = MIMEText(text, "plain")
            part2 = MIMEText(html, "html")
            message.attach(part1)
            message.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, email, message.as_string())
            
            return (True, "Email successfully sent")
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return (False, f"Error sending email: {str(e)}")
