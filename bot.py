from io import BytesIO
import os
import random
import re
import requests
import requests.auth
import sys
import textwrap
import time
from urllib.request import urlopen, HTTPError

from PIL import Image, ImageFont, ImageDraw
from praw import Reddit
from imgurpython import ImgurClient

# Constants
TEXT_COLOR = (255, 255, 255)
SHADOW_COLOR = (0, 0, 0)
MAX_LETTERS_PER_LINE = 80
MAX_UPLOAD_TRIES = 20
FILENAME = 'gwcoep.jpg'

# Setting up various variables used for API access
IMGUR_ID = os.getenv('IMGUR_ID')
IMGUR_SECRET = os.getenv('IMGUR_SECRET')
REDDIT_ID = os.getenv('REDDIT_ID')
REDDIT_SECRET = os.getenv('REDDIT_SECRET')
REDDIT_USERNAME = os.getenv('REDDIT_USERNAME')
REDDIT_PASSWORD = os.getenv('REDDIT_PASSWORD')
REDDIT_USER_AGENT = 'script for /u/gwcoepbot to created /r/gwcoepbot content'
URI = 'http://127.0.0.1:65010/authorize_callback'

# Choose the font that will be used for the image
FONTS = os.listdir('fonts/')
FONT_FILE = 'fonts/' + random.choice(FONTS)

# Initialize the list of "naughty" words
with open('naughty-words.txt', 'r') as naughty_file:
    NAUGHTY_WORDS = set(naughty_file.read().split())

# Returns whether the string has a single word we consider "naughty"
def has_naughty(sentence):
    for word in sentence.split():
        if word.lower() in NAUGHTY_WORDS:
            return True
    return False

# Set up the Reddit instance
reddit = Reddit(client_id=REDDIT_ID,
                client_secret=REDDIT_SECRET,
                user_agent=REDDIT_USER_AGENT,
                username=REDDIT_USERNAME,
                password=REDDIT_PASSWORD)

# Go through the recent comments from /r/gonewild until we find one that's
# acceptable for our purposes
for gw_comment in reddit.subreddit('gonewild').comments():
    comment = gw_comment.body
    comment_url = gw_comment.permalink
    if len(comment.split()) > 2 and has_naughty(comment):
        # If the comment is at least 3 words long, and has a 'naughty' word,
        # we call that acceptable, and select that as our comment
        break

# Gets a recent image from /r/earthporn
for submission in reddit.subreddit('earthporn').new():
    image_title = submission.title
    image_post = submission.permalink
    image_url = submission.url
    # Sometimes imgur images are linked to without the ".jpg" file extension
    # This dumb kludge tries to fix that
    if image_url[-4:] != '.jpg':
        image_url += '.jpg'
    try:
        image = Image.open(BytesIO(urlopen(image_url).read()))
        # If the image was successfully opened, we exit out of the loop
        break
    except HTTPError:
        # We weren't able to open the image, continue through the loop to go
        # to the next image
        continue

# Loads the font and chooses an appropriate font size
image_width, image_height = image.size
font_size = image_width // 45
font = ImageFont.truetype(FONT_FILE, font_size)

# Breaks up the comment onto different lines
letters_per_line = MAX_LETTERS_PER_LINE
message = '\n'.join(textwrap.wrap(comment, letters_per_line))
msg_width, msg_height = font.getsize(message)
# Make sure the writing doesn't overflow the image
while msg_width > image_width and letters_per_line > 30:
    letters_per_line -= 1
    message = '\n'.join(textwrap.wrap(comment, letters_per_line))
    msg_width, msg_height = font.getsize(message)

# Draw the text centered onto the image
text_x = (image_width - msg_width) / 2
text_y = (image_height - msg_height) / 2
draw = ImageDraw.Draw(image)
# Draw the shadow of the text
draw.text((text_x + font_size // 10, text_y + font_size // 10), message,
          SHADOW_COLOR, font)
# Draw the actual text
draw.text((text_x, text_y), message, TEXT_COLOR, font)

# Save the image
image.save(FILENAME)

# Upload the image, trying again if need be
uploaded = False
tries = 0
while not uploaded:
    try:
        imgur = ImgurClient(IMGUR_ID, IMGUR_SECRET)
        uploaded_url = imgur.upload_from_path(FILENAME)['link']
        uploaded = True
    except:
        # Imgur's over capacity, so try again later
        tries += 1
        if tries == MAX_UPLOAD_TRIES:
            # If we've been trying too long, we give up
            sys.exit()
        time.sleep(30)

# Remove the "[width x height]" and "[OC]" tags from the image's title
image_title = re.subn(r'(\[.*?\]|\(.*?\))', '', image_title)[0]
# Remove excess spaces between words
image_title = ' '.join(image_title.split())
if len(image_title) == 0:
    # If we managed to delete the entire title, we just use the original
    # /r/earthporn submission title
    image_title = submission.title

# Finally, submit the image to reddit, and post a comment linking to the
# original sources
subreddit = reddit.subreddit('GWCOEPBot')
new_submission = subreddit.submit(title=image_title, url=uploaded_url)
credit = (f'[Original /r/earthporn post]({image_post})\n\n' +
          f'[Original /r/gonewild comment]({comment_url})')
new_submission.reply(credit)
