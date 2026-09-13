# Tamil → English Subtitle Generator

Streamlit version of the original Tamil-to-English subtitle notebook.

The translation step intentionally uses the original notebook's OpenAI Whisper
logic: `task="translate"`, `language="ta"`, and `word_timestamps=True`.

Only the UI, review/edit step, subtitle appearance, and faster FFmpeg encoding
were changed.
