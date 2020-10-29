


import base64
import enum
import io
import itertools
import typing

import PIL
import PIL.Image
import PIL.ImageChops
import requests


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "ProfileImageType",

    "is_image_anonymous",
    "is_image_likely_identical",

    "detect_profile_image_type",
]


ANONYMOUS_AVATAR_BINARY_DATA = base64.b64decode("".join(
    ["iVBORw0KGgoAAAANSUhEUgAAAMAAAADACAMAAABlApw1AAAASFBMVEWGhobx8fHGxsabm5",
     "vNzc2/v7+NjY34+PiUlJTq6uqjo6Pb29uxsbGioqLU1NTj4+Pc3Ny4uLiqqqq3t7ewsLDp",
     "6empqani4uJPPisWAAADpUlEQVR42u2cCZakIAyGRYEAKlpr3/+mU1U93W9qumtRQ0jey3",
     "eC/JIVkKZRFEVRFEVRFEVRFEVRFEVRFEXBIQzOztHABRPn7PadJON3+Wb5PSYPQYL13vXw",
     "kIm9hvGJ9Z/YJNr8K3EQbf6VmaMj+RYWYNlJGCMsIu552d/CYhynxN/DCiY2bhQirCIyUd",
     "AZWEnsZNt/aS8YKAgb7OegYK3/c4kDv9H+iwJfVUCGzeSa9jtAYFcxAACFeoEccQRMoh2o",
     "Ylu0rQLcVYM6mcgCGlZwBH8SZC9AlSVAXYAaUeBQBVRIRBFXgKG2PwEySXIIX2llexC5D3",
     "WADm1Ld8AXQNtVZ3wBWXYIXGZL0lEYCuAlVwHqKN6XEEB57uFKCKBMQ20JAZS12JYQYFWA",
     "ClABmoWq1gHKsXiQXomLtBKUU3EoIYB0JDP49tMOxT2+gJlUQCs7ixaZaGh3tjx+EBBvbK",
     "EHAfVpK3opOxILQPch8gMC5DxEf0STJOcg/DCe6e3HXYJjBQGYS3CqYT/mElS6T53lpqC/",
     "UwFSLThVu3Z2EBzBiHFs69mPcOevpgNd6baHQeV7l0fBV/5Q9rgYXMJ3wu3fpIDJTxBOrP",
     "9/cV6Vi8y5YcOaO+wnVj8y+cUTZusbXhwXLcJpbNjh349l43zDkfDm0Znl+0vrGxJMy/uP",
     "3HD8eGZ+f/ANe8LhwZjQOxG/dN8COrl8txIxH0bfSCN0KQ3DOXWhURRFURRFed07pMG1Ns",
     "8x/jKemRjn2bZuSAyfGvLd0OYFM+U0t7vEpbnrdnblHvWUd1114/uN29NmribCjy3SEVO0",
     "+wrWW9TLEoZWA9q3v18HosNW7z6gEJHgDbFQ4uPT7RmNPRSnoAQK829XV8ok1o7I/EKr4F",
     "sgBVuCM0BMxDw/GyeoANrTQ9Teg32KM0aoBsYrYi1UZWskhB4qs+05vZru8+1GG3q8A7DA",
     "CXX/rf9G+B7YkFfk0zABI5aHcojAiqVlmZv9SxXws3+ZAs/Q/kWvMk7AkslLy/8r7/g6YM",
     "tbNXkAxryxfxcMZwHmdSqKwJqXgeyAOS8auxHYk+RVsAX1zIEAnjhRABE83qroZQiYRZaw",
     "d+I4ShEwCV+AR6+YRDkCfo2CPQgiyU1BD5cggCh+1gIrS4CTHMK3weB/+xMII8n2oJ8tXZ",
     "QmIIrOQVeC1Dbi93bCyhNgJWwmvh8EIJB/Z+NOooAgtRP94szvPHUZO2nbKc/6OStRgFUB",
     "LAT8AZ+XolMgM/v8AAAAAElFTkSuQmCC"]))
"""
This is the binary JPEG image of a default anonymous
avatar that Slack currently assigns to users who have not uploaded a custom
image to their profile yet. Although Slack uses default anonymous avatars of
several different colors, through heurististics we are able to detect
whether a profile contains an anonymous image.
"""

ANONYMOUS_AVATAR_IMAGE = PIL.Image.open(io.BytesIO(ANONYMOUS_AVATAR_BINARY_DATA))


# noinspection PyBroadException
def _request_image(image_url: str) -> typing.Optional[PIL.Image.Image]:
    data = None
    try:
        r = requests.get(image_url)
        if r.ok:
            data = r.content
    except:
        pass

    if data is None:
        return

    img = PIL.Image.open(io.BytesIO(data))

    return img


class ProfileImageType(enum.Enum):
    NONE = 'none'
    ANONYMOUS = 'anonymous'
    PROVISIONED = 'provisioned'
    CUSTOMIZED = 'customized'


