from base.settings import settings
from base import app

print("-------------------------------------------------------------------------"+__name__)
if __name__ == "__main__":
    try:
        app.run()  
    except Exception:
        print("********* Unknown Error!!! ********")    
        raise
