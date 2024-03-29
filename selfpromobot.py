#!/usr/bin/env python3

import configparser
import praw
import json
import time
from datetime import datetime, timezone, timedelta

import logging

global DEBUG

# logging.basicConfig(format = '%(asctime)s | %(levelname)s \t| %(message)s',
#                    datefmt = '%H:%M:%S')
logging.basicConfig(format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

REMOVAL_MESSAGE_TEMPLATE = """Sorry, your submission has been removed.\n\n{message}\n\n
*I am a bot, and this action was performed automatically. Please
[contact the moderators of this subreddit](https://www.reddit.com/message/compose/?to=/r/anime)
if you have any questions or concerns.*"""


def main(reddit, config):
    """
    Main loop.

    :param reddit: the praw Reddit instance
    :param config: config options dict
    """

    subreddit = reddit.subreddit(config["subreddit"])
    posts_per_run = int(config["posts_per_run"])
    interval = int(config["interval"])

    # Only check posts once
    checked = list()

    logger.info(f"Running as {reddit.user.me().name} on subreddit {subreddit.display_name}")
    if DEBUG:
        logger.warning("Running in debug mode")

    while True:
        logger.debug(f"Checking for the {posts_per_run} most recent posts")
        for post in subreddit.new(limit=posts_per_run):
            if not post in checked:
                # Note : only the first violation will be reported
                # Check fanart frequency
                if is_fanart(post):
                    logger.info(f"Found fanart {post} by {post.author.name}")
                    check_fanart_frequency(reddit, config, post)
                # Check self-promo ratio
                # if is_selfpromotion(post):
                #     logger.info(f'Found self-promotion {post} by {post.author.name}')
                #     check_sp_ratio(reddit, config, post)
                # Check clip frequency
                if is_clip(post):
                    logger.info(f"Found clip {post} by {post.author.name}")
                    check_clip_frequency(reddit, config, post)
                # Check video edit frequency
                if is_video_edit(post):
                    logger.info(f"Found video edit {post} by {post.author.name}")
                    check_video_edit_frequency(reddit, config, post)
                # Check video frequency
                if is_video(post):
                    logger.info(f"Found video {post} by {post.author.name}")
                    check_video_frequency(reddit, config, post)
                checked.append(post)

        # Only remember the most recent posts, as the others won't flow back into /new
        checked = checked[-3 * posts_per_run :]

        time.sleep(interval)


def report(post, reason):
    if DEBUG:
        logger.info("  !-> Not reporting in debug mode")
    else:
        logger.info("  --> Reporting post")
        post.report(reason)


def remove(post, reason, message=None):
    if DEBUG:
        logger.info("  !-> Not removing in debug mode")
    else:
        logger.info("  --> Removing post")
        if is_removed(post):
            logger.warning("  !-> Post already removed")
            return
        post.mod.remove(mod_note=reason)
        if message is not None:
            formatted_message = REMOVAL_MESSAGE_TEMPLATE.format(message=message)
            post.mod.send_removal_message(formatted_message)


def is_removed(item):
    return item.removed or item.banned_by is not None


#####################################
# Self-promotion verification block #
#####################################


def check_sp_ratio(reddit, config, post):
    """
    Perform the post verification.
    This function reports if a user is above the self-promotion threshold.

    :param reddit: the praw Reddit instance
    :param config: config options dict
    :param user: the user whose ratio must be verified
    """
    threshold = float(config["threshold"])
    user = post.author

    history = read_history(reddit, config, user)

    ratio = history["selfpromo_posts"] / (
        history["selfpromo_posts"] + history["other_posts"] + history["other_comments"]
    )
    ratio = round(ratio, 2)

    logger.debug(f"User {user.name} has ratio {ratio}")

    # Check the ratio once per self-promotion post
    logger.info(f"  Ratio: {ratio}")
    if ratio > threshold:
        report(post, f"Possible excessive self-promotion (ratio: {ratio})")

    logger.debug(f"Finished checking history of {post.author.name} for SP ratio")


def read_history(reddit, config, user):
    """
    Read submitted content from user since last verification.
    Updates the history.

    :param reddit: the praw Reddit instance
    :param config: parsed config
    :param user: Redditor to verify
    :param history: data for already parsed posts
    :return: the updated history
    """
    subreddit = reddit.subreddit(config["subreddit"])
    max_history = int(config["history"])

    history = {
        "selfpromo_posts": 0,
        "other_posts": 0,
        "selfpromo_comments": 0,
        "ignored_comments": 0,
        "other_comments": 0,
    }

    found_items = 0
    for item in user.new(limit=max_history):
        # Running as mod will return removed items - skip them
        if item.subreddit.display_name == config["subreddit"] and is_removed(item):
            continue
        else:
            found_items += 1

        if isinstance(item, praw.models.Submission):
            if is_selfpromotion(item):
                history["selfpromo_posts"] += 1
            else:
                history["other_posts"] += 1
        elif isinstance(item, praw.models.Comment):
            if item.is_submitter and is_selfpromotion(item.submission):
                history["ignored_comments"] += 1
            elif is_selfpromotion_comment(item):
                history["selfpromo_comments"] += 1
            else:
                history["other_comments"] += 1
        else:
            logger.error(f"Found unknown item in user history: {item}")

    logger.info(f"Checked {found_items} items for user {user.name}")
    logger.debug(str(history))

    return history


def is_selfpromotion(post):
    """
    Heuristically decide if a post is self-promotion.

    :param post: the post to check
    :return: True is post is self-promotion, false otherwise
    """
    # Based on user flairing
    if post.is_original_content:
        return True
    if post.link_flair_text == "OC Fanart":
        return True
    if post.link_flair_text == "Fanart" and not post.is_self:
        return True
    if post.link_flair_text == "Fanart Misc" and not post.is_self:
        return True
    if post.link_flair_text == "Question":
        return False
    if post.link_flair_text == "News":
        return False
    if post.link_flair_text == "Rewatch":
        return False
    if post.link_flair_text == "Official Media":
        return False
    if post.link_flair_text == "Clip":
        return False

    # Based on post title
    title = post.title.lower()
    if "[oc]" in title or "(oc)" in title or "original" in title:
        return True
    if "i made" in title or "i drew" in title or "my " in title:
        return True
    if "i tried" in title or "attempt" in title:
        return True
    if "sketch" in title or "drawing" in title:
        return True

    # Based on url
    if (post.is_video or post.is_reddit_media_domain) and post.subreddit.display_name == config["subreddit"]:
        return True

    if "imgur.com" in post.url:
        return True
    if "youtube.com" in post.url or "youtu.be" in post.url:
        return True

    domains = ["deviantart.com", "instagram.com", "artstation.com"]
    for domain in domains:
        if post.is_self and domain in post.selftext:
            return True
        elif domain in post.url:
            return True

    return False


def is_selfpromotion_comment(comment):
    domains = ["deviantart.com", "instagram.com", "artstation.com", "patreon.com", "pixiv.net"]
    for domain in domains:
        if domain in comment.body.lower():
            return True
    return False


##########################################
# OC fanart frequency verification block #
##########################################


def check_fanart_frequency(reddit, config, post):
    count = 0
    for submission in post.author.submissions.new():
        if submission.subreddit.display_name == config["subreddit"] and is_removed(submission):
            continue

        created_at = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
        if datetime.now(timezone.utc) - created_at > timedelta(days=6, hours=23, minutes=45):
            break
        if is_fanart(submission):
            count += 1
        if count > 2:
            remove(post, f"Recent fanart (id: {submission.id})", message="You may only submit two fanart posts in a 7-day period.")
            break

    logger.debug(f"Finished checking history of {post.author.name} for fanart frequency")


def is_fanart(post):
    return (
        post.subreddit.display_name == config["subreddit"]
        and post.link_flair_text == "Fanart"
    )


#####################################
# Clip frequency verification block #
#####################################


def check_clip_frequency(reddit, config, post):
    count = 0
    for submission in post.author.submissions.new():
        if submission.subreddit.display_name == config["subreddit"] and is_removed(submission):
            continue

        created_at = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
        if datetime.now(timezone.utc) - created_at > timedelta(days=29, hours=23, minutes=45):
            break
        if is_clip(submission):
            count += 1
        if count > 2:
            remove(post, f"Too many clips submitted", message="You may only submit two clips every 30 days.")
            break

    logger.debug(f"Finished checking history of {post.author.name} for clip frequency")


def is_clip(post):
    return post.subreddit.display_name == config["subreddit"] and post.link_flair_text == "Clip"


#####################################
# Video Edit frequency verification block #
#####################################


def check_video_edit_frequency(reddit, config, post):
    count = 0
    for submission in post.author.submissions.new():
        if submission.subreddit.display_name == config["subreddit"] and is_removed(submission):
            continue

        created_at = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
        if datetime.now(timezone.utc) - created_at > timedelta(days=29, hours=23, minutes=45):
            break
        if is_video_edit(submission):
            count += 1
        if count > 2:
            remove(post, f"Too many clips submitted", message="You may only submit two video edits every 30 days.")
            break

    logger.debug(f"Finished checking history of {post.author.name} for video edit frequency")


def is_video_edit(post):
    return post.subreddit.display_name == config["subreddit"] and post.link_flair_text == "Video Edit"


#####################################
# Video frequency verification block #
#####################################


def check_video_frequency(reddit, config, post):
    count = 0
    for submission in post.author.submissions.new():
        if submission.subreddit.display_name == config["subreddit"] and is_removed(submission):
            continue

        created_at = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
        if datetime.now(timezone.utc) - created_at > timedelta(days=6, hours=23, minutes=45):
            break
        if is_video(submission):
            count += 1
        if count > 2:
            remove(post, f"Too many videos submitted", message="You can only submit 2 videos at most every 7 days.")
            break

    logger.debug(f"Finished checking history of {post.author.name} for video frequency")


def is_video(post):
    return post.subreddit.display_name == config["subreddit"] and post.link_flair_text == "Video"


#####################################


def get_reddit_instance(config_dict: dict):
    """
    Initialize a reddit instance and return it.

    :param config_dict: dict containing necessary values for authenticating
    :return: reddit instance
    """

    auth_dict = {**config_dict}
    password = config_dict["password"]
    totp_secret = config_dict.get("totp_secret")

    if totp_secret:
        import mintotp

        auth_dict["password"] = f"{password}:{mintotp.totp(totp_secret)}"

    reddit_instance = praw.Reddit(**auth_dict)
    return reddit_instance


if __name__ == "__main__":
    c = configparser.ConfigParser()
    c.read("config.ini")
    logger.debug("Loaded config.ini")

    reddit = get_reddit_instance(c["Auth"])
    config = c["Options"]
    logger.debug(f"Found {len(config)} config options")

    DEBUG = config.getboolean("debug", True)
    logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    main(reddit, config)
