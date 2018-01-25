from base import app 
from base.views import kickoff , shutdown
from base.settings import settings
import signal

def signal_handler(signal, frame):
    raise SystemExit

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    try:
        #Initial setup of Manager
        #kickoff()
        app.run()
    except SystemExit:
        #shutdown()
        print("\n Manager Aborted !!!")  
        exit()    
    except Exception:
        print("********* Unknown Error!!! ********")    
        raise