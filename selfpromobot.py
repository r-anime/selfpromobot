#!/usr/bin/env python3

import configparser
import praw
import json
import time
from datetime import datetime, timezone, timedelta

import logging

global DEBUG

logging.basicConfig(format = '%(asctime)s | %(levelname)s \t| %(message)s',
                    datefmt = '%H:%M:%S')
logger = logging.getLogger(__name__)


def main(reddit, config):
    '''
    Main loop.

    :param reddit: the praw Reddit instance
    :param config: config options dict
    '''

    subreddit = reddit.subreddit(config['subreddit'])
    posts_per_run = int(config['posts_per_run'])
    interval = int(config['interval'])

    # Only check posts once
    checked = list()

    logger.info(f'Running as {reddit.user.me().name} on subreddit {subreddit.display_name}')
    if DEBUG:
        logger.warning('Running in debug mode')

    while True:
        logger.debug(f'Checking for the {posts_per_run} most recent posts')
        for post in subreddit.new(limit = posts_per_run):
            if not post in checked:
                if is_selfpromotion(post):
                    logger.info(f'Found self-promotion {post} by {post.author.name}')
                    check_sp_ratio(reddit, config, post)
                if is_oc_fanart(post):
                    logger.info(f'Found OC fanart {post} by {post.author.name}')
                    check_fanart_frequency(reddit, config, post)
                if is_clip(post):
                    logger.info(f'Found clip {post} by {post.author.name}')
                    check_clip_frequency(reddit, config, post)
                checked.append(post)

        # Only remember the most recent posts, as the others won't flow back into /new
        checked = checked[-3 * posts_per_run:]

        time.sleep(interval)

def report(post, reason):
    if DEBUG:
        logger.info('  !-> Not reporting in debug mode')
    else:
        logger.info('  --> Reporting post')
        post.report(reason)


#####################################
# Self-promotion verification block #
#####################################

def check_sp_ratio(reddit, config, post):
    '''
    Perform the post verification.
    This function reports if a user is above the self-promotion threshold.

    :param reddit: the praw Reddit instance
    :param config: config options dict
    :param user: the user whose ratio must be verified
    '''
    threshold = float(config['threshold'])
    user = post.author

    history = read_history(reddit, config, user)

    ratio = history['selfpromo_posts'] / (history['selfpromo_posts'] + history['other_posts'] + history['other_comments'])
    ratio = round(ratio, 2)

    logger.debug(f'User {user.name} has ratio {ratio}')

    # Check the ratio once per self-promotion post
    logger.info(f'  Ratio: {ratio}')
    if ratio > threshold:
        report(post, f'Possible excessive self-promotion (ratio: {ratio})')

    logger.debug(f'Finished checking history of {post.author.name} for SP ratio')


def read_history(reddit, config, user):
    '''
    Read submitted content from user since last verification.
    Updates the history.

    :param reddit: the praw Reddit instance
    :param config: parsed config
    :param user: Redditor to verify
    :param history: data for already parsed posts
    :return: the updated history
    '''
    subreddit = reddit.subreddit(config['subreddit'])
    max_history = int(config['history'])

    history = {'selfpromo_posts': 0,
               'other_posts': 0,
               'selfpromo_comments': 0,
               'other_comments': 0}

    found_items = 0
    for item in user.new(limit = max_history):
        # Running as mod will return removed items - skip them
        if item.subreddit.display_name == config['subreddit'] and item.removed:
            continue
        else:
            found_items += 1

        if isinstance(item, praw.models.Submission):
            if is_selfpromotion(item):
                history['selfpromo_posts'] += 1
            else:
                history['other_posts'] += 1
        elif isinstance(item, praw.models.Comment):
            if item.is_submitter and is_selfpromotion(item.submission):
                history['selfpromo_comments'] += 1
            else:
                history['other_comments'] += 1
        else:
            logger.error(f'Found unknown item in user history: {item}')

    logger.info(f'Checked {found_items} items for user {user.name}')
    logger.debug(str(history))

    return history


def is_selfpromotion(post):
    '''
    Heuristically decide if a post is self-promotion.

    :param post: the post to check
    :return: True is post is self-promotion, false otherwise
    '''
    # Based on user flairing
    if post.is_original_content:
        return True
    if post.link_flair_text == 'Fanart' and not post.is_self:
        return True
    if post.link_flair_text == 'Question':
        return False
    if post.link_flair_text == 'News':
        return False
    if post.link_flair_text == 'Rewatch':
        return False
    if post.link_flair_text == 'Official Media':
        return False
    if post.link_flair_text == 'Clip':
        return False

    # Based on post title
    if '[oc]' in post.title.lower() or 'original' in post.title.lower():
        return True
    if 'made' in post.title.lower() or 'drew' in post.title.lower():
        return True

    # Based on url
    #if post.is_video or post.is_reddit_media_domain:
    #    return True

    if 'imgur.com' in post.url:
        return True
    if 'youtube.com' in post.url or 'youtu.be' in post.url:
        return True

    domains = ['deviantart.com', 'instagram.com', 'artstation.com']
    for domain in domains:
        if post.is_self and domain in post.selftext:
            return True
        elif domain in post.url:
            return True

    return False


##########################################
# OC fanart frequency verification block #
##########################################

def check_fanart_frequency(reddit, config, post):
    count = 0
    for submission in post.author.submissions.new():
        if submission.subreddit.display_name == config['subreddit'] and submission.removed:
            continue

        created_at = datetime.fromtimestamp(submission.created_utc, tz = timezone.utc)
        if datetime.now(timezone.utc) - created_at > timedelta(days = 7):
            break
        if is_oc_fanart(submission):
            count += 1
        if count > 1:
            report(post, f'Recent fanart (id: {submission.id})')

    logger.debug(f'Finished checking history of {post.author.name} for fanart frequency')

def is_oc_fanart(post):
    return post.subreddit.display_name == config['subreddit'] \
           and post.link_flair_text == 'Fanart' \
           and (post.is_original_content or not post.is_self)


#####################################
# Clip frequency verification block #
#####################################

def check_clip_frequency(reddit, config, post):
    count = 0
    for submission in post.author.submissions.new():
        if submission.subreddit.display_name == config['subreddit'] and submission.removed:
            continue

        created_at = datetime.fromtimestamp(submission.created_utc, tz = timezone.utc)
        if datetime.now(timezone.utc) - created_at > timedelta(days = 7):
            break
        if is_clip(submission):
            count += 1
        if count > 4:
            report(post, f'Too many clips submitted')

    logger.debug(f'Finished checking history of {post.author.name} for clip frequency')

def is_clip(post):
    return post.subreddit.display_name == config['subreddit'] \
           and post.link_flair_text == 'Clip'


#####################################

if __name__ == '__main__':
    c = configparser.ConfigParser()
    c.read('config.ini')
    logger.debug('Loaded config.ini')

    reddit = praw.Reddit(**c['Auth'])
    config = c['Options']
    logger.debug(f'Found {len(config)} config options')

    DEBUG = config.getboolean('debug', True)
    logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    main(reddit, config)
