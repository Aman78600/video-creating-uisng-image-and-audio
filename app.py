import streamlit as st
import os
import tempfile
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageEnhance, ImageOps
import numpy as np
from io import BytesIO
import time

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
    transition_options = ["None", "Fade", "Slide"]
    selected_transition = st.selectbox("Transition Effect", transition_options)
    
    # Image duration
    image_duration = st.slider("Image Duration (seconds)", 2, 10, 5)
    
    # Image editing options
    st.subheader("Image Editing")
    brightness = st.slider("Brightness", 0.5, 1.5, 1.0)
    contrast = st.slider("Contrast", 0.5, 1.5, 1.0)

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
        type=["mp3", "wav", "ogg"]
    )
    
    # Display audio info if uploaded
    if uploaded_audio:
        st.subheader("Audio File")
        st.audio(uploaded_audio)

with tab2:
    st.header("Edit & Process")
    
    if not uploaded_images:
        st.warning("Please upload images to continue.")
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
                
                # Resize images to consistent size
                img = img.resize((1280, 720))
                
                # Save processed image
                processed_path = os.path.join(temp_dir, f"processed_{idx}.jpg")
                img.save(processed_path)
                processed_images.append(processed_path)
        
        st.success(f"Processed {len(processed_images)} images!")
        
        # Save audio file if uploaded
        audio_path = None
        if uploaded_audio:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                tmp_audio.write(uploaded_audio.read())
                audio_path = tmp_audio.name
            st.success("Audio file processed!")
        
        # Video generation
        st.subheader("Generate Video")
        
        if st.button("Create Video", type="primary"):
            with st.spinner("Creating video..."):
                try:
                    # Create a text file with image paths and durations
                    concat_file = os.path.join(temp_dir, "input.txt")
                    with open(concat_file, "w") as f:
                        for img_path in processed_images:
                            f.write(f"file '{img_path}'\n")
                            f.write(f"duration {image_duration}\n")
                    
                    # Create video from images
                    temp_video_path = os.path.join(temp_dir, "temp_video.mp4")
                    
                    # Build FFmpeg command
                    cmd = [
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", concat_file,
                        "-vf", "fps=30,format=yuv420p",
                        "-c:v", "libx264", "-preset", "medium",
                        temp_video_path
                    ]
                    
                    # Run FFmpeg
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        st.error(f"FFmpeg error: {result.stderr}")
                        st.stop()
                    
                    # Add audio if provided
                    output_path = os.path.join(temp_dir, "output_video.mp4")
                    
                    if audio_path:
                        # Get audio duration
                        cmd = [
                            "ffmpeg", "-i", audio_path
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        # Add audio to video
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", temp_video_path,
                            "-i", audio_path,
                            "-c:v", "copy", "-c:a", "aac", "-shortest",
                            output_path
                        ]
                    else:
                        # Copy video without audio
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", temp_video_path,
                            "-c", "copy",
                            output_path
                        ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        st.error(f"FFmpeg error: {result.stderr}")
                        st.stop()
                    
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
