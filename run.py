from base.settings import settings
from base import app

if __name__ == "__main__":
    try:
        app.run()  
    except Exception:
        print("********* Unknown Error!!! ********")    
        raise
