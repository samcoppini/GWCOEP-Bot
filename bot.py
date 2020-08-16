#!/usr/bin/env python3

from io import BytesIO
import logging
import os
from typing import Set
from urllib.request import urlopen, HTTPError

from PIL import Image
from praw import Reddit

REDDIT_ID = os.getenv('REDDIT_ID')
REDDIT_SECRET = os.getenv('REDDIT_SECRET')
REDDIT_USERNAME = os.getenv('REDDIT_USERNAME')
REDDIT_PASSWORD = os.getenv('REDDIT_PASSWORD')
REDDIT_USER_AGENT = 'script for /u/gwcoepbot to created /r/gwcoepbot content'

IMAGES_SUBREDDIT = 'earthporn'
IMAGE_EXTENSIONS = {'gif', 'jpg', 'jpeg', 'png', 'tiff', 'webp'}


class ImageSubmission:
    def __init__(self, image: Image, title: str, link: str):
        self.image = image
        self.title = title
        self.link = link


def adjust_image_url(filename: str) -> str:
    extension = filename.split('.')[-1]

    if extension not in IMAGE_EXTENSIONS:
        # Sometimes, images uploaded to imgur are not linked to directly.
        # In those cases, a lot of times we can merely add a 'jpg' extension
        # to the URL and have it just work.
        return filename + '.jpg'
    else:
        return filename


def get_earthporn_image(reddit: Reddit) -> ImageSubmission:
    for submission in reddit.subreddit(IMAGES_SUBREDDIT).new():
        image_url = adjust_image_url(submission.url)
        image_title = submission.title
        image_link = submission.permalink

        try:
            logging.debug(f'Opening "{image_url}"')
            image_bytes = BytesIO(urlopen(image_url).read())
            image = Image.open(image_bytes)
            logging.info(f'Selecting {image_url} as image')
            return ImageSubmission(image, image_title, image_link)
        except HTTPError:
            logging.warn(f'Unable to open "{image_url}"')


def run_bot():
    reddit = Reddit(client_id=REDDIT_ID,
                    client_secret=REDDIT_SECRET,
                    user_agent=REDDIT_USER_AGENT,
                    username=REDDIT_USERNAME,
                    password=REDDIT_PASSWORD)

    image = get_earthporn_image(reddit)


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    run_bot()
