import os
from mistralai import Mistral
import discord
import requests
import datetime

MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = "You are a helpful assistant. Randomly come up with a political perspective that is either strongly left or right leaning. Make this something debatable--a topic that can be an example for respectful and logical debate."

class NewsAgent:
    def __init__(self):
        NEWS_API_KEY = os.getenv("NEWS_API_KEY")
        self.NEWS_API_KEY = NEWS_API_KEY   

    def get_top_article(self, message: discord.Message):

        url = ('https://newsapi.org/v2/top-headlines?'
            'country=us&'
            'from=' + (datetime.date.today() - datetime.timedelta(days=7)).isoformat() + '&'
            'sortBy=popularity&'
            f'apiKey={self.NEWS_API_KEY}')
        
        response = requests.get(url).json()

        """
        response
        {
            -"source": {
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
        }
        """

        return response.articles[0]
    
    def get_related_articles(self, keyword, message: discord.Message):

        url = ('https://newsapi.org/v2/everything?'
            f'q={keyword}&'
            'from=' + (datetime.date.today() - datetime.timedelta(days=7)).isoformat() + '&'
            'sortBy=popularity&'
            f'apiKey={self.NEWS_API_KEY}')
        
        response = requests.get(url).json()

        return response.articles

class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.conversation_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    async def run(self, message: discord.Message):

        self.conversation_history.append({"role": "user", "content": message.content})

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=self.conversation_history,
        )

        return response.choices[0].message.content
