from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import yt_dlp
import tempfile
import shutil
import logging
import json
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import google.auth.transport.requests
from google.oauth2.credentials import Credentials

# 🔹 Allow OAuth without HTTPS (for local testing)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (for dev, restrict in production)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

# OAuth Config
CLIENT_SECRETS_FILE = "client_secret.json"  # Ensure this exists on Railway
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
REDIRECT_URI = "https://youtubeapi-production-0740.up.railway.app/oauth2callback"

# Store OAuth Tokens
TOKEN_FILE = "token.json"

def load_oauth_credentials():
    """Load stored OAuth credentials or None if not available."""
    if os.path.exists(TOKEN_FILE):
        return Credentials.from_authorized_user_file(TOKEN_FILE)
    return None

def save_oauth_credentials(credentials):
    """Save OAuth credentials to a file for reuse."""
    with open(TOKEN_FILE, "w") as token_file:
        token_file.write(credentials.to_json())

@app.get("/login")
async def oauth_login():
    """Redirect user to Google OAuth 2.0 login for YouTube API access."""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(prompt='consent')
    return RedirectResponse(auth_url)

@app.get('/oauth2callback')
async def oauth2callback(request: Request):
    """Handle Google OAuth 2.0 callback and save credentials."""
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        flow.fetch_token(authorization_response=str(request.url))
        credentials = flow.credentials
        save_oauth_credentials(credentials)
        return {"message": "OAuth authentication successful! You can now download YouTube audio."}
    except Exception as e:
        logger.error(f"OAuth Callback Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OAuth Callback Error: {str(e)}")

def download_youtube_audio(youtube_url: str, output_dir: str) -> str | None:
    """
    Downloads a YouTube video's audio as MP3 using OAuth.
    """
    logger.info(f"Downloading audio from URL: {youtube_url}")
    credentials = load_oauth_credentials()

    if not credentials:
        raise HTTPException(status_code=401, detail="OAuth credentials not found. Please authenticate.")

    # Normalize YouTube URL
    if "?si=" in youtube_url:
        youtube_url = youtube_url.split("?si=")[0]
        logger.info(f"Normalized URL to: {youtube_url}")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "source_address": "0.0.0.0",
        "nocheckcertificate": True,  # Avoid SSL certificate issues
        "cookiesfrombrowser": None,  # Ensure yt-dlp does NOT use cookies
        "force_generic_extractor": True,  # ✅ Forces OAuth for authentication
        "usenetrc": False,  # ✅ Ensures it does NOT fallback to local auth
        "username": None,  # ✅ Remove any username-based auth
        "oauth_token": credentials.token,  # ✅ Force OAuth for yt-dlp
        "oauth_headers": {"Authorization": f"Bearer {credentials.token}"},  # ✅ Required OAuth headers
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(youtube_url, download=True)
            for file in os.listdir(output_dir):
                if file.endswith(".mp3"):
                    return os.path.join(output_dir, file)
            return None
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        return None

@app.post("/convert")
async def convert(data: dict, background_tasks: BackgroundTasks):
    """API endpoint to convert a YouTube video to MP3."""
    youtube_url = data.get("youtube_url")
    if not youtube_url:
        raise HTTPException(status_code=400, detail="No YouTube URL provided")

    temp_dir = tempfile.mkdtemp()
    try:
        mp3_file = download_youtube_audio(youtube_url, temp_dir)
        if not mp3_file:
            raise HTTPException(status_code=500, detail="Failed to download and convert video")

        background_tasks.add_task(shutil.rmtree, temp_dir)
        return FileResponse(path=mp3_file, filename=os.path.basename(mp3_file), media_type="audio/mpeg")
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Conversion error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)


