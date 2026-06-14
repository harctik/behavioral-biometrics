import os
from app.app_impl import create_app

# Set default FLASK_ENV if not present
env = os.environ.get("FLASK_ENV", "development")

# Create the flask app
app = create_app(env)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=(env == "development"))
