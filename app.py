from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import yt_dlp
import tempfile
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware to allow all origins (adjust for production if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (e.g., Postman, browsers); restrict in production
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

def download_youtube_audio(youtube_url: str, output_dir: str) -> str | None:
    """
    Downloads a YouTube video's audio as MP3 and returns the file path.
    """
    logger.info(f"Downloading audio from URL: {youtube_url}")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
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
    """
    API endpoint to convert a YouTube video to MP3.
    Accepts a JSON payload with 'youtube_url' and returns the MP3 file.
    """
    youtube_url = data.get("youtube_url")
    if not youtube_url:
        raise HTTPException(status_code=400, detail="No YouTube URL provided")

    # Validate YouTube URL (basic check)
    if not youtube_url.startswith("https://www.youtube.com/watch?v="):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL format")

    temp_dir = tempfile.mkdtemp()
    try:
        mp3_file = download_youtube_audio(youtube_url, temp_dir)
        if not mp3_file:
            raise HTTPException(status_code=500, detail="Failed to download and convert video")

        background_tasks.add_task(shutil.rmtree, temp_dir)

        logger.info(f"Successfully converted URL to MP3: {os.path.basename(mp3_file)}")
        return FileResponse(
            path=mp3_file,
            filename=os.path.basename(mp3_file),
            media_type="audio/mpeg"
        )
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Conversion error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
