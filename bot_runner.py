import threading
from server import app
from bot import main

if __name__ == "__main__":
    # Run the bot in a background thread
    t = threading.Thread(target=main)
    t.start()

    # Run Flask web server (Render health check)
    app.run(host="0.0.0.0", port=10000)
