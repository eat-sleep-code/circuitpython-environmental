import time
import terminalio # fontio now?

from adafruit_dislay_text  import label

def WriteToDisplay(display, textToWrite, hold):
    font = terminalio.FONT
    color = 0x0000FF
    textArea = label.Label(font, text=textToWrite, color=color)
    textArea.x = 100
    textArea.y = 80
    display.show(textArea)
    time.sleep(hold)
    return True
