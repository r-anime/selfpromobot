#!/usr/bin/env python3

import configparser
import praw
import json
import time

import logging

DEBUG = True

logging.basicConfig(format = '%(asctime)s | %(levelname)s | %(message)s',
                    datefmt = '%H:%M:%S')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)


def main(reddit, config, dry_run = False):
    '''
    Main loop.

    :param reddit: the praw Reddit instance
    :param config: config options dict
    :param dry_run: if True, no report will be made
    '''

    subreddit = reddit.subreddit(config['subreddit'])
    posts_per_run = int(config['posts_per_run'])
    interval = int(config['interval'])
    threshold = float(config['threshold'])

    # Only check posts once
    checked = list()

    logger.info(f'Running as {reddit.user.me().name} on subreddit {subreddit.display_name}')
    if dry_run:
        logger.warning('Running in dry run mode')

    while True:
        logger.debug(f'Checking for the {posts_per_run} most recent posts')
        for post in subreddit.new(limit = posts_per_run):
            if selfpromotion(post) and not post in checked:
                logger.info(f'Found self-promotion {post} by {post.author.name}')
                # Check the ratio once per self-promotion post
                ratio = check_ratio(reddit, config, post.author)
                if ratio > threshold:
                    if dry_run:
                        logger.info('Not reporting because running a dry run')
                    else:
                        logger.info(f'Reporting post (ratio: {ratio})')
                        post.report('Possible excessive self-promotion (ratio: {ratio})')
                checked.append(post)

        # Only remember the most recent posts, as the others won't flow back into /new
        checked = checked[-3 * posts_per_run:]

        time.sleep(interval)


def check_ratio(reddit, config, user):
    '''
    Perform the post verification.
    This function reports if a user is above the self-promotion threshold.

    :param reddit: the praw Reddit instance
    :param config: config options dict
    :param user: the user whose ratio must be verified
    :return: the user ratio
    '''
    history = check_history(reddit, config, user)

    ratio = history['selfpromo_posts'] / (history['selfpromo_posts'] + history['other_posts'] + history['other_comments'])

    logger.debug(f'User {user.name} has ratio {ratio}')
    return ratio


def _new_history():
    return {
            'last_checked': None,
            'selfpromo_posts': 0,
            'other_posts': 0,
            'selfpromo_comments': 0,
            'other_comments': 0,
            }

def check_history(reddit, config, user):
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

    # TODO -- reload known information about the user
    # For now, we read the history on each verification
    history = _new_history()

    last_check = history['last_checked']
    history['last_checked'] = time.time() # Record check time before verification
    ignored_items = 0 # Many posts on other subs can reduce accuracy

    for item in user.new(limit = max_history):
        # Early exit if history was already checked
        if last_check is not None and item.created_utc < last_check:
            break
        # Ignore content on other subreddits
        if item.subreddit != subreddit:
            ignored_items += 1
            continue

        if isinstance(item, praw.models.Submission):
            if selfpromotion(item):
                history['selfpromo_posts'] += 1
                #logger.warning(f'Found post that should have been already recorded (id={item.id})')
            else:
                history['other_posts'] += 1
        elif isinstance(item, praw.models.Comment):
            if item.submission.author == item.author and selfpromotion(item.submission):
                history['selfpromo_comments'] += 1
            else:
                history['other_comments'] += 1
        else:
            logger.error(f'Found unknown item in user history: {item}')

    logger.info(f'Checked history for user {user.name}, ignored {ignored_items} items')
    logger.debug(str(history))

    return history



def selfpromotion(post):
    '''
    Decide if a post is self-promotion.

    :param post: the post to check
    :return: True is post is self-promotion, false otherwise
    '''
    return post.link_flair_text == 'Fanart' and (post.is_original_content or not post.is_self)



if __name__ == '__main__':
    c = configparser.ConfigParser()
    c.read('config.ini')
    logger.debug('Loaded config.ini')

    reddit = praw.Reddit(**c['Auth'])
    config = c['Options']
    logger.debug(f'Found {len(config)} config options')

    main(reddit, config, dry_run = DEBUG)
