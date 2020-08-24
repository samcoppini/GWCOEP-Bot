#!/usr/bin/env python3

from io import BytesIO
import logging
import os
import random
import re
import sys
import textwrap
import time
from typing import Set, Tuple
from urllib.request import urlopen, HTTPError

from emoji import UNICODE_EMOJI
from imgur_python import Imgur
from PIL import Image, ImageDraw, ImageFont
from praw import Reddit

REDDIT_ID = os.getenv('REDDIT_ID')
REDDIT_SECRET = os.getenv('REDDIT_SECRET')
REDDIT_USERNAME = os.getenv('REDDIT_USERNAME')
REDDIT_PASSWORD = os.getenv('REDDIT_PASSWORD')
REDDIT_USER_AGENT = 'script for /u/gwcoepbot to created /r/gwcoepbot content'

IMGUR_ID = os.getenv('IMGUR_ID')
IMGUR_SECRET = os.getenv('IMGUR_SECRET')

IMAGES_SUBREDDIT = 'earthporn'
COMMENTS_SUBREDDIT = 'gonewild'
BOT_SUBREDDIT = 'GWCOEPBot'

IMAGE_EXTENSIONS = {'gif', 'jpg', 'jpeg', 'png', 'tiff', 'webp'}
FONT_FOLDER = 'fonts'
FONT_SIZE_FACTOR = 30
TEXT_COLOR = (255, 255, 255)
SHADOW_COLOR = (0, 0, 0)

IMAGE_FILENAME = 'gwcoep.jpg'
IMAGE_MODE = 'RGB'
IMAGE_TITLE = 'Submission for /r/GWCOEPBot'
IMAGE_DESCRIPTION = ''
MAX_IMAGE_UPLOAD_TRIES = 10
IMAGE_UPLOAD_WAIT_TIME = 30

COMMENT_MIN_WORDS = 3
COMMENT_MAX_WORDS = 30
MAX_WORD_LENGTH = 20
MAX_LETTERS_PER_LINE = 80
MIN_LETTERS_PER_LINE = 60
TEXT_MAX_SIZE = 0.8
NAUGHTY_WORDS_FILE = 'naughty-words.txt'


class ImageSubmission:
    def __init__(self, image: Image, title: str, link: str) -> None:
        self.image = image
        self.title = title
        self.link = link

    @property
    def width(self) -> int:
        return self.image.size[0]


class Comment:
    def __init__(self, text: str, link: str) -> None:
        self.text = text
        self.link = link


def get_text_size(text: str, font: ImageFont) -> Tuple[int, int]:
    width = 0
    height = 0

    for line in text.split('\n'):
        line_width, line_height = font.getsize(line)
        width = max(line_width, width)
        height += line_height

    return width, height

def get_font(font_size: int) -> ImageFont:
    font_file = random.choice(os.listdir(FONT_FOLDER))
    font_file = os.path.join(FONT_FOLDER, font_file)
    logging.info(f'Selecting {font_file} as the font')
    return ImageFont.truetype(font_file, font_size)


def adjust_image_url(filename: str) -> str:
    extension = filename.split('.')[-1]

    if extension not in IMAGE_EXTENSIONS:
        # Sometimes, images uploaded to imgur are not linked to directly.
        # In those cases, a lot of times we can merely add a 'jpg' extension
        # to the URL and have it just work.
        return filename + '.jpg'
    else:
        return filename


def get_image(reddit: Reddit) -> ImageSubmission:
    logging.debug('Selecting /r/earthporn submission...')

    for submission in reddit.subreddit(IMAGES_SUBREDDIT).new():
        image_url = adjust_image_url(submission.url)
        image_title = submission.title
        image_link = submission.permalink

        try:
            logging.debug(f'Opening "{image_url}"')
            image_bytes = BytesIO(urlopen(image_url).read())
            image = Image.open(image_bytes)
            image_width, image_height = image.size

            if image_height > image_width:
                logging.debug(f'Rejecting image for being more tall than wide')
                continue

            logging.info(f'Selecting {image_url} as image')
            return ImageSubmission(image, image_title, image_link)
        except HTTPError:
            logging.warn(f'Unable to open "{image_url}"')


def valid_comment(text: str, naughty_words: Set[str]) -> bool:
    words = text.split()

    if len(words) < COMMENT_MIN_WORDS:
        logging.debug(f'Rejecting "{text}". Reason: Too short')
        return False

    if len(words) > COMMENT_MAX_WORDS:
        logging.debug(f'Rejecting "{text}". Reason: Too long')
        return False

    if max(len(word) for word in words) > MAX_WORD_LENGTH:
        logging.debug(f'Rejecting "{text}". Reason: Too long word')
        return False

    if len(set(words) & naughty_words) == 0:
        logging.debug(f'Rejecting "{text}". Reason: No naughty words')
        return False

    if len(set(text) & set(UNICODE_EMOJI)) > 0:
        logging.debug(f'Rejecting "{text}". Reason: Contains emoji')
        return False

    return True


