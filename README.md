# kyuu

Tested with Python 3.9.7, 1280 x 720 window dimensions, 60 FPS cap (should work fine with anything better than 30 FPS cap), and minimum graphics.

Provide a Discord webhook URL in `config.ini`.

On Windows, run a terminal (e.g., PowerShell) as administrator. Using the terminal, navigate to the script directory, then run this script with `python bot.py`.

To terminate the script, hold the Q key on your keyboard, or press Ctrl-C while your terminal is focused to raise a KeyboardInterrupt exception.

Dependencies:

```
pip install pyautogui
pip install Pillow
pip install opencv-python
pip install pytesseract
pip install requests
```