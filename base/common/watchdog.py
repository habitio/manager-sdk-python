import threading
import traceback
import logging
import requests

from base import settings

logger = logging.getLogger(__name__)


class Watchdog:

    def __init__(self):
        self.interval = None
        self.thread = None
        try:
            self.interval = int(settings.config_boot['keep_alive'])
            logger.debug('[Watchdog] interval {}'.format(self.interval))
        except (KeyError, TypeError, ValueError):
            logger.info('[Watchdog] not enabled, keep_alive missing')

    def start(self):
        if self.interval is not None and self.interval > 0:
            try:
                self.thread = threading.Thread(target=self.send_notification, name="watchdog")
                self.thread.start()
            except:
                logger.alert('[Watchdog] Unexpected exception {}'.format(traceback.format_exc(limit=5)))
        else:
            logger.info('[Watchdog] not enabled, keep_alive missing or 0')

    def send_notification(self):
        try:
            from systemd.daemon import notify
            event = threading.Event()

            # send first notification on init
            logger.debug('[Watchdog]... everything is ok')
            notify('WATCHDOG=1')

            while not event.wait(self.interval - 1):
                main_thread_alive = threading.main_thread().is_alive()
                logger.debug('[Watchdog] is alive {}'.format(main_thread_alive))
                if main_thread_alive:
                    logger.debug('[Watchdog]...')
                    url = settings.config_http['bind']
                    resp = requests.get(url)
                    if resp.status_code == 200:
                        logger.debug('[Watchdog] everything is ok')
                        notify('WATCHDOG=1')
        except (KeyError, TypeError, ValueError):
            logger.info('[Watchdog] not enabled, keep_alive missing')
        except ImportError:
            logger.warn('[Watchdog] systemd not imported {}'.format(traceback.format_exc(limit=5)))
        except:
            logger.alert('[Watchdog] Unexpected exception {}'.format(traceback.format_exc(limit=5)))
