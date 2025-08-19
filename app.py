import streamlit as st
import os
from moviepy.editor import ImageClip, AudioFileClip
from pydub import AudioSegment, effects
import tempfile

st.set_page_config(page_title="Image + Audio to Video", layout="centered")

st.title("🎬 Image + Audio to Video Maker")
st.write("Upload an image and an audio file, and we’ll create a video for you with enhanced audio quality.")

# File uploaders
image_file = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])
audio_file = st.file_uploader("Upload Audio", type=["mp3", "wav", "m4a"])

if image_file and audio_file:
    if st.button("✨ Make Video"):
        with st.spinner("Processing... Please wait..."):
            # Temporary files
            temp_dir = tempfile.mkdtemp()

            # Save uploaded image
            image_path = os.path.join(temp_dir, image_file.name)
            with open(image_path, "wb") as f:
                f.write(image_file.read())

            # Save uploaded audio
            audio_path = os.path.join(temp_dir, audio_file.name)
            with open(audio_path, "wb") as f:
                f.write(audio_file.read())

            # 🎵 Enhance audio quality
            audio = AudioSegment.from_file(audio_path)
            audio = audio.set_channels(1)  # mono
            audio = audio.set_frame_rate(44100)  # resample
            audio = effects.normalize(audio)  # normalize volume

            enhanced_audio_path = os.path.join(temp_dir, "enhanced_audio.wav")
            audio.export(enhanced_audio_path, format="wav")

            # 🎥 Create video
            audioclip = AudioFileClip(enhanced_audio_path)
            imageclip = ImageClip(image_path).set_duration(audioclip.duration)
            videoclip = imageclip.set_audio(audioclip)

            final_video_path = os.path.join(temp_dir, "final_video.mp4")
            videoclip.write_videofile(final_video_path, fps=24, codec="libx264", audio_codec="aac")

        st.success("✅ Video created successfully!")

        # Show video in app
        st.video(final_video_path)

        # Download button
        with open(final_video_path, "rb") as f:
            st.download_button("⬇️ Download Video", f, file_name="output_video.mp4", mime="video/mp4")
