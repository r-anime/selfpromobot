**This repo has been archived.** Functionality has been moved to [r-anime/modbot](https://github.com/r-anime/modbot).

# Self-Promotion checker bot

Python script that automatically detects and reports users that seem to be below the 10% self-promotion posts ratio. Built on [PRAW](https://github.com/praw-dev/praw).

## Prerequisites

Note: earlier versions may work fine; these are the lowest *tested* versions.

- Python 3.7
- Praw 6.0

## Usage

```bash
# install dependencies
pip install -r requirements.txt
# write your config
cp config.sample.ini config.ini && $EDITOR config.ini
# run the bot
python selfpromobot.py
```

## License

MIT &copy; 2018 The /r/anime mod team
