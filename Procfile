# Procfile — Railway / Heroku-style process declaration.
# $PORT is injected by the platform; bind 0.0.0.0 so the container is reachable.
# Set GD_API_KEY (secret) and GD_ROOT_FOLDER (config) as platform variables;
# do NOT hard-code them here. The app starts and degrades gracefully if unset.
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
