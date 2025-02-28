# Echobreaker

This Discord bot delivers news updates, paired with "hot takes" from various political perspectives, and allows users to engage in a debate with an AI.

## Features

* **Customizable News Topics (Optional):**
    * Users can specify a news topic they are interested in (e.g., "climate change," "economy," "foreign policy") using commands.
    * Alternatively, the bot can provide general political updates.
* **Hot Take Generation:**
    * Each news update is accompanied by a "hot take" generated from a randomly selected political perspective (e.g., conservative, liberal, libertarian, socialist).
* **Interactive Debate:**
    * Users can attempt to respectfully and persuasively argue the opposite position of the generated "hot take" using commands.
    * The AI (powered by Mistral) will evaluate the user's argument and provide feedback.

## Setting up the starter code

We'll be using Python, if you've got a good Python setup already, great! But make sure that it is at least Python version 3.12. If not, the easiest thing to do is to make sure you have at least 3GB free on your computer and then to head over to [miniconda install](https://docs.anaconda.com/miniconda/install/) and install the Python 3 version of Anaconda. It will work on any operating system.

After you have installed conda, close any open terminals you might have. Then open a terminal in the same folder as your `bot.py` file. Once in, run the following command

## 1. Create an environment with dependencies specified in env.yml:

    conda env create -f local_env.yml

## 2. Activate the new environment:

    conda activate discord_bot

This will install the required dependencies to start the project.

## Guide To The Starter Code

The starter code includes two files, `bot.py` and `agent.py`. Let's take a look at what this project already does.

To do this, run `python3 bot.py` and leave it running in your terminal. Next, go into our team’s channel `echobreaker` and try typing any message. You should see the bot respond in the same channel. The default behavior of the bot is, that any time it sees a message (from a user), it sends that message to our agent and sends back the response.

Let's take a deeper look into how this is done. In the `bot.py` file, scroll to the `on_message` function. This function is called every time a message is sent in your channel. Observe how `agent.run()` is called on the message content, and how the result of that message call is sent back to the user.

This agent is defined in the `agent.py` file. The `run()` function creates a simple LLM call with a system message defined at the top, and the user's message passed in. The response from the LLM is then returned.

Check out this finalized [weather agent bot](https://github.com/CS-153/weather-agent-template/blob/main/agent.py) to see a more detailed example.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone [repository URL]
    cd [repository directory]
    ```
2.  **Install dependencies:**
    * Follow the conda environment setup instructions above.
3.  **Create a Discord bot:**
    * Go to the Discord Developer Portal and create a new application.
    * Create a bot user for your application.
    * Copy the bot token.
4.  **Configure API keys:**
    * Obtain API keys for the News API and Mistral AI.
    * Set the API keys and Discord bot token as environment variables or in a `.env` file within your project directory.
5.  **Invite the bot to your server:**
    * Use the OAuth2 URL generator in the Discord Developer Portal to generate an invite link with the "bot" scope and appropriate permissions.
    * Paste the link into your browser and select the server to invite the bot to.
6.  **Run the bot:**
    ```bash
    python bot.py
    ```

## Usage

* **News Updates:**
    * `!news [topic]` : retrieves news on the specified topic. If no topic is provided, it returns general news.
* **Debate:**
    * After the bot provides a news update and hot take, you can reply to the bot's message with your argument. The bot will then analyze your argument and provide feedback.

## Debate Evaluation Criteria (Mistral AI)

The Mistral AI model will evaluate user arguments based on the following criteria:

* **Respectfulness:**
    * Arguments must be presented in a respectful and civil manner.
* **Persuasiveness:**
    * Arguments should be logical, well-supported, and address the core points of the "hot take."
* **Understanding of Opposing Viewpoint:**
    * The user must show they understand the viewpoint that they are arguing against.
* **Accuracy:**
    * The user should provide factual information.

## Future Improvements

* Implement user profiles and preference storage.
* Add more diverse political perspectives.
* Improve the accuracy and sophistication of the debate evaluation.
* Add the capability to have a continuous back and forth debate with the AI.
* Allow users to select the political perspective of the hot take.
* Add more discord commands for easier user interaction.
* implement a cooldown for the debate functionality.

## Troubleshooting

### `Exception: .env not found`!

If you’re seeing this error, it probably means that your terminal is not open in the right folder. Make sure that it is open inside the folder that contains `bot.py` and `.env`

## Contributing

Contributions are welcome! Please submit pull requests or open issues to suggest improvements or report bugs.