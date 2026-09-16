import importlib.util
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_FILE = os.path.join(BASE_DIR, "app.py")

spec = importlib.util.spec_from_file_location("canteen_app", APP_FILE)
canteen_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canteen_app)

app = canteen_app.app


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )