from datetime import datetime
import pyautogui
import time
import keyboard
import cv2
import json
import requests
import pathlib
import pytesseract
import configparser

config = configparser.ConfigParser()
config.read("config.ini")

# game window title
WINDOW_TITLE = "PHANTASY STAR ONLINE 2 NEW GENESIS"

# colors (RGB)
FILLED_PIP_COLOR = (147, 103, 29)
EMPTY_PIP_COLOR = (119, 115, 101)
# coordinate of left edge of final pip (taking top-left of window to be (0, 0))
PIP_X, PIP_Y = (156, 260)
# turquoise
DEFAULT_SKY_COLOR = (2, 167, 231)
# lavender
CHANCE_SKY_COLOR = (213, 190, 217)
# dark blue
BURST_SKY_COLOR = (2, 6, 215)
# coordinate to check (taking top-left of window to be (0, 0))
SKY_X, SKY_Y = (738, 137)
# coordinates defining region for casino coin display
COINS_X, COINS_Y, COINS_WIDTH, COINS_HEIGHT = (680, 705, 70, 35)

# logging to Discord
WEBHOOK_URL = config.get("webhook", "webhook_url")

# image of the bottom of the wild indicator that the circle homes in on
# grayscale for performance
WILD_INDICATOR_IMAGE = cv2.imread("wild_indicator.png", cv2.IMREAD_GRAYSCALE)


# x, y = coordinates with top-left corner of screenshot being (0, 0)
def getPixelColor(x, y, screenshot):
    return screenshot.getpixel((x, y))[:3]


# alternative to using pyscreeze.pixelMatchesColor()
def colorMatchesColor(color_1, color_2, tolerance=0):
    r, g, b = color_1[:3]
    exR, exG, exB = color_2[:3]
    return (
        (abs(r - exR) <= tolerance)
        and (abs(g - exG) <= tolerance)
        and (abs(b - exB) <= tolerance)
    )


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


window = pyautogui.getWindowsWithTitle(WINDOW_TITLE)[0]
if not window:
    print("No windows with matching title found")
    quit()

# focus window
window.activate()
print("Starting script")
time.sleep(1)
# get window size (should be constant)
window_width, window_height = window.size
print(f"Window size: {window_width} x {window_height}")

# current state of Rappy Slots instance
# only save confirmed states (i.e., non-transitional states)
pip_state = "empty"
sky_state = "default"

# hold down Q to break out
while not keyboard.is_pressed("q"):
    # focus window
    window.activate()
    # get position of top-left corner of window
    window_left, window_top = window.topleft
    print(f"Window top-left corner: {window_left, window_top}")
    # get single screenshot of window
    screenshot = pyautogui.screenshot(
        region=(window_left, window_top, window_width, window_height),
    )
    casino_coin_display = screenshot.crop(
        (COINS_X, COINS_Y, COINS_X + COINS_WIDTH, COINS_Y + COINS_HEIGHT)
    )

    casino_coin_display.save("./casino.png")
    casino_coin_image_grayscale = cv2.imread("./casino.png", cv2.IMREAD_GRAYSCALE)
    # setting threshold value to 50 so we have bolder text
    # inverting image so we have dark text on light background
    # hopefully will reduce the number of times "4" is read as "6"
    ret_val, casino_coin_image_processed = cv2.threshold(
        casino_coin_image_grayscale, 50, 255, cv2.THRESH_BINARY_INV
    )
    # page segmentation mode 7 = "Treat the image as a single text line."
    # disable dictionaries
    # restrict text values to digits and comma
    casino_coin_display_text = pytesseract.image_to_string(
        casino_coin_image_processed,
        config="--psm 7 -c load_system_dawg=0 load_freq_dawg=0 "
        + "tessedit_char_whitelist=0123456789,",
    ).strip()
    print(casino_coin_display_text)
    pip_color = getPixelColor(PIP_X, PIP_Y, screenshot)
    print(f"Pip color: {pip_color}")
    sky_color = getPixelColor(SKY_X, SKY_Y, screenshot)
    print(f"Sky color: {sky_color}")

    if colorMatchesColor(pip_color, FILLED_PIP_COLOR, 10):
        pip_state = "filled"
    elif colorMatchesColor(pip_color, EMPTY_PIP_COLOR, 10):
        pip_state = "empty"

    if colorMatchesColor(sky_color, DEFAULT_SKY_COLOR, 10):
        if sky_state != "default":
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
            screenshot.save(
                "./detection_history/chance/"
                + f"chance_detected_{datetime.now():%Y%m%d_%H%M%S}.png"
            )
            payload = {
                "embeds": [
                    {
                        "color": 0xD5BED9,
                        "title": "Currently in PSE Chance state.",
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
            screenshot.save(
                "./detection_history/burst/"
                + f"burst_detected_{datetime.now():%Y%m%d_%H%M%S}.png"
            )
            payload = {
                "embeds": [
                    {
                        "color": 0x0206D7,
                        "title": "Currently in PSE Burst state.",
                        "footer": {"text": f"Coins: {casino_coin_display_text}"},
                    }
                ]
            }
            logToDiscord(payload)
        sky_state = "burst"

    if pip_state == "filled" and sky_state == "default":
        print("Sleeping for 3 seconds")
        time.sleep(3)

    print(f"{pip_state} {sky_state} {datetime.now():%H%M%S}")

    count = 0
    while (
        pip_state == "filled"
        and sky_state == "default"
        and not keyboard.is_pressed("q")
    ):
        screenshot = pyautogui.screenshot(
            region=(window_left, window_top, window_width, window_height),
        )
        # press enter when circle homes in on wild indicator
        if pyautogui.locate(
            WILD_INDICATOR_IMAGE,
            screenshot,
            grayscale=True,
            confidence=0.8,
        ):
            print(f"Wild indicator detected {datetime.now():%H%M%S}")
            # save screenshot containing wild indicator for review
            # press in time with the circle
            pyautogui.press("enter")
            pathlib.Path("./detection_history/wild").mkdir(parents=True, exist_ok=True)
            screenshot.save(
                "./detection_history/wild/"
                + f"wild_detected_{datetime.now():%Y%m%d_%H%M%S}.png"
            )
            print("Enter pressed, sleeping for 3 seconds")
            time.sleep(3)
            break
        else:
            print(f"Not yet {datetime.now():%H%M%S}")
            # failsafe in case bot is stuck in loop waiting for wild
            count += 1
            if count > 200:
                payload = {
                    "embeds": [{"color": 0xFF0000, "title": "Failsafe triggered."}]
                }
                logToDiscord(payload)
                print("Failsafe triggered")
                pyautogui.press("enter")
                print("Enter pressed, sleeping for 3 seconds")
                time.sleep(3)
                break

    pyautogui.press("enter")
    print("Enter pressed")
    time.sleep(1)
