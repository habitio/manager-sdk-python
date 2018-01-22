from bin.settings import settings
from os import path, remove
from datetime import datetime
import logging
import logging.handlers


log_levels = {
    "EMERGENCY" : ["\x1B[4;31m emergency \x1B[0m ",109],
    "ALERT" : ["\x1B[4;31m   alert   \x1B[0m ",108],
    "CRITICAL" : ["\x1B[4;35m critical  \x1B[0m ",107],
    "ERROR" : ["\x1B[4;35m   error   \x1B[0m ",106],
    "WARNING" : ["\x1B[4;35m  warning  \x1B[0m ",105],
    "NOTICE" : ["\x1B[4;36m  notice   \x1B[0m ",104],
    "INFO" : ["\x1B[4;37m   info    \x1B[0m ",103],
    "DEBUG" : ["\x1B[4;33m   debug   \x1B[0m ",102],
    "TRACE" : ["\x1B[4;32m   trace   \x1B[0m ",101],
    "VERBOSE" : ["\x1B[4;32m  verbose  \x1B[0m ",100]
}

for lvl in log_levels.keys():
    logging.addLevelName(log_levels[lvl][0], log_levels[lvl][1])

def verbose(self, message, *args, **kws):
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["VERBOSE"][1]):    
        self._log(log_levels["VERBOSE"][1], message, args, **kws) 
logging.Logger.verbose = verbose


def trace(self, message,*args, **kws):
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["TRACE"][1]):
        kws["exc_info"]=True    
        self._log(log_levels["TRACE"][1], message, args, **kws) 
logging.Logger.trace = trace


def debug(self, message, *args, **kws):
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["DEBUG"][1]):    
        self._log(log_levels["DEBUG"][1], message, args, **kws) 
logging.Logger.debug = debug


def info(self, message, *args, **kws):
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["INFO"][1]):    
        self._log(log_levels["INFO"][1], message, args, **kws) 
logging.Logger.info = info


def notice(self, message, *args, **kws):
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["NOTICE"][1]):    
        self._log(log_levels["NOTICE"][1], message, args, **kws) 
logging.Logger.notice = notice


def warning(self, message, *args, **kws):
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["WARNING"][1]):    
        self._log(log_levels["WARNING"][1], message, args, **kws) 
logging.Logger.warning = warning


def error(self, message, *args, **kws):
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["ERROR"][1]):    
        self._log(log_levels["ERROR"][1], message, args, **kws) 
logging.Logger.error = error


def critical(self, message, *args, **kws):
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["CRITICAL"][1]):    
        self._log(log_levels["CRITICAL"][1], message, args, **kws) 
logging.Logger.critical = critical


def alert(self, message, *args, **kws):
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["ALERT"][1]):    
        self._log(log_levels["ALERT"][1], message, args, **kws) 
logging.Logger.alert = alert


def emergency(self, message, *args, **kws):
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["EMERGENCY"][1]):    
        self._log(log_levels["EMERGENCY"][1], message, args, **kws) 
logging.Logger.emergency = emergency

# Configuring Logger for Manager
log_path = settings.log_path

#Transform level value to make it compatible with python"s standard logging package 
log_level = (100 + 9-int(settings.config_log["level"]))

if log_path == "python_logging.log":
    #remove("python_logging.log")
    pass

# Create the Handler for logging data to a file
if log_path == "/var/log/syslog" :
    logger_handler = logging.handlers.SysLogHandler(address = "/dev/log")
else :
    logger_handler = logging.FileHandler(log_path)

# Create a Formatter for formatting the log messages
logger_formatter = logging.Formatter( datetime.now().strftime("%b %d %H:%M:%S")+" "+settings.host_bind+" : %(levelname)s | \x1B[1;37m%(asctime)s\x1B[0m | %(message)s | %(processName)s:%(process)d %(filename)s:%(lineno)d ",
    datefmt="%Y-%m-%d %H:%M:%S")

# Adding Formatter to the Handler
logger_handler.setFormatter(logger_formatter)

# Setting Level to the handler
logger_handler.setLevel(log_level)