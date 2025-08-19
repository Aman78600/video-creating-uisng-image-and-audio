import streamlit as st
import os
import tempfile
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
from io import BytesIO
import time

# Check if required packages are installed, if not, install them
try:
    import moviepy.editor as mpy
except ImportError:
    st.error("MoviePy not found. Please install it with: pip install moviepy")
    st.stop()

try:
    from pydub import AudioSegment
    from pydub.effects import normalize
except ImportError:
    st.error("Pydub not found. Please install it with: pip install pydub")
    st.stop()

# Set page configuration
st.set_page_config(
    page_title="Offline Video Creator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Check if FFmpeg is available
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

if not check_ffmpeg():
    st.error("FFmpeg is not installed or not found in PATH. Please install FFmpeg to use this application.")
    st.info("You can download FFmpeg from: https://ffmpeg.org/download.html")
    st.stop()

# Create temporary directory for processing
@st.cache_resource
def create_temp_dir():
    return tempfile.mkdtemp()

temp_dir = create_temp_dir()

# App title and description
st.title("🎬 Offline Video Creator")
st.markdown("Create videos by combining images and audio - completely offline!")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    
    # Transition effects
    transition_options = ["None", "Fade", "Slide", "Zoom"]
    selected_transition = st.selectbox("Transition Effect", transition_options)
    
    # Video templates
    template_options = ["Slideshow", "Single Image", "Ken Burns Effect"]
    selected_template = st.selectbox("Video Template", template_options)
    
    # Image editing options
    st.subheader("Image Editing")
    brightness = st.slider("Brightness", 0.5, 1.5, 1.0)
    contrast = st.slider("Contrast", 0.5, 1.5, 1.0)
    saturation = st.slider("Saturation", 0.5, 1.5, 1.0)

# Main content area
tab1, tab2, tab3 = st.tabs(["Upload Media", "Edit & Process", "Preview & Export"])

with tab1:
    st.header("Upload Media")
    
    # Image upload
    uploaded_images = st.file_uploader(
        "Upload Images", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    
    # Display uploaded images
    if uploaded_images:
        st.subheader("Uploaded Images")
        cols = st.columns(min(4, len(uploaded_images)))
        for idx, img in enumerate(uploaded_images):
            with cols[idx % 4]:
                st.image(img, use_column_width=True)
                st.caption(f"Image {idx+1}")
    
    # Audio upload
    uploaded_audio = st.file_uploader(
        "Upload Audio File", 
        type=["mp3", "wav", "ogg", "m4a"]
    )
    
    # Display audio info if uploaded
    if uploaded_audio:
        st.subheader("Audio File")
        st.audio(uploaded_audio)
        
        # Load audio to get duration
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
            tmp_audio.write(uploaded_audio.read())
            audio_path = tmp_audio.name
        
        try:
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000  # Convert to seconds
            st.info(f"Audio duration: {duration:.2f} seconds")
            
            # Audio trimming sliders
            st.subheader("Audio Trimming")
            start_time = st.slider("Start Time (seconds)", 0.0, duration, 0.0)
            end_time = st.slider("End Time (seconds)", 0.0, duration, duration)
            
        except Exception as e:
            st.error(f"Error loading audio: {e}")

with tab2:
    st.header("Edit & Process")
    
    if not uploaded_images or not uploaded_audio:
        st.warning("Please upload both images and audio to continue.")
    else:
        # Process images with editing options
        processed_images = []
        
        with st.spinner("Processing images..."):
            for idx, img_file in enumerate(uploaded_images):
                img = Image.open(img_file)
                
                # Apply image enhancements
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(brightness)
                
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(contrast)
                
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(saturation)
                
                # Save processed image
                processed_path = os.path.join(temp_dir, f"processed_{idx}.jpg")
                img.save(processed_path)
                processed_images.append(processed_path)
        
        st.success(f"Processed {len(processed_images)} images!")
        
        # Audio enhancement section
        st.subheader("Audio Enhancement")
        
        if st.button("Improve Audio Quality", type="secondary"):
            with st.spinner("Enhancing audio quality..."):
                try:
                    # Load audio
                    audio = AudioSegment.from_file(audio_path)
                    
                    # Trim audio if needed
                    if start_time > 0 or end_time < duration:
                        start_ms = int(start_time * 1000)
                        end_ms = int(end_time * 1000)
                        audio = audio[start_ms:end_ms]
                    
                    # Normalize audio
                    audio = normalize(audio)
                    
                    # Simple noise reduction (basic high-pass filter)
                    audio = audio.high_pass_filter(100)
                    
                    # Export enhanced audio
                    enhanced_audio_path = os.path.join(temp_dir, "enhanced_audio.wav")
                    audio.export(enhanced_audio_path, format="wav")
                    
                    st.success("Audio enhanced successfully!")
                    st.audio(enhanced_audio_path)
                    
                except Exception as e:
                    st.error(f"Error enhancing audio: {e}")
        
        # Video generation
        st.subheader("Generate Video")
        
        if st.button("Create Video", type="primary"):
            with st.spinner("Creating video..."):
                try:
                    # Use enhanced audio if available, otherwise original
                    final_audio_path = enhanced_audio_path if os.path.exists(enhanced_audio_path) else audio_path
                    
                    # Calculate duration per image
                    audio = AudioSegment.from_file(final_audio_path)
                    audio_duration = len(audio) / 1000
                    duration_per_image = audio_duration / len(processed_images)
                    
                    # Create video clips
                    clips = []
                    for img_path in processed_images:
                        clip = mpy.ImageClip(img_path).set_duration(duration_per_image)
                        
                        # Apply transitions based on selection
                        if selected_transition == "Fade":
                            clip = clip.crossfadein(1).crossfadeout(1)
                        elif selected_transition == "Slide":
                            # Simple slide effect
                            clip = clip.set_position(lambda t: (int(t*10), 0))
                        elif selected_transition == "Zoom":
                            # Simple zoom effect
                            clip = clip.resize(lambda t: 1 + 0.1 * t)
                        
                        clips.append(clip)
                    
                    # Concatenate clips
                    video = mpy.concatenate_videoclips(clips, method="compose")
                    
                    # Set audio
                    video = video.set_audio(mpy.AudioFileClip(final_audio_path))
                    
                    # Export video
                    output_path = os.path.join(temp_dir, "output_video.mp4")
                    video.write_videofile(
                        output_path, 
                        fps=24, 
                        codec="libx264", 
                        audio_codec="aac",
                        verbose=False,
                        logger=None
                    )
                    
                    st.session_state.video_path = output_path
                    st.success("Video created successfully!")
                    
                except Exception as e:
                    st.error(f"Error creating video: {e}")

with tab3:
    st.header("Preview & Export")
    
    if "video_path" in st.session_state and os.path.exists(st.session_state.video_path):
        # Video preview
        st.subheader("Video Preview")
        video_file = open(st.session_state.video_path, "rb")
        video_bytes = video_file.read()
        st.video(video_bytes)
        
        # Export options
        st.subheader("Export Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Download button
            st.download_button(
                label="Download Video",
                data=video_bytes,
                file_name="created_video.mp4",
                mime="video/mp4"
            )
        
        with col2:
            # Save to specific location
            save_path = st.text_input("Save to folder", value=os.path.expanduser("~/Videos"))
            if st.button("Save to Folder"):
                if os.path.isdir(save_path):
                    dest_path = os.path.join(save_path, "created_video.mp4")
                    with open(dest_path, "wb") as f:
                        f.write(video_bytes)
                    st.success(f"Video saved to {dest_path}")
                else:
                    st.error("Invalid directory path")
    else:
        st.info("Generate a video first to see the preview and export options.")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center'>
        <p>This app works completely offline. All processing is done on your local machine.</p>
    </div>
    """,
    unsafe_allow_html=True
)