def _quantize_color(img, color=None, distance=1):

    img = img.convert("RGB")

    if color is None:
        color = PIL.ImageColor.getcolor("white", "RGB")

    def pixdist(xcoord: int, ycoord: int):
        pixcolor = img.getpixel((xcoord, ycoord))
        return sum(map(abs, map(sum, zip(pixcolor, map(lambda v: -v, color)))))

    x = 0
    dx = 1
    while x < img.width:

        changed_pixels = 0

        y = 0
        dy = 1
        while y < img.height:
            if pixdist(x, y) > distance:
                break
            img.putpixel((x,y), color)
            changed_pixels += 1
            y += dy

        y = img.height - 1
        dy = -1
        while y >= 0:
            if pixdist(x, y) > distance:
                break
            img.putpixel((x,y), color)
            changed_pixels += 1
            y += dy

        if changed_pixels == 0:
            break

        x += dx

    x = img.width - 1
    dx = -1
    while x >= 0:

        changed_pixels = 0

        y = 0
        dy = 1
        while y < img.height:
            if pixdist(x, y) > distance:
                break
            img.putpixel((x,y), color)
            changed_pixels += 1
            y += dy

        y = img.height - 1
        dy = -1
        while y >= 0:
            if pixdist(x, y) > distance:
                break
            img.putpixel((x,y), color)
            changed_pixels += 1
            y += dy

        if changed_pixels == 0:
            break

        x += dx

    return img


def _trim_image(
        img: PIL.Image.Image,
        border_color: typing.Tuple[int] = None,
) -> PIL.Image.Image:

    if border_color is None:
        trimmed = img
        for xy in itertools.product(range(2), range(2)):
            trimmed = _trim_image(
                img=trimmed,
                border_color=img.getpixel(xy),
            )
        return trimmed

    bg = PIL.Image.new(img.mode, img.size, border_color)
    diff = PIL.ImageChops.difference(img, bg)
    bbox = diff.getbbox()

    if bbox:
        return img.crop(bbox)
    else:
        # found no content
        raise ValueError("cannot trim; image was empty")


def _resize_image_pair(
        img1: PIL.Image.Image,
        img2: PIL.Image.Image,
        trim1: bool = True,
        trim2: bool = True,
) -> typing.Tuple[PIL.Image.Image, PIL.Image.Image]:

    def _trim_helper(img):
        return _trim_image(_trim_image(
            _quantize_color(img, distance=15), # hardcoded threshold
            border_color=PIL.ImageColor.getcolor("white", "RGBA")))

    img1 = _trim_helper(img1) if trim1 else img1
    img2 = _trim_helper(img2) if trim2 else img2

    w = max(img1.width, img2.width)
    h = max(img1.height, img2.height)

    return img1.resize((w, h)), img2.resize((w, h))


def _is_image_empty(img, threshold=0, proportion=None):
    img = img.convert("L")

    pixels_total = img.width * img.height
    pixels_below_threshold = 0

    for x in range(img.width):
        for y in range(img.height):
            if img.getpixel((x,y)) > threshold:
                if proportion is None:
                    return False
            else:
                pixels_below_threshold += 1

    if proportion is None:
        return pixels_below_threshold == pixels_total

    proportion_below_threshold = (float(pixels_below_threshold)/float(pixels_total)) * 100.0

    return proportion_below_threshold >= proportion


def _binarize_image(
        img: PIL.Image.Image,
        threshold: float
) -> PIL.Image.Image:
    output = img.convert("L")
    for x in range(output.width):
        for y in range(output.height):
            output.putpixel(
                xy=(x, y),
                value=0 if output.getpixel((x,y)) < threshold else 255,
            )
    return output


def is_image_anonymous(img):
    try:
        img_comb = PIL.ImageChops.difference(ANONYMOUS_AVATAR_IMAGE, img)
    except:
        return False

    img_bin = _binarize_image(img=img_comb, threshold=45.0)

    return _is_image_empty(img_bin, threshold=30, proportion=99.9)


def is_image_likely_identical(img1, img2):

    img1_r, img2_r = _resize_image_pair(img1=img1, img2=img2)
    try:
        img_comb = PIL.ImageChops.difference(img1_r, img2_r)
    except:
        return False

    return _is_image_empty(img_comb, threshold=15, proportion=70.0)


# noinspection PyBroadException
def detect_profile_image_type(
        image_url: typing.Optional[str],
        directory_img: typing.Optional[typing.Union[bytes, str, PIL.Image.Image]] = None,
) -> ProfileImageType:

    if image_url is None or image_url == "":
        return ProfileImageType.NONE

    img = _request_image(image_url=image_url)

    if img.size == (0, 0):
        return ProfileImageType.NONE

    if is_image_anonymous(img):
        return ProfileImageType.ANONYMOUS

    if type(directory_img) is bytes:
        directory_img = PIL.Image.open(io.BytesIO(directory_img))

    if type(directory_img) is str:
        # could be an URL
        if "http" in directory_img:
            directory_img = _request_image(image_url=directory_img)
        else:
            # or base64 encoded image: TO implement
            raise NotImplementedError("only urls are supported at this time")

    try:
        if is_image_likely_identical(img1=img, img2=directory_img):
            return ProfileImageType.PROVISIONED
    except:
        pass

    return ProfileImageType.CUSTOMIZED
