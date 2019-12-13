import sys
import json
import threading
from time import sleep
from functools import wraps
from base.redis_db import get_redis

DEFAULT_THREAD_NAME = "CustomPoolThread"


class CustomPoolThread(threading.Thread):
    """ Thread executing tasks from a given tasks queue """
    def __init__(self, tasks, thread_num):
        super().__init__()
        self.killed = False
        self.daemon = True
        self.tasks = tasks
        self.thread_num = thread_num
        self.name = f"{DEFAULT_THREAD_NAME}-{thread_num}"
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
        self.lock.acquire()
        pool_queue = self.db.get_key('poolthread/queues/main-async')
        json_obj = {}
        if pool_queue:
            json_obj = pool_queue.pop(0)
            self.db.set_key('poolthread/queues/main-async', pool_queue)
        self.lock.release()
        if json_obj:
            print(f"found object {json_obj}")
            return json_obj
        else:
            print("sleeping for (%d)sec" % 5)
            sleep(5)

    def run(self):
        while True:
            # func, args, kargs = self.tasks.get()
            json_obj = self.get_function()
            print(f"TASKS: {self.tasks}")
            try:
                print("Trying to get obj")
                obj = json.loads(json_obj)
                print(f"OBJ: {obj}")
                _func = obj.get('func')
                _args = obj.get('args', [])
                _kwargs = obj.get('kwargs', {})
                if _func and _func in self.tasks:
                    print(f"function found: {_func}")
                    self.tasks[_func](*_args, **_kwargs)
                sleep(5)
            except Exception as e:
                # An exception happened in this thread
                print(e)
            # finally:
                # Mark this task as done, whether an exception happened or not
                # self.tasks.task_done()


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
            pool_queue = self.db.get_key('poolthread/queues/main-async')
            if not pool_queue:
                self.db.set_key('poolthread/queues/main-async', [value])
            else:
                pool_queue.append(value)
                self.db.set_key('poolthread/queues/main-async', [value])
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
        threads = [t for t in threading.enumerate() if DEFAULT_THREAD_NAME in t.name]
        if threads and hasattr(threads[0], 'register_task'):
            threads[0].register_task(self)
        return func

    return register_pool_task(func)


def default_task_name(func):
    return f"{func.__globals__['__name__']}.{func.__name__}"