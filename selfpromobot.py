#!/usr/bin/env python3

import configparser
import praw
import json
import time
from collections import namedtuple

User = namedtuple("User", ["last_checked",
                           "selfpromo_posts",
                           "other_posts",
                           "selfpromo_comments",
                           "other_comments",
                           "previous_reports"])

def main(reddit, config, dry_run = False):
    """
    Main loop.

    :param reddit: the praw Reddit instance
    :param config: config options dict
    :param dry_run: if True, no report will be made
    """

    subreddit = config["subreddit"]
    posts_per_run = int(config["posts_per_run"])
    interval = int(config["interval"])

    sub = reddit.subreddit(subreddit)

    # Only check posts once
    checked = list()

    while True:
        for post in sub.new(limit = posts_per_run):
            if selfpromotion(post) and not post in checked:
                verify_ratio(reddit, config, post.author, dry_run = dry_run)
                checked.append(post)

        # Only remember the most recent posts, as the others won't flow back into /new
        checked = checked[-3 * posts_per_run:]

        time.sleep(interval)

def verify_ratio(reddit, config, user, dry_run = False):
    """
    Perform the post verification.
    This function reports if a user is above the self-promotion threshold.

    :param reddit: the praw Reddit instance
    :param config: config options dict
    :param user: the user whose ratio must be verified
    :param dry_run: if True, no report will be made
    """
    user = User(None, 0, 0, 0, 0, 0)
    pass

def selfpromotion(post):
    """
    Decide if a post is self-promotion.

    :param post: the post to check
    :return: True is post is self-promotion, false otherwise
    """
    pass



if __name__ == "__main__":
    c = configparser.ConfigParser()
    c.read("config.ini")

    reddit = praw.Reddit(**c["Auth"])
    config = c["Options"]

    main(reddit, config, dry_run = True)
