import os
from mistralai import Mistral
import discord
import requests
import datetime

MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = """You are EchoBreaker, a debate bot that takes strong political positions to engage users in thoughtful debate.

When a debate starts:
1. Randomly choose either a strong conservative/right-leaning OR liberal/left-leaning position on the news topic
2. Present your position clearly and concisely (under 1500 characters)
3. Include 3-4 strong supporting points for your position
4. End with 1-2 questions to engage the user

During the debate:
1. Maintain your chosen political stance consistently
2. Respond to user arguments respectfully but firmly
3. Challenge their points with counterarguments
4. Ask follow-up questions to deepen the discussion
5. Keep responses under 1500 characters
6. Never switch sides - your goal is to defend your position

Your purpose is to help users practice debating against viewpoints they disagree with, in a respectful and educational manner."""

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

class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.conversation_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    async def run(self, message: discord.Message):
        # Add the user message to conversation history
        self.conversation_history.append({"role": "user", "content": message.content})
        
        # Get response from Mistral
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=self.conversation_history,
        )
        
        # Extract the assistant's message
        assistant_message = response.choices[0].message
        
        # Add the assistant's response to conversation history
        self.conversation_history.append({"role": "assistant", "content": assistant_message.content})
        
        return assistant_message.content
