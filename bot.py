import configparser
import ctypes
import json
import pathlib
import time
from datetime import datetime as dt

import cv2
import keyboard
import numpy as np
import pytesseract
import requests
import win32con
import win32gui
from PIL import Image

config = configparser.ConfigParser()
config.read("config.ini")

# game window title
WINDOW_TITLE = "PHANTASY STAR ONLINE 2 NEW GENESIS"

# colors (RGB)
FILLED_PIP_COLOR = 147, 103, 29
EMPTY_PIP_COLOR = 119, 115, 101
# coordinate of left edge of final pip (taking top-left of window to be (0, 0))
PIP_X, PIP_Y = 156, 260
# turquoise
DEFAULT_SKY_COLOR = 2, 167, 231
# lavender
CHANCE_SKY_COLOR = 213, 190, 217
# dark blue
BURST_SKY_COLOR = 2, 6, 215
# coordinate to check (taking top-left of window to be (0, 0))
SKY_X, SKY_Y = 738, 137
# coordinates defining region for casino coin display
COINS_X, COINS_Y, COINS_WIDTH, COINS_HEIGHT = 680, 705, 70, 35

# logging to Discord
WEBHOOK_URL = config.get("webhook", "webhook_url")

# image of the bottom of the wild indicator that the circle homes in on
# grayscale for performance
# note: discrepancy between loading as grayscale vs converting from BGR to grayscale
# WILD_INDICATOR_IMAGE = cv2.imread("wild_indicator.png", cv2.IMREAD_GRAYSCALE)
# https://stackoverflow.com/questions/37203970/opencv-grayscale-mode-vs-gray-color-conversion
WILD_INDICATOR_IMAGE = cv2.cvtColor(
    cv2.imread("wild_indicator.png"), cv2.COLOR_BGR2GRAY
)
# offset assumes window top-left corner is (0, 0)
DETECTION_REGION_X, DETECTION_REGION_Y = (623, 338)
DETECTION_REGION_WIDTH, DETECTION_REGION_HEIGHT = (52, 24)


# https://github.com/NetEaseGame/ATX/blob/master/atx/drivers/windows.py
# https://msdn.microsoft.com/en-us/library/windows/desktop/dd183376(v=vs.85).aspx
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.wintypes.DWORD),
        ("biWidth", ctypes.wintypes.LONG),
        ("biHeight", ctypes.wintypes.LONG),
        ("biPlanes", ctypes.wintypes.WORD),
        ("biBitCount", ctypes.wintypes.WORD),
        ("biCompression", ctypes.wintypes.DWORD),
        ("biSizeImage", ctypes.wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.wintypes.LONG),
        ("biYPelsPerMeter", ctypes.wintypes.LONG),
        ("biClrUsed", ctypes.wintypes.DWORD),
        ("biClrImportant", ctypes.wintypes.DWORD),
    ]


# x, y = coordinates with top-left corner of screenshot being (0, 0)
# screenshot = RGB numpy array
# return RGB
def getPixelColor(x, y, screenshot):
    # ignore alpha channel
    return screenshot[y, x]


# alternative to using pyscreeze.pixelMatchesColor()
def colorMatchesColor(color_1, color_2, tolerance=0):
    # assume no alpha channel
    r, g, b = color_1
    exR, exG, exB = color_2
    return (
        (abs(r - exR) <= tolerance)
        and (abs(g - exG) <= tolerance)
        and (abs(b - exB) <= tolerance)
    )


def getCasinoCoinDisplayText(screenshot_array):
    casino_coin_display_array = screenshot_array[
        COINS_Y : COINS_Y + COINS_HEIGHT, COINS_X : COINS_X + COINS_WIDTH
    ]

    casino_coin_display_grayscale = cv2.cvtColor(
        casino_coin_display_array, cv2.COLOR_RGB2GRAY
    )
    # setting threshold value to 50 so we have bolder text
    # inverting image so we have dark text on light background
    # hopefully will reduce the number of times "4" is read as "6"
    ret_val, casino_coin_display_processed = cv2.threshold(
        casino_coin_display_grayscale, 80, 255, cv2.THRESH_BINARY_INV
    )

    # page segmentation mode 7 = "Treat the image as a single text line."
    casino_coin_display_text = pytesseract.image_to_string(
        casino_coin_display_processed,
        config="--psm 7",
    ).strip()
    # print(casino_coin_display_text)
    return casino_coin_display_text