def get_comment(reddit: Reddit) -> Comment:
    with open(NAUGHTY_WORDS_FILE, 'r') as file:
        naughty_words = set(file.read().split())

    logging.debug(f'Selecting /r/gonewild comment...')

    for comment in reddit.subreddit(COMMENTS_SUBREDDIT).comments():
        if valid_comment(comment.body, naughty_words):
            logging.info(f'Selected "{comment.body}"')
            return Comment(comment.body, comment.permalink)


def format_comment(image: Image, font: ImageFont, comment: str) -> str:
    letters_per_line = MAX_LETTERS_PER_LINE
    formatted = '\n'.join(textwrap.wrap(comment, letters_per_line))
    image_width, image_height = image.size
    image_width *= TEXT_MAX_SIZE
    image_height *= TEXT_MAX_SIZE
    text_width, text_height = get_text_size(formatted, font)

    while text_width > image_width and letters_per_line >= MIN_LETTERS_PER_LINE:
        letters_per_line -= 1
        logging.debug(f'Decreasing letters per line to {letters_per_line}')
        formatted = '\n'.join(textwrap.wrap(comment, letters_per_line))
        text_width, text_height = get_text_size(formatted, font)

    if text_height > image_height or text_width > image_width:
        return None

    return formatted


def make_image(image: Image, font: ImageFont, comment: str, size: int) -> bool:
    formatted = format_comment(image, font, comment)

    if formatted is None:
        return False

    text_width, text_height = get_text_size(formatted, font)
    image_width, image_height = image.size

    # Figure out where to draw the text where it'll be centered
    text_x = (image_width - text_width) / 2
    text_y = (image_height - text_height) / 2

    logging.debug(f'Image dimensions: {image_width} x {image_height}')
    logging.debug(f'Text dimensions: {text_width} x {text_height}')
    logging.debug(f'Placing text at {text_x}, {text_y}')

    draw = ImageDraw.Draw(image)

    shadow_pos = (text_x + size / 10, text_y + size / 10)
    draw.text(shadow_pos, formatted, SHADOW_COLOR, font)
    draw.text((text_x, text_y), formatted, TEXT_COLOR, font)

    if not image.mode == IMAGE_MODE:
        logging.info(f'Converting image mode from {image.mode} to {IMAGE_MODE}')
        image.convert(IMAGE_MODE)

    image.save(IMAGE_FILENAME)

    logging.info(f'Saved file to "{IMAGE_FILENAME}".')

    return True


def upload_to_imgur(imgur: Imgur) -> str:
    tries = 0

    while tries < MAX_IMAGE_UPLOAD_TRIES:
        try:
            image = imgur.image_upload(os.path.realpath(IMAGE_FILENAME),
                                       IMAGE_TITLE,
                                       IMAGE_DESCRIPTION)
            url = image['response']['data']['link']
            logging.info(f'Uploaded image to {url}.')
            return url
        except Exception as ex:
            # Uploading images to imgur seems kinda flaky. So when it does fail,
            # we wait a little bit, then try again
            logging.warn(f'Encountered exception "{ex}" when uploading to imgur')
            tries += 1
            time.sleep(IMAGE_UPLOAD_WAIT_TIME)

    # If we reached here, we failed to upload to imgur too many times, so now
    # we're just giving up
    logging.error('Failed to upload too many times, giving up')
    sys.exit(1)


def make_title(orig_title: str) -> str:
    # Remove the "[width x height]" and "[OC]" tags from the image's title
    title = re.subn(r'(\[.*?\]|\(.*?\))', '', orig_title)[0]

    # Remove excess spaces
    title = ' '.join(title.split())

    # If we somehow managed to delete the entire title, return
    # the original title
    if len(title) == 0:
        return orig_title
    else:
        return title


def make_reddit_post(reddit: Reddit, comment: Comment,
                     image: ImageSubmission, url: str):
    title = make_title(image.title)
    subreddit = reddit.subreddit('GWCOEPBot')
    submission = subreddit.submit(title=title, url=url)
    logging.info(f'Created submission at {submission.permalink}.')

    credit = f'[Original /r/earthporn post]({image.link})\n\n'
    credit += f'[Original /r/gonewild comment]({comment.link})'
    comment = submission.reply(credit)

    logging.info(f'Added credit comment at {comment.permalink}')


def run_bot():
    reddit = Reddit(client_id=REDDIT_ID,
                    client_secret=REDDIT_SECRET,
                    user_agent=REDDIT_USER_AGENT,
                    username=REDDIT_USERNAME,
                    password=REDDIT_PASSWORD)

    image = get_image(reddit)
    font_size = image.width // FONT_SIZE_FACTOR
    font = get_font(font_size)
    comment = get_comment(reddit)

    while not make_image(image.image, font, comment.text, font_size):
        logging.debug("Comment can't fit, decreasing font size")
        font_size -= 1
        font = get_font(font_size)

    imgur = Imgur({'client_id': IMGUR_ID, 'access_token': IMGUR_SECRET})
    uploaded_url = adjust_image_url(upload_to_imgur(imgur))
    make_reddit_post(reddit, comment, image, uploaded_url)


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    run_bot()
