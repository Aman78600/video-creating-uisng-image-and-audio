import streamlit as st
import os
import tempfile
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageEnhance
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

# Function to process images and convert RGBA to RGB if needed
def process_image(img, brightness=1.0, contrast=1.0):
    # Convert RGBA to RGB if needed (remove alpha channel)
    if img.mode == 'RGBA':
        # Create a white background
        background = Image.new('RGB', img.size, (255, 255, 255))
        # Paste the image on the background
        background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Apply image enhancements
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(brightness)
    
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast)
    
    # Resize images to consistent size (16:9 aspect ratio)
    img = img.resize((1280, 720), Image.LANCZOS)
    
    return img

# App title and description
st.title("🎬 Offline Video Creator")
st.markdown("Create videos by combining images and audio - completely offline!")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    
    # Image duration
    image_duration = st.slider("Image Duration (seconds)", 2, 10, 5)
    
    # Image editing options
    st.subheader("Image Editing")
    brightness = st.slider("Brightness", 0.5, 1.5, 1.0)
    contrast = st.slider("Contrast", 0.5, 1.5, 1.0)

# Main content area
tab1, tab2 = st.tabs(["Upload Media", "Create & Download"])

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
    st.header("Create & Download Video")
    
    if not uploaded_images:
        st.warning("Please upload images to continue.")
    else:
        # Process images in memory without saving intermediate files
        processed_images_data = []
        
        with st.spinner("Processing images..."):
            progress_bar = st.progress(0)
            for idx, img_file in enumerate(uploaded_images):
                img = Image.open(img_file)
                
                # Process the image (convert RGBA to RGB if needed)
                img = process_image(img, brightness, contrast)
                
                # Save processed image to memory (BytesIO)
                img_bytes = BytesIO()
                img.save(img_bytes, format="JPEG", quality=95)
                processed_images_data.append(img_bytes.getvalue())
                
                # Update progress
                progress_bar.progress((idx + 1) / len(uploaded_images))
        
        st.success(f"Processed {len(processed_images_data)} images!")
        
        # Video generation
        if st.button("Create Video", type="primary"):
            with st.spinner("Creating video..."):
                try:
                    # Create a temporary directory for processing
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # Save processed images temporarily
                        temp_image_paths = []
                        for idx, img_data in enumerate(processed_images_data):
                            temp_path = os.path.join(temp_dir, f"img_{idx}.jpg")
                            with open(temp_path, "wb") as f:
                                f.write(img_data)
                            temp_image_paths.append(temp_path)
                        
                        # Create a text file with image paths and durations
                        concat_file = os.path.join(temp_dir, "input.txt")
                        with open(concat_file, "w") as f:
                            for img_path in temp_image_paths:
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
                        final_video_path = os.path.join(temp_dir, "final_video.mp4")
                        
                        if uploaded_audio:
                            # Save audio temporarily
                            audio_data = uploaded_audio.read()
                            temp_audio_path = os.path.join(temp_dir, "audio.mp3")
                            with open(temp_audio_path, "wb") as f:
                                f.write(audio_data)
                            
                            # Add audio to video
                            cmd = [
                                "ffmpeg", "-y",
                                "-i", temp_video_path,
                                "-i", temp_audio_path,
                                "-c:v", "copy", "-c:a", "aac", "-shortest",
                                final_video_path
                            ]
                        else:
                            # Copy video without audio
                            cmd = [
                                "ffmpeg", "-y",
                                "-i", temp_video_path,
                                "-c", "copy",
                                final_video_path
                            ]
                        
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode != 0:
                            st.error(f"FFmpeg error: {result.stderr}")
                            st.stop()
                        
                        # Read the final video into memory
                        with open(final_video_path, "rb") as f:
                            video_data = f.read()
                        
                        # Store video data in session state
                        st.session_state.video_data = video_data
                        st.success("Video created successfully!")
                
                except Exception as e:
                    st.error(f"Error creating video: {e}")
        
        # Display video and download button if video exists
        if "video_data" in st.session_state and st.session_state.video_data:
            st.subheader("Video Preview")
            
            # Display video
            st.video(st.session_state.video_data)
            
            # Download button
            st.download_button(
                label="Download Video",
                data=st.session_state.video_data,
                file_name="created_video.mp4",
                mime="video/mp4",
                key="download_button"
            )

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
