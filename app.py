import os
import re
import subprocess
import tempfile
from pathlib import Path

import streamlit as st
import whisper

st.set_page_config(
    page_title="Tamil → English Subtitle Generator",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 Tamil Video → English Subtitles")
st.caption("Upload a Tamil video, translate the speech to English, review the subtitles, and burn them into the video.")

# ---------- Helpers ----------
@st.cache_resource
def load_whisper(model_name: str):
    return whisper.load_model(model_name)


def fmt_time(t):
    m = int(t // 60)
    s = int(t % 60)
    return f"{m:02d}:{s:02d}"


def to_srt_time(seconds):
    total_ms = max(0, int(round(seconds * 1000)))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def compact_subtitle(text, max_chars=42):
    """Keep subtitles compact, targeting a maximum of about two lines."""
    text = re.sub(r"\\s+", " ", text.strip())
    if len(text) <= max_chars:
        return text

    words = text.split()
    lines = ["", ""]
    for word in words:
        candidate = (lines[0] + " " + word).strip()
        if len(candidate) <= max_chars:
            lines[0] = candidate
        else:
            lines[1] = (lines[1] + " " + word).strip()

    if not lines[1]:
        return lines[0]
    return lines[0] + "\\n" + lines[1]


def build_srt(segments):
    lines = []
    for i, seg in enumerate(segments, start=1):
        text = compact_subtitle(seg["text"])
        if not text:
            continue
        lines.extend([
            str(i),
            f'{to_srt_time(seg["start"])} --> {to_srt_time(seg["end"])}',
            text,
            "",
        ])
    return "\n".join(lines)


def escape_subtitle_path(path):
    # ffmpeg's subtitles filter uses ':' as an option separator.
    # Escape characters that commonly matter in filter arguments.
    p = str(path).replace("\\", r"\\").replace(":", r"\:")
    p = p.replace("'", r"\'")
    return p


def burn_subtitles(input_path, srt_path, output_path, font_size):
    # Movie-style subtitles: small white text, bottom-center,
    # with a subtle semi-transparent black background.
    style = (
        f"FontName=Arial,"
        f"FontSize={font_size},"
        "PrimaryColour=&H00FFFFFF&,"
        "SecondaryColour=&H00FFFFFF&,"
        "OutlineColour=&H80000000&,"
        "BackColour=&H80000000&,"
        "BorderStyle=4,"
        "Outline=2,"
        "Shadow=0,"
        "Alignment=2,"
        "MarginL=70,"
        "MarginR=70,"
        "MarginV=45,"
        "Spacing=0,"
        "WrapStyle=2"
    )

    srt_filter_path = escape_subtitle_path(srt_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"subtitles={srt_filter_path}:force_style='{style}'",
        "-c:v", "libx264",
        "-crf", "22",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-4000:])


# ---------- Sidebar ----------
with st.sidebar:
    st.header("Settings")
    model_name = st.selectbox(
        "Whisper model",
        ["small", "medium", "large"],
        index=1,
        help="small = faster, medium = better balance, large = highest accuracy but needs much more RAM/CPU.",
    )
    font_size = st.slider(
        "Subtitle font size",
        min_value=10,
        max_value=30,
        value=13,
        step=1,
        help="Default is 14, reduced from the original notebook's 18.",
    )
    st.info("Movie-style subtitles: small white text, bottom-center, subtle black background, and kept away from faces. Video encoding uses a faster preset.")

# ---------- Upload ----------
uploaded = st.file_uploader(
    "Upload a Tamil video",
    type=["mp4", "mov", "mkv", "avi", "m4v", "webm"],
)

if uploaded is None:
    st.markdown("""
    ### How it works
    1. Upload your Tamil video.
    2. Whisper transcribes and translates Tamil → English.
    3. Review/edit every subtitle line.
    4. Burn the edited subtitles into the video.
    5. Download the finished MP4 and/or `.srt` file.
    """)
    st.stop()

# Save upload to a temporary directory for ffmpeg.
work_dir = Path(tempfile.mkdtemp(prefix="tamil_subs_"))
input_path = work_dir / Path(uploaded.name).name
input_path.write_bytes(uploaded.getbuffer())

st.success(f"Uploaded: {uploaded.name} ({input_path.stat().st_size / 1_000_000:.1f} MB)")

# ---------- Transcription ----------
if "segments" not in st.session_state:
    st.session_state.segments = None

if st.button("🎙️ Translate Tamil → English", type="primary", use_container_width=True):
    try:
        with st.status("Preparing AI model and translating...", expanded=True) as status:
            st.write(f"Loading Whisper **{model_name}** model...")
            model = load_whisper(model_name)

            st.write("Listening to the video and creating word-level timings...")
            result = model.transcribe(
                str(input_path),
                task="translate",
                language="ta",
                word_timestamps=True,
                verbose=False,
            )

            segments = []
            for s in result["segments"]:
                text = s["text"].strip()
                if not text:
                    continue

                words = s.get("words") or []
                if words:
                    start = words[0]["start"]
                    end = words[-1]["end"]
                else:
                    start, end = s["start"], s["end"]

                segments.append({
                    "start": float(start),
                    "end": float(end),
                    "text": text,
                })

            segments.sort(key=lambda x: x["start"])

            for i in range(len(segments) - 1):
                if segments[i]["end"] > segments[i + 1]["start"]:
                    segments[i]["end"] = segments[i + 1]["start"]
                if segments[i]["end"] <= segments[i]["start"]:
                    segments[i]["end"] = segments[i]["start"] + 0.3

            st.session_state.segments = segments
            st.session_state.edited_texts = [s["text"] for s in segments]
            status.update(label=f"Done — {len(segments)} subtitle lines created.", state="complete")

    except Exception as e:
        st.error(f"Translation failed: {e}")
        st.stop()

# ---------- Review ----------
segments = st.session_state.segments

if segments:
    st.divider()
    st.subheader("✏️ Review and edit subtitles")
    st.caption("Correct any translation mistakes below. The timings are automatically preserved.")

    edited = []
    for i, seg in enumerate(segments):
        c1, c2 = st.columns([1.2, 5])
        with c1:
            st.write(f"**{i + 1}**")
            st.caption(f"{fmt_time(seg['start'])} – {fmt_time(seg['end'])}")
        with c2:
            value = st.text_area(
                f"Subtitle {i + 1}",
                value=st.session_state.edited_texts[i],
                key=f"subtitle_{i}",
                label_visibility="collapsed",
                height=68,
            )
            edited.append(value)

    st.session_state.edited_texts = edited

    st.divider()
    st.subheader("🎞️ Create subtitled video")

    if st.button("🔥 Burn subtitles into video", type="primary", use_container_width=True):
        try:
            final_segments = []
            for seg, text in zip(segments, st.session_state.edited_texts):
                final_segments.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": text.strip(),
                })

            srt_text = build_srt(final_segments)
            srt_path = work_dir / "subtitles.srt"
            srt_path.write_text(srt_text, encoding="utf-8")

            output_name = f"{Path(uploaded.name).stem}_english_subs.mp4"
            output_path = work_dir / output_name

            with st.status("Burning subtitles into the video...", expanded=True) as status:
                burn_subtitles(input_path, srt_path, output_path, font_size)
                status.update(label="Finished — video is ready.", state="complete")

            st.session_state.output_bytes = output_path.read_bytes()
            st.session_state.output_name = output_name
            st.session_state.srt_bytes = srt_text.encode("utf-8")

        except Exception as e:
            st.error(f"FFmpeg failed: {e}")

# ---------- Downloads ----------
if "output_bytes" in st.session_state:
    st.divider()
    st.subheader("⬇️ Download")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "🎬 Download subtitled MP4",
            data=st.session_state.output_bytes,
            file_name=st.session_state.output_name,
            mime="video/mp4",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "📝 Download subtitles (.srt)",
            data=st.session_state.srt_bytes,
            file_name="subtitles.srt",
            mime="text/plain",
            use_container_width=True,
        )
