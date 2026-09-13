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

st.title("🎬 Tamil → English Subtitle Generator")
st.caption("Upload a Tamil video → translate it to English → review the translation → burn movie-style subtitles.")

# ---------------------------------------------------------
# Whisper: KEEP THE SAME TRANSLATION METHOD AS THE ORIGINAL
# NOTEBOOK. This is intentionally NOT a different translator.
# ---------------------------------------------------------
@st.cache_resource
def load_whisper(model_name):
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


def build_srt(segments):
    lines = []
    n = 1
    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue

        lines.extend([
            str(n),
            f'{to_srt_time(seg["start"])} --> {to_srt_time(seg["end"])}',
            text,
            "",
        ])
        n += 1

    return "\n".join(lines)


def escape_filter_path(path):
    p = str(path).replace("\\", r"\\")
    p = p.replace(":", r"\:")
    p = p.replace("'", r"\'")
    return p


def burn_subtitles(input_path, srt_path, output_path, font_size):
    # Movie-style: small white text, bottom center, subtle black box.
    # The subtitle size is intentionally much smaller than the original 18.
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
        "MarginL=60,"
        "MarginR=60,"
        "MarginV=45,"
        "Spacing=0,"
        "WrapStyle=2"
    )

    srt_filter_path = escape_filter_path(srt_path)

    # Faster than the original notebook while retaining good visual quality.
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
        raise RuntimeError(proc.stderr[-5000:])


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
with st.sidebar:
    st.header("Settings")

    model_name = st.selectbox(
        "Whisper model",
        ["small", "medium"],
        index=1,
        help="Uses the same OpenAI Whisper translation method as the original notebook. Medium gives better translation quality; small is faster.",
    )

    font_size = st.slider(
        "Subtitle font size",
        min_value=10,
        max_value=20,
        value=13,
        step=1,
    )

    st.info(
        "Translation uses Whisper's Tamil → English translation mode. "
        "Subtitles are small, white, bottom-centered and kept away from faces."
    )


# ---------------------------------------------------------
# Upload
# ---------------------------------------------------------
uploaded = st.file_uploader(
    "Upload a Tamil video",
    type=["mp4", "mov", "mkv", "avi", "m4v", "webm"],
)

if uploaded is None:
    st.markdown("""
### How it works

1. Upload your Tamil video.
2. Whisper translates Tamil → English using the **same translation approach as your original notebook**.
3. Word-level timing keeps subtitles synchronized.
4. Review and correct the English text.
5. Burn the subtitles into the video using a small movie-style subtitle format.
6. Download the MP4 and/or SRT.
""")
    st.stop()


# Keep uploaded video in a temp folder.
work_dir = Path(tempfile.mkdtemp(prefix="tamil_subtitles_"))
input_path = work_dir / Path(uploaded.name).name
input_path.write_bytes(uploaded.getbuffer())

st.success(
    f"Uploaded: {uploaded.name} "
    f"({input_path.stat().st_size / 1_000_000:.1f} MB)"
)

if "segments" not in st.session_state:
    st.session_state.segments = None


# ---------------------------------------------------------
# STEP 1: EXACT TRANSLATION LOGIC FROM ORIGINAL NOTEBOOK
# ---------------------------------------------------------
if st.button(
    "🎙️ Translate Tamil → English",
    type="primary",
    use_container_width=True,
):
    try:
        with st.status(
            "Translating Tamil → English...",
            expanded=True,
        ) as status:

            st.write(
                f"Loading Whisper **{model_name}** model..."
            )

            model = load_whisper(model_name)

            st.write(
                "Listening to the video and translating to English..."
            )

            # This mirrors the original notebook:
            # model.transcribe(INPUT_VIDEO,
            #                  task="translate",
            #                  language="ta",
            #                  word_timestamps=True)
            result = model.transcribe(
                str(input_path),
                task="translate",
                language="ta",
                word_timestamps=True,
                verbose=False,
            )

            # Same word-level timing logic as the original notebook.
            segments = []

            for s in result["segments"]:
                subtitle_text = s["text"].strip()

                if not subtitle_text:
                    continue

                words = s.get("words") or []

                if words:
                    start = words[0]["start"]
                    end = words[-1]["end"]
                else:
                    start = s["start"]
                    end = s["end"]

                segments.append({
                    "start": float(start),
                    "end": float(end),
                    "text": subtitle_text,
                })

            # Same safety pass as the original notebook.
            segments.sort(key=lambda x: x["start"])

            for i in range(len(segments) - 1):
                if segments[i]["end"] > segments[i + 1]["start"]:
                    segments[i]["end"] = segments[i + 1]["start"]

                if segments[i]["end"] <= segments[i]["start"]:
                    segments[i]["end"] = segments[i]["start"] + 0.3

            st.session_state.segments = segments
            st.session_state.edited_texts = [
                s["text"] for s in segments
            ]

            status.update(
                label=f"Translation complete — {len(segments)} subtitle lines.",
                state="complete",
            )

    except Exception as e:
        st.error(
            "Whisper translation failed. "
            "If you are using Streamlit Cloud, try the **small** model "
            "instead of medium if the server runs out of memory."
        )
        st.exception(e)
        st.stop()


# ---------------------------------------------------------
# STEP 2: REVIEW
# ---------------------------------------------------------
segments = st.session_state.segments

if segments:
    st.divider()
    st.subheader("✏️ Review the English translation")
    st.caption(
        "The English text comes directly from Whisper. "
        "You can correct wording without changing the timings."
    )

    edited = []

    for i, seg in enumerate(segments):
        c1, c2 = st.columns([1.15, 5])

        with c1:
            st.write(f"**{i + 1}**")
            st.caption(
                f"{fmt_time(seg['start'])} – "
                f"{fmt_time(seg['end'])}"
            )

        with c2:
            value = st.text_area(
                f"Subtitle {i + 1}",
                value=st.session_state.edited_texts[i],
                key=f"subtitle_{i}",
                label_visibility="collapsed",
                height=70,
            )
            edited.append(value)

    st.session_state.edited_texts = edited

    st.divider()
    st.subheader("🎬 Burn movie-style subtitles")

    if st.button(
        "🔥 Burn subtitles into video",
        type="primary",
        use_container_width=True,
    ):
        try:
            final_segments = []

            for seg, text in zip(
                segments,
                st.session_state.edited_texts,
            ):
                final_segments.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": text.strip(),
                })

            srt_text = build_srt(final_segments)

            srt_path = work_dir / "subtitles.srt"
            srt_path.write_text(
                srt_text,
                encoding="utf-8",
            )

            output_name = (
                f"{Path(uploaded.name).stem}_english_subs.mp4"
            )
            output_path = work_dir / output_name

            with st.status(
                "Burning subtitles into video...",
                expanded=True,
            ) as status:

                burn_subtitles(
                    input_path,
                    srt_path,
                    output_path,
                    font_size,
                )

                status.update(
                    label="Finished — video is ready.",
                    state="complete",
                )

            st.session_state.output_bytes = (
                output_path.read_bytes()
            )
            st.session_state.output_name = output_name
            st.session_state.srt_bytes = (
                srt_text.encode("utf-8")
            )

        except Exception as e:
            st.error("FFmpeg failed while burning the subtitles.")
            st.exception(e)


# ---------------------------------------------------------
# DOWNLOADS
# ---------------------------------------------------------
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
