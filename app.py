from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
import yt_dlp
import tempfile
import shutil

app = FastAPI()

def download_youtube_audio(youtube_url: str, output_dir: str) -> str | None:
    """
    Downloads a YouTube video's audio as MP3 and returns the file path.
    """
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
        print(f"Error downloading video: {str(e)}")
        return None

@app.post("/convert")
async def convert(data: dict, background_tasks: BackgroundTasks):
    """
    API endpoint to convert a YouTube video to MP3.
    """
    youtube_url = data.get("youtube_url")
    if not youtube_url:
        raise HTTPException(status_code=400, detail="No YouTube URL provided")

    temp_dir = tempfile.mkdtemp()
    try:
        mp3_file = download_youtube_audio(youtube_url, temp_dir)
        if not mp3_file:
            raise HTTPException(status_code=500, detail="Failed to download and convert video")

        background_tasks.add_task(shutil.rmtree, temp_dir)

        return FileResponse(
            path=mp3_file,
            filename=os.path.basename(mp3_file),
            media_type="audio/mpeg"
        )
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)