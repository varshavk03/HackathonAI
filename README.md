# Tamil → English Subtitle Generator (Streamlit)

This app converts Tamil speech in a video into English subtitles using OpenAI Whisper, lets you edit the translated subtitle lines, and burns them into the video with FFmpeg.

## Run locally

You need Python 3.10+ and FFmpeg.

### Install FFmpeg

**Ubuntu/Debian**
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

**macOS (Homebrew)**
```bash
brew install ffmpeg
```

**Windows**
Install FFmpeg and make sure `ffmpeg` is available in PATH.

### Install Python packages
```bash
pip install -r requirements.txt
```

### Start the website
```bash
streamlit run app.py
```

Then open the URL Streamlit prints, usually:
`http://localhost:8501`

## Deploy as a public website

The easiest option is Streamlit Community Cloud:

1. Create a GitHub repository.
2. Upload `app.py` and `requirements.txt`.
3. Open Streamlit Community Cloud.
4. Select your GitHub repository and `app.py`.
5. Deploy.

### Important hosting note

Whisper + video encoding is CPU/RAM intensive. A hosted free-tier instance may be slow for large videos. For faster processing, use a machine/server with more CPU/RAM, or select the `small` Whisper model.

## Subtitle font

The app defaults to **font size 14**, reduced from the original notebook's 18. You can change it in the sidebar.


## Faster video rendering

The current version uses FFmpeg's `veryfast` H.264 preset and CRF 22. This is substantially faster than the previous `slow` + CRF 18 setting while still producing good quality for subtitle videos.

If you need it even faster, change:
```text
-preset veryfast
```
to:
```text
-preset ultrafast
```
This will encode faster but create a larger output file and may reduce compression efficiency.


## Deploy from your phone with Streamlit Community Cloud

1. Create/sign in to GitHub and create a new repository.
2. Upload these files from this project:
   - `app.py`
   - `requirements.txt`
   - `packages.txt`
3. Open Streamlit Community Cloud and connect your GitHub account.
4. Select the repository, branch, and `app.py`.
5. Deploy.
6. Streamlit will give you a web URL that you can open on your Android phone.

`packages.txt` tells the Linux hosting environment to install FFmpeg automatically.

### Recommended model
For cloud/phone use, start with **small** for faster processing. Use **medium** when translation accuracy is more important.


### Subtitle appearance

The output now uses a movie/reel-style subtitle treatment:
- Small white text
- Bottom-center placement
- Subtle semi-transparent black background
- Extra bottom margin so it stays away from faces
- Long subtitles are compacted to approximately two lines
