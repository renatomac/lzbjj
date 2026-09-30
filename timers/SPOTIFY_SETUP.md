# Spotify controls on the timer screen

The timer page always shows a Spotify section. Playback controls appear after the app has a Spotify client ID, client secret, and redirect URI, and the signed-in user connects an account. Until then the section explains why controls are unavailable.

Set these in the Django deployment settings from private environment variables (never commit the secret):

```python
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "")
```

Register the **exact same** redirect URI in the Spotify app configuration. It must point to the public `/timers/spotify/callback/` route, for example `https://your-domain.example/timers/spotify/callback/`. Restart the Django web app after updating its environment. Then open a timer's **Run** page and choose **Connect Spotify**. Playback requires an available Spotify device and an account eligible for Web API playback control.

The TV screen and Cast receiver are display routes. The per-user playback controls are on the timer **Run** page.
