"""
Contains code for getting data from Tumblr's API and parsing it.
"""

from bs4 import BeautifulSoup
from markdownify import markdownify


async def get_trail(post: dict, post_body: str = '') -> dict:
    trail = []

    # Custom handling for audio-only posts (type == 'audio'):
    # since these are not included in the reblog trail, we have to add
    # a little placeholder
    if post['type'] == 'audio':
        info = {
            "type": "audio",
            "content": f"{post['track_name']} (1 audio file attached)",
            "content_html": f"{post['track_name']} (1 audio file attached)",
            "images": [post['album_art']]
        }
        if 'reblogged_root_name' in post:
            info['blogname'] = post['reblogged_root_name']
        else:
            info['blogname'] = post['blog']['name']
        trail.append(info)

    # Custom handling for video-only posts (type == 'video'):
    # since these are not included in the reblog trail, we have to add
    # a little placeholder
    if post['type'] == 'video':
        info = {
            "type": "video",
            "content": "(video)",
            "content_html": "(video)",
            "video": {
                "url": post['video_url'],
                "height": post['thumbnail_height'],
                "width": post['thumbnail_width'],
            },
            "images": [post['thumbnail_url']]
        }
        if 'reblogged_root_name' in post:
            info['blogname'] = post['reblogged_root_name']
        else:
            info['blogname'] = post['blog']['name']
        trail.append(info)

    skip_placeholders = False
    if len(trail) + len(post['trail']) == 1:
        skip_placeholders = True

    for p in post['trail']:
        trail.append(await get_post_info(p, skip_placeholders=skip_placeholders))

    # Workaround for bug where reblogged root user is ignored and the second
    # reblogger appears as the OP of the first post.
    if 'reblogged_root_name' in post:
        trail[0]['blogname'] = post['reblogged_root_name']

    # Custom handling for image posts (type == 'photo'):
    # the image is not included in the first post in the trail, so we
    # have to add it manually
    if post['type'] == 'photo':
        trail[0]['images'] = [photo['original_size']['url'] for photo in post['photos']]
        images_include = ''
        for image in trail[0]['images']:
            images_include += f'<p><figure class="tmblr-full"><img src="{image}"></figure></p>'
        trail[0]['content_html'] = images_include + trail[0]['content_html']

    # Custom handling for asks (type == 'answer'):
    # the question is not included in the main content, so we have to
    # prepend it manually
    if post['type'] == 'answer':
        trail[0]['content'] = f'{post["asking_name"]} asked:' + "\n" + markdownify(post['question']).strip() + "\n\n" + trail[0]['content']
        trail[0]['content_html'] = f'<div class="question"><p class="question-header"><strong class="asking-name">{post["asking_name"]}</strong> asked:</p>\n' + post['question'] + '</div>\n' + trail[0]['content_html']

    if len(trail) == 1:
        if trail[0]['type'] == ['video']:
            trail[0]['content'] = ''

    return trail


async def get_post_info(post: dict, skip_placeholders: bool = False) -> dict:
    images = []
    soup = BeautifulSoup(post['content_raw'], 'html.parser')

    info = {
        "blogname": post['blog']['name'],
        "content_html": post['content']
    }

    # Handle video posts. Video posts are just text posts with a <video> tag embedded in a <figure>.
    if soup.find('video'):
        info['type'] = 'video'
        for fig in soup.findAll('figure'):
            if fig.video:
                info['video'] = {
                    "url": next(fig.video.children, None)['src'],
                    "width": fig['data-orig-width'],
                    "height": fig['data-orig-height']
                }
                info['video']['thumbnail'] = info['video']['url']\
                    .replace('.mp4', '_frame1.jpg')\
                    .replace('va.media.tumblr.com', '64.media.tumblr.com')\
                    .replace('ve.media.tumblr.com', '64.media.tumblr.com')

                fig.replaceWith('')
        images = [info['video']['thumbnail']]

    # Handle audio posts. Audio posts with text or multiple audio files are
    # just text posts with a <audio> tags.
    elif soup.find('audio'):
        info['type'] = 'audio'
        n_audios = len(soup.findAll('audio'))
        n = 0
        for tag in soup.findAll('audio'):
            if n == 0:
                tag.replaceWith(f'({n_audios} audio files attached) ')
            else:
                tag.replaceWith('')
            n += 1
    else:
        info['type'] = 'text'

    if not images:
        for image in soup.findAll('img'):
            images.append(image['src'])
            if not skip_placeholders:
                image.replaceWith('(image) ')
            else:
                image.replaceWith('')

    info['images'] = images

    content_html = str(soup)
    info['content'] = markdownify(content_html).strip()
    if not info['content']:
        if info['type'] == 'video':
            info['content'] = '(video)'
        elif info['type'] == 'audio':
            info['content'] = '(audio)'

    return info