def logToDiscord(payload):
    response = requests.post(
        WEBHOOK_URL,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    if response.status_code < 200 or response.status_code >= 300:
        print("Issue with logging to Discord")
    else:
        print("Logged to Discord")


hwnd = win32gui.FindWindow(None, WINDOW_TITLE)
print(hwnd)
if not hwnd:
    print("Error with finding NGS")
    quit()


window_left, window_top, window_right, window_bottom = win32gui.GetWindowRect(hwnd)
window_width, window_height = window_right - window_left, window_bottom - window_top


# returns an RGB array
# https://github.com/NetEaseGame/ATX/blob/master/atx/drivers/windows.py
# https://stackoverflow.com/questions/4589206/python-windows-7-screenshot-without-pil
# https://github.com/mhammond/pywin32/blob/73e253d5eba8d92fa9b6277e333da261e8c0c0d1/win32/Demos/print_desktop.py
# https://docs.microsoft.com/en-us/windows/win32/gdi/capturing-an-image
def screenshotWindow():
    # get the device context of the window
    hdcwin = win32gui.GetWindowDC(hwnd)
    # create a temporary device context
    hdcmem = win32gui.CreateCompatibleDC(hdcwin)
    # create a temporary bitmap
    # TODO: look into using CreateDIBSection() instead
    hbmp = win32gui.CreateCompatibleBitmap(hdcwin, window_width, window_height)
    # select bitmap for temporary device context
    win32gui.SelectObject(hdcmem, hbmp)
    # copy bits to temporary device context
    win32gui.BitBlt(
        hdcmem,
        0,
        0,
        window_width,
        window_height,
        hdcwin,
        0,
        0,
        win32con.SRCCOPY,
    )
    bmp = win32gui.GetObject(hbmp)

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = bmp.bmWidth
    bi.biHeight = bmp.bmHeight
    bi.biPlanes = bmp.bmPlanes
    bi.biBitCount = bmp.bmBitsPixel
    bi.biCompression = 0  # BI_RGB
    bi.biSizeImage = 0
    bi.biXPelsPerMeter = 0
    bi.biYPelsPerMeter = 0
    bi.biClrUsed = 0
    bi.biClrImportant = 0

    # calculate total size for bits
    size = (
        ((bmp.bmWidth * bmp.bmBitsPixel + bmp.bmBitsPixel - 1) // bmp.bmBitsPixel)
        * 4
        * bmp.bmHeight
    )
    buf = (ctypes.c_char * size)()

    # read bits into buffer
    ctypes.windll.gdi32.GetDIBits(
        hdcmem,
        hbmp.handle,
        0,
        bmp.bmHeight,
        buf,
        ctypes.byref(bi),
        win32con.DIB_RGB_COLORS,
    )
    # handle bottom-up DIB, and remove alpha channel
    screenshot_array = np.frombuffer(buf, dtype=np.uint8).reshape(
        bmp.bmHeight, bmp.bmWidth, 4
    )[::-1, :, 2::-1]

    # cleanup
    win32gui.DeleteObject(hbmp)
    win32gui.DeleteObject(hdcmem)
    win32gui.ReleaseDC(hwnd, hdcwin)

    return screenshot_array


# focus window
win32gui.SetForegroundWindow(hwnd)
print("Starting script")
time.sleep(1)

# current state of Rappy Slots instance
# only save confirmed states (i.e., non-transitional states)
pip_state = "empty"
sky_state = "default"

# hold down Q to break out
while not keyboard.is_pressed("q"):
    # focus window
    win32gui.SetForegroundWindow(hwnd)
    # get position of top-left corner of window
    window_left, window_top, window_right, window_bottom = win32gui.GetWindowRect(hwnd)
    print(f"Window top-left corner: {window_left, window_top}")
    print("Taking screenshot...")
    start_time = time.perf_counter()

    screenshot_array = screenshotWindow()

    print(f"Screenshot taken. Elapsed time: {(time.perf_counter() - start_time):.4f}")

    pip_color = getPixelColor(PIP_X, PIP_Y, screenshot_array)
    # print(f"Pip color: {pip_color}")
    sky_color = getPixelColor(SKY_X, SKY_Y, screenshot_array)
    # print(f"Sky color: {sky_color}")

    if colorMatchesColor(pip_color, FILLED_PIP_COLOR, 10):
        pip_state = "filled"
    elif colorMatchesColor(pip_color, EMPTY_PIP_COLOR, 10):
        if pip_state == "filled" and sky_state == "default":
            payload = {"embeds": [{"color": 0xFF0000, "title": "Missed circle."}]}
            logToDiscord(payload)
        pip_state = "empty"

    if colorMatchesColor(sky_color, DEFAULT_SKY_COLOR, 10):
        if sky_state != "default":
            casino_coin_display_text = getCasinoCoinDisplayText(screenshot_array)
            payload = {
                "embeds": [
                    {
                        "color": 0x02A7E7,
                        "title": "Returned to default state.",
                        "footer": {"text": f"Coins: {casino_coin_display_text}"},
                    }
                ]
            }
            logToDiscord(payload)
        sky_state = "default"
    elif colorMatchesColor(sky_color, CHANCE_SKY_COLOR, 10):
        print(f"Matched chance sky color of {CHANCE_SKY_COLOR} with {sky_color}")
        # before logging to Discord, check that we weren't recently in this state
        if sky_state != "chance":
            pathlib.Path("./detection_history/chance").mkdir(
                parents=True, exist_ok=True
            )
            Image.fromarray(screenshot_array).save(
                "./detection_history/chance/"
                + f"chance_detected_{dt.now():%Y%m%d_%H%M%S}.png"
            )
            casino_coin_display_text = getCasinoCoinDisplayText(screenshot_array)
            payload = {
                "embeds": [
                    {
                        "color": 0xD5BED9,
                        "title": "Rappy PSE Chance triggered.",
                        "footer": {"text": f"Coins: {casino_coin_display_text}"},
                    }
                ]
            }
            logToDiscord(payload)
        sky_state = "chance"
    elif colorMatchesColor(sky_color, BURST_SKY_COLOR, 10):
        print(f"Matched burst sky color of {BURST_SKY_COLOR} with {sky_color}")
        # before logging to Discord, check that we weren't recently in this state
        if sky_state != "burst":
            pathlib.Path("./detection_history/burst").mkdir(parents=True, exist_ok=True)
            Image.fromarray(screenshot_array).save(
                "./detection_history/burst/"
                + f"burst_detected_{dt.now():%Y%m%d_%H%M%S}.png"
            )
            casino_coin_display_text = getCasinoCoinDisplayText(screenshot_array)
            payload = {
                "embeds": [
                    {
                        "color": 0x0206D7,
                        "title": "Rappy PSE Burst triggered.",
                        "footer": {"text": f"Coins: {casino_coin_display_text}"},
                    }
                ]
            }
            logToDiscord(payload)
        else:
            pathlib.Path("./detection_history/burst").mkdir(parents=True, exist_ok=True)
            Image.fromarray(screenshot_array).save(
                "./detection_history/burst/"
                + f"burst_ongoing_{dt.now():%Y%m%d_%H%M%S}.png"
            )
        sky_state = "burst"

    if pip_state == "filled" and sky_state == "default":
        print("Sleeping for 3 seconds")
        time.sleep(3)

    print(f"{pip_state} {sky_state} {dt.now():%H%M%S}")

    count = 0
    while pip_state == "filled" and sky_state == "default":
        screenshot_array = screenshotWindow()
        region_screenshot_array = screenshot_array[
            DETECTION_REGION_Y : DETECTION_REGION_Y + DETECTION_REGION_HEIGHT,
            DETECTION_REGION_X : DETECTION_REGION_X + DETECTION_REGION_WIDTH,
        ]

        region_screenshot_array_grayscale = cv2.cvtColor(
            region_screenshot_array, cv2.COLOR_RGB2GRAY
        )

        # press enter when circle homes in on wild indicator
        confidence = 0.7
        # https://stackoverflow.com/questions/7670112/finding-a-subimage-inside-a-numpy-image/
        result = cv2.matchTemplate(
            region_screenshot_array_grayscale,
            WILD_INDICATOR_IMAGE,
            cv2.TM_CCOEFF_NORMED,
        )
        match_indices = np.arange(result.size)[(result > confidence).flatten()]
        matches = np.unravel_index(match_indices, result.shape)

        if len(matches[0]):
            print(f"Wild indicator detected {dt.now():%H%M%S}")
            # save screenshot containing wild indicator for review
            # press in time with the circle
            keyboard.press_and_release("enter")
            print("Enter pressed, sleeping for 4 seconds")
            print(f"Count: {count}")
            time.sleep(4)
            payload = {
                "embeds": [
                    {"color": 0x00FF00, "title": f"Wild detected. Count: {count}."}
                ]
            }
            logToDiscord(payload)
            pathlib.Path("./detection_history/wild").mkdir(parents=True, exist_ok=True)
            Image.fromarray(screenshot_array).save(
                "./detection_history/wild/"
                + f"wild_detected_{dt.now():%Y%m%d_%H%M%S}.png"
            )
            # Image.fromarray(region_screenshot_array).save("./region.png")
            break
        else:
            # print(f"Not yet {dt.now():%H%M%S}")
            # failsafe in case bot is stuck in loop waiting for wild
            count += 1
            if count > 400:
                payload = {
                    "embeds": [{"color": 0xFF0000, "title": "Failsafe triggered."}]
                }
                logToDiscord(payload)
                print("Failsafe triggered")
                keyboard.press_and_release("enter")
                print("Enter pressed, sleeping for 3 seconds")
                time.sleep(3)
                pathlib.Path("./detection_history/failsafe").mkdir(
                    parents=True, exist_ok=True
                )
                Image.fromarray(screenshot_array).save(
                    "./detection_history/failsafe/"
                    + f"failsafe_{dt.now():%Y%m%d_%H%M%S}.png"
                )
                break

    keyboard.press_and_release("enter")
    print("Enter pressed")
    time.sleep(1)
