from flask import Flask, current_app
from base import app
from base.settings import settings
import signal

def signal_handler(signal, frame):
    raise SystemExit

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    try:
        app.run()
    except SystemExit:
        app.shutdown()
        print("\n Manager Aborted !!!")  
        exit()    
    except Exception:
        print("********* Unknown Error!!! ********")    
        raise