import threading
import traceback
from base.settings import settings
from base import logger
import requests

class Watchdog:

    def __init__(self):
        self.interval = None
        try:
            self.interval = int(settings.config_boot['keep_alive'])
            logger.debug('watchdog interval {}'.format(self.interval))
        except (KeyError, TypeError, ValueError):
            logger.info('Watchdog not enabled, keep_alive missing')

    def start(self):
        if self.interval is not None and self.interval > 0:
            try:
                t = threading.Thread(target=self.send_notification, name="watchdog")
                t.start()
            except:
                logger.alert('Unexpected exception {}'.format(traceback.format_exc(limit=5)))
        logger.info('Watchdog not enabled')

    def send_notification(self):
        try:
            from systemd.daemon import notify
            event = threading.Event()

            while not event.wait(self.interval):
                main_thread_alive = threading.main_thread().is_alive()
                logger.debug('is alive {}'.format(main_thread_alive))
                if main_thread_alive:
                    logger.debug('watchdog...')
                    url = settings.config_http['bind']
                    resp = requests.get(url)
                    if resp.status_code == 200:
                        logger.debug('everything is ok')
                        notify('WATCHDOG=1')
        except (KeyError, TypeError, ValueError):
            logger.info('Watchdog not enabled, keep_alive missing')
        except ImportError:
            logger.warn('systemd not imported {}'.format(traceback.format_exc(limit=5)))
        except:
            logger.alert('Unexpected exception {}'.format(traceback.format_exc(limit=5)))
