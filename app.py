import os
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
st.caption(
    "Upload a Tamil video → translate it to English → review the subtitles → "
    "burn them into the video."
)


@st.cache_resource
def load_whisper(model_name):
    return whisper.load_model(model_name)


def fmt_time(t):
    m = int(t // 60)
    s = int(t % 60)
    return f"{m:02d}:{s:02d}"


def to_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments):
    lines = []
    for i, seg in enumerate(segments, start=1):
        text = seg["text"].strip()
        if not text:
            continue
        lines.append(str(i))
        lines.append(
            f'{to_srt_time(seg["start"])} --> {to_srt_time(seg["end"])}'
        )
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def escape_subtitle_path(path):
    # FFmpeg subtitles filter escaping for temporary paths.
    return (
        str(path)
        .replace("\\", r"\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
    )


def burn_subtitles(input_path, srt_path, output_path, font_size):
    # Only subtitle appearance is changed from the original notebook:
    # small, bottom-center, movie-style.
    style = (
        f"FontName=Arial,"
        f"FontSize={font_size},"
        "PrimaryColour=&H00FFFFFF&,"
        "OutlineColour=&H00000000&,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=0,"
        "Alignment=2,"
        "MarginV=30"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf",
        f"subtitles={escape_subtitle_path(srt_path)}:"
        f"force_style='{style}'",
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


with st.sidebar:
    st.header("Settings")

    model_name = st.selectbox(
        "Whisper model",
        ["small", "medium"],
        index=0,
        help=(
            "Same OpenAI Whisper translation method as the original notebook. "
            "Medium gives the best balance of accuracy and speed."
        ),
    )

    font_size = st.slider(
        "Subtitle font size",
        min_value=10,
        max_value=20,
        value=13,
        step=1,
    )

    st.info(
        "Translation uses the original Whisper Tamil → English logic. "
        "Subtitles are small, white, bottom-centered, with a black outline."
    )


uploaded = st.file_uploader(
    "Upload a Tamil video",
    type=["mp4", "mov", "mkv", "avi", "m4v", "webm"],
)

if uploaded is None:
    st.markdown(
        """
### How it works

1. Upload your Tamil video.
2. Whisper translates Tamil → English.
3. Word-level timing keeps subtitles synchronized.
4. Review and correct the English subtitle text.
5. Burn the subtitles into the video.
6. Download the finished MP4 or SRT.
"""
    )
    st.stop()


work_dir = Path(tempfile.mkdtemp(prefix="tamil_subtitles_"))
input_path = work_dir / Path(uploaded.name).name
input_path.write_bytes(uploaded.getbuffer())

st.success(
    f"Uploaded: {uploaded.name} "
    f"({input_path.stat().st_size / 1_000_000:.1f} MB)"
)

if "segments" not in st.session_state:
    st.session_state.segments = None


# =========================================================
# TRANSLATION
# This section intentionally follows the original notebook.
# =========================================================
if st.button(
    "🎙️ Translate Tamil → English",
    type="primary",
    use_container_width=True,
):
    try:
        with st.status(
            "Preparing AI model and translating...",
            expanded=True,
        ) as status:

            st.write(f"Loading Whisper **{model_name}** model...")

            model = load_whisper(model_name)

            st.write(
                "Listening to the video and translating to English..."
            )

            # EXACT ORIGINAL NOTEBOOK TRANSLATION SETTINGS.
            result = model.transcribe(
                str(input_path),
                task="translate",
                language="ta",
                word_timestamps=True,
                verbose=False,
            )

            # EXACT ORIGINAL NOTEBOOK WORD-LEVEL TIMING LOGIC.
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

                segments.append(
                    {
                        "start": start,
                        "end": end,
                        "text": text,
                    }
                )

            # EXACT ORIGINAL NOTEBOOK SAFETY PASS.
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
        st.error("The translation step failed.")
        st.exception(e)
        st.stop()


segments = st.session_state.segments

if segments:
    st.divider()
    st.subheader("✏️ Review and correct the English subtitles")
    st.caption(
        "The translation is generated using the original notebook's Whisper "
        "logic. Correct any line here before burning it into the video."
    )

    edited = []

    for i, seg in enumerate(segments):
        c1, c2 = st.columns([1.15, 5])

        with c1:
            st.write(f"**{i + 1}**")
            st.caption(
                f"{fmt_time(seg['start'])} – {fmt_time(seg['end'])}"
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
                final_segments.append(
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": text.strip(),
                    }
                )

            srt_text = build_srt(final_segments)
            srt_path = work_dir / "subtitles.srt"
            srt_path.write_text(srt_text, encoding="utf-8")

            output_name = (
                f"{Path(uploaded.name).stem}_english_subs.mp4"
            )
            output_path = work_dir / output_name

            with st.status(
                "Burning subtitles onto the video...",
                expanded=True,
            ) as status:

                burn_subtitles(
                    input_path,
                    srt_path,
                    output_path,
                    font_size,
                )

                status.update(
                    label="Done — finished video is ready.",
                    state="complete",
                )

            st.session_state.output_bytes = output_path.read_bytes()
            st.session_state.output_name = output_name
            st.session_state.srt_bytes = srt_text.encode("utf-8")

        except Exception as e:
            st.error("FFmpeg failed while burning the subtitles.")
            st.exception(e)


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
