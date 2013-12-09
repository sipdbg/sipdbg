import sys
import logging

RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

def formatter_message(message, use_color = True):
    if use_color:
        message = message.replace("$RESET", RESET_SEQ).replace(
            "$BOLD", BOLD_SEQ)
    else:
        message = message.replace("$RESET", "").replace("$BOLD", "")
    return message

GREY, RED, GREEN, YELLOW , BLUE, PURPLE, AZUR, WHITE, BLACK = range (9)

COLORS = {
    'DEBUG'     : YELLOW,
    'INFO'      : GREEN,
    'WARNING'   : RED,
    'ERROR'     : BLACK,
    'CRITICAL'  : BLACK
}

class ColoredFormatter (logging.Formatter):
    def __init__ (self, msg, use_color = True):
        logging.Formatter.__init__ (self, msg)
        self.use_color = use_color

    def format (self, record):
        levelname = record.levelname
        if self.use_color and levelname in COLORS:
            levelname_color = COLOR_SEQ % (30 + COLORS [levelname]) + levelname [:1] + RESET_SEQ
            record.levelname = levelname_color
        return logging.Formatter.format (self, record)

class ColoredLogger (logging.Logger):
    FORMAT = "[%(levelname)s] %(message)s"
    COLOR_FORMAT = formatter_message (FORMAT, True)
    def __init__ (self, name):
        logging.Logger.__init__ (self, name, logging.INFO)
        color_formatter = ColoredFormatter (self.COLOR_FORMAT)
        console = logging.StreamHandler (sys.stdout)
        console.setFormatter (color_formatter)
        self.addHandler (console)
        return

if '__main__' == __name__:
    logging.setLoggerClass (ColoredLogger)
    logger = ColoredLogger ("MyTestLogger")
    logger.debug ("debugmsg")
    logger.info ("infomsg")
    logger.warn ("warnmsg")
    logger.error ("errormsg")
    # http://docs.python.org/2/library/logging.handlers.html#memoryhandler
