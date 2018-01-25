from base import app
from base.settings import settings
from base.views import kickoff
import signal

def signal_handler(signal, frame):
    raise SystemExit

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    try:
        print("Before run ...")
        kickoff()
        app.run()
    except SystemExit:
        app.shutdown()
        print("\n Manager Aborted !!!")  
        exit()    
    except Exception:
        print("********* Unknown Error!!! ********")    
        raise

with app.app_context():
    print(current_app.name)
    # kickoff()



@app.teardown_appcontext
def teardown_app(exception):
    print("Initial setup of Manager ...")
    # kickoff()

        