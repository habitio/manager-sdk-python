import sys
import json
import threading
import traceback
from time import sleep
from functools import wraps
from base import logger, settings
from base.redis_db import get_redis
from base.constants import DEFAULT_THREAD_POOL_NAME, DEFAULT_THREAD_KEY_NAME, DEFAULT_SLEEP_TIME

SLEEP_TIME = settings.config_thread_pool.get('sleep_time', DEFAULT_SLEEP_TIME)
THREAD_NAME = settings.config_thread_pool.get('thread_name', DEFAULT_THREAD_POOL_NAME)
KEY_NAME = f"{DEFAULT_THREAD_KEY_NAME}{THREAD_NAME.lower()}"


class CustomPoolThread(threading.Thread):
    """ Thread executing tasks from a given tasks queue """
    def __init__(self, tasks, thread_num):
        super().__init__()
        self.killed = False
        self.daemon = True
        self.tasks = tasks
        self.thread_num = thread_num
        self.name = f"{THREAD_NAME}-{thread_num}"
        self.lock = threading.Lock()
        self.db = get_redis()

    def start(self):
        self.__run_backup = self.run
        self.run = self.__run
        super().start()

    def __run(self):
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, event, arg):
        if event == 'call':
            return self.localtrace
        else:
            return None

    def localtrace(self, frame, event, arg):
        if self.killed:
            if event == 'line':
                raise SystemExit()
        return self.localtrace

    def kill(self):
        self.killed = True

    def register_task(self, func):
        self.tasks.update({
            default_task_name(func): func
        })

    def get_function(self):
        json_obj = {}
        self.lock.acquire()
        pool_queue = self.db.get_key(KEY_NAME)
        if pool_queue:
            json_obj = pool_queue.pop(0)
            self.db.set_key(KEY_NAME, pool_queue)
        self.lock.release()

        return json_obj

    def run(self):
        while True:
            json_obj = self.get_function()
            try:
                obj = json.loads(json_obj)
                logger.debug(f"Found object to be executed: {obj}")
                _func = obj.get('func')
                _args = obj.get('args', [])
                _kwargs = obj.get('kwargs', {})
                if _func and _func in self.tasks:
                    logger.debug(f"Running function {_func} with args: {_args}; kwargs: {_kwargs}")
                    self.tasks[_func](*_args, **_kwargs)
                sleep(SLEEP_TIME)
            except TypeError:
                sleep(SLEEP_TIME)
            except Exception:
                logger.error(f"Unexpected error on thread pool: {traceback.format_exc(limit=5)}")


class ThreadPool:
    """ Pool of threads consuming tasks from a queue """
    def __init__(self, num_threads: int):
        self._tasks = {}
        self.num_threads = num_threads
        self._threads = []
        self.lock = threading.Lock()
        self.db = get_redis()

    @property
    def tasks(self):
        return self._tasks

    @property
    def threads(self):
        return self._threads

    def start(self):
        self.kill_threads()
        for num in range(self.num_threads):
            cpt = CustomPoolThread(self.tasks, num)
            cpt.start()
            self.threads.append(cpt)

    def kill_threads(self):
        for t in self.threads:
            t.kill()
            t.join()

    def register_task(self, func):
        self.tasks.update({
            default_task_name(func): func
        })

    def add_task(self, func, attrs=None, *args, **kwargs):
        attrs = attrs or []
        if type(attrs) is not list:
            attrs = [attrs]
        attrs.extend(args)
        task_name = default_task_name(func)
        if task_name in self.tasks:
            func_obj = {
                'func': task_name,
                'args': attrs,
                'kwargs': kwargs
            }
            self.lock.acquire()
            value = json.dumps(func_obj)
            pool_queue = self.db.get_key(KEY_NAME)
            if not pool_queue:
                self.db.set_key(KEY_NAME, [value])
            else:
                pool_queue.append(value)
                self.db.set_key(KEY_NAME, [value])
            self.lock.release()

    def map(self, func, args_list):
        """ Add a list of tasks to the queue """
        for args in args_list:
            self.add_task(func, args)

    def wait_completion(self):
        """ Wait for completion of all the tasks in the queue """
        self.tasks.join()


def pool_task(func):
    @wraps(func)
    def register_pool_task(self) -> func:
        thread_name = settings.config_thread_pool.get('thread_name', DEFAULT_THREAD_POOL_NAME)
        threads = [t for t in threading.enumerate() if thread_name in t.name]
        if threads and hasattr(threads[0], 'register_task'):
            threads[0].register_task(self)
        return func

    return register_pool_task(func)


def default_task_name(func):
    return f"{func.__globals__['__name__']}.{func.__name__}"
