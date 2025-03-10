# EchoBreaker - AI Debate Bot

EchoBreaker is an advanced AI debate bot for Discord that helps users sharpen their debate skills by engaging them in thoughtful political discussions on current news topics.

## 🔑 Key Features

- **AI-Powered Political Debates**: Engage in debates where the bot takes strong political positions on current news topics
- **Historical Figure Personas**: Debate against AI simulations of historical figures like Socrates, Churchill, MLK, and more
- **Fact-Checking**: Real-time verification of factual claims during debates using Perplexity AI
- **Gamified Experience**: Earn points, track stats, and climb the leaderboard as you improve your debate skills
- **Personalized Feedback**: Receive coach-like analysis of your debate performance
- **Email Summaries**: Get detailed debate summaries and performance analysis sent to your inbox
- **Customizable Difficulty**: Choose from beginner, intermediate, or advanced debate levels

## 🧠 Implementation Approach

EchoBreaker leverages several powerful AI technologies:

1. **Mistral AI**: Powers the core debate functionality, allowing the bot to take strong political positions and respond intelligently to user arguments
2. **News API**: Fetches current news articles to serve as debate topics
3. **Perplexity AI**: Provides real-time fact-checking of claims made during debates
4. **Discord.py**: Enables rich interactive experiences within Discord servers

The implementation follows a modular architecture:
- `agent.py`: Contains the core AI logic, including the MistralAgent, NewsAgent, FactChecker, and other components
- `bot.py`: Handles Discord interactions, commands, and the debate flow

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Discord Bot Token
- Mistral AI API Key
- News API Key
- Perplexity API Key (for fact-checking)
- SMTP Email credentials (optional, for email summaries)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/echobreaker.git
   cd echobreaker
   ```

2. **Create a virtual environment:**
   ```bash
   conda env create -f local_env.yml
   conda activate discord_bot
   ```

3. **Set up environment variables:**
   Create a `.env` file with the following:
   ```
   DISCORD_TOKEN=your_discord_token
   MISTRAL_API_KEY=your_mistral_api_key
   NEWS_API_KEY=your_news_api_key
   PERPLEXITY_API_KEY=your_perplexity_api_key
   CHANNEL_ID=your_discord_channel_id
   EMAIL_SMTP_SERVER=smtp.example.com
   EMAIL_SMTP_PORT=587
   EMAIL_SENDER=your_email@example.com
   EMAIL_PASSWORD=your_email_password
   ```

4. **Run the bot:**
   ```bash
   python bot.py
   ```

## 💬 Usage

### Starting a Debate

- `!debate [topic]` - Start a debate on a specific topic
- `!debate` - Start a debate on a random current news topic
- `!debate [level] [topic]` - Start a debate with a specific difficulty level
  - Example: `!debate advanced climate change`
- `!debate [figure] [level] [topic]` - Debate against a historical figure
  - Example: `!debate churchill advanced democracy`

### Historical Figures

- `!figures` - List available historical figures
- `!figure [name]` - View details about a specific figure
- `!customfigure [name]` - Create a custom historical figure to debate against

### Debate Management

- `!enddebate` - End your current debate session
- `!enddebate email` - End debate and receive a summary by email
- `!join @user` - Join another user's debate
- `!leave` - Leave a debate you've joined
- `!debates` - List active debates you can join

### Stats and Settings

- `!stats` - View your debate statistics
- `!leaderboard` - See top debaters
- `!levels` - View available debate difficulty levels
- `!email set youremail@example.com` - Register your email for summaries

## 🌟 Why EchoBreaker Is Useful

EchoBreaker serves multiple valuable purposes:

1. **Skill Development**: Helps users improve their critical thinking, argumentation, and persuasion skills
2. **Knowledge Expansion**: Exposes users to diverse political viewpoints and current events
3. **Safe Practice Environment**: Provides a space to practice debating controversial topics without real-world social consequences
4. **Educational Tool**: Serves as a teaching aid for debate classes, political science courses, and critical thinking education
5. **Fact-Checking Practice**: Teaches users to verify claims and distinguish between facts and opinions
6. **Historical Perspective**: Allows users to engage with the rhetorical styles and worldviews of important historical figures

## 📋 Future Improvements

- Multi-user debates with AI moderator
- Voice-based debates using Discord's voice channels
- Integration with educational platforms for classroom use
- Expanded fact-checking capabilities
- More sophisticated debate evaluation metrics
- Additional historical and contemporary personas

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.