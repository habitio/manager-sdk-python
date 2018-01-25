from base.settings import settings
from base import app

if __name__ == "__main__":
    try:
        app.run(port=settings.port, host="0.0.0.0")
    except Exception:
        print("********* Unknown Error!!! ********")    
        raise
