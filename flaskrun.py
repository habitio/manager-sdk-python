from base.settings import settings
from base import app

if __name__ == "__main__":
    try:
        #, host="0.0.0.0"
        app.run(port=settings.port)
    except Exception:
        print("********* Unknown Error!!! ********")    
        raise
