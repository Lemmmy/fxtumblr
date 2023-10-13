"""
Contains code for post rendering functionality. See README.md for more info.
"""

from . import app
from .config import BASE_URL, config
from .npf import TumblrThread
from .tumblr import get_post
import shutil

browser = None

if config["renders_enable"]:
    from quart import render_template, send_from_directory
    import tempfile
    import pyppeteer

    RENDERS_PATH = config["renders_path"]

    # https://stackoverflow.com/questions/2632199/how-do-i-get-the-path-of-the-current-executed-file-in-python
    from inspect import getsourcefile
    import os.path

    FXTUMBLR_PATH = os.path.dirname(
        os.path.dirname(os.path.abspath(getsourcefile(lambda: 0)))
    )

    @app.before_serving
    async def setup_browser():
        global browser
        if not browser:
            browser = await pyppeteer.launch()
            # keep alive by leaving blank page open
            await browser.newPage()

    @app.route("/renders/<blogname>-<postid>.png")
    async def get_render(blogname, postid):
        if (
            not os.path.exists(os.path.join(RENDERS_PATH, f"{blogname}-{postid}.png"))
            or config["renders_debug"]
        ):
            post = get_post(blogname, postid)
            thread = TumblrThread.from_payload(post)
            await render_thread(thread)
        return await send_from_directory(RENDERS_PATH, f"{blogname}-{postid}.png")

    @app.route("/renders/<blogname>-<postid>.html")
    async def get_html_render(blogname, postid):
        if (
            not os.path.exists(os.path.join(RENDERS_PATH, f"{blogname}-{postid}.html"))
            or config["renders_debug"]
        ):
            post = get_post(blogname, postid)
            thread = TumblrThread.from_payload(post)
            await render_thread(thread)
        return await send_from_directory(RENDERS_PATH, f"{blogname}-{postid}.html")

    async def render_thread(thread: TumblrThread, force_new_render: bool = False):
        """
        Takes trail info from the generate_embed function and renders out
        the thread into a picture. Returns a URL to the generated image.
        """
        global browser
        target_filename = f"{thread.blog_name}-{thread.id}.png"

        if (
            config["renders_debug"]
            or force_new_render
            or not os.path.exists(os.path.join(RENDERS_PATH, target_filename))
        ):
            with tempfile.NamedTemporaryFile(suffix=".html") as target_html:
                target_html.write(
                    bytes(
                        await render_template(
                            "render.html", thread=thread, fxtumblr_path=FXTUMBLR_PATH
                        ),
                        "utf-8",
                    )
                )

                if config["renders_debug"]:
                    shutil.copyfile(target_html.name, "latest-render.html")

                shutil.copyfile(
                    target_html.name,
                    os.path.join(RENDERS_PATH, f"{thread.blog_name}-{thread.id}.html"),
                )

                page = await browser.newPage()
                await page.setViewport({"width": 560, "height": 300})
                await page.goto(f"file://{target_html.name}")
                await page.screenshot(
                    {
                        "path": os.path.join(RENDERS_PATH, target_filename),
                        "fullPage": True,
                        "omitBackground": True,
                    }
                )
                await page.close()

        return BASE_URL + f"/renders/{target_filename}"

else:

    async def render_thread(*args, **kwargs):
        return False
