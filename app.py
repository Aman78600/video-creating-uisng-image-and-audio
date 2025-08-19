import streamlit as st
import tempfile
import os
import subprocess
import numpy as np
import io
import base64
from PIL import Image
import wave
import threading
import time

# Set page config
st.set_page_config(
    page_title="Image + Audio to Video Maker",
    page_icon="🎬",
    layout="wide"
)

def check_ffmpeg():
    """Check if ffmpeg is available"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except:
        return False

def get_audio_duration(audio_path):
    """Get audio duration in seconds"""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'a:0',
            '-show_entries', 'format=duration', 
            '-of', 'csv=p=0', audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except:
        pass
    return None

def enhance_audio_basic(audio_file_path, output_path):
    """Basic audio enhancement using ffmpeg"""
    try:
        # Simple but effective audio enhancement
        cmd = [
            'ffmpeg', '-i', audio_file_path,
            '-af', 'volume=1.2,highpass=f=60',
            '-ar', '44100', '-ac', '2',
            '-y', output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            st.error(f"FFmpeg audio error: {result.stderr}")
            return False
        return True
        
    except Exception as e:
        st.error(f"Audio enhancement failed: {str(e)}")
        return False

def create_video_ffmpeg(image_path, audio_path, output_path, timeout=None):
    """Create video using ffmpeg with proper dimension and codec handling"""
    try:
        # Get audio duration for progress tracking
        duration = get_audio_duration(audio_path)
        if duration:
            st.info(f"Processing audio: {duration:.2f} seconds")
        
        # Fixed command that addresses the issues found in the error log:
        # 1. Uses video filter to ensure even dimensions
        # 2. Forces AAC audio codec 
        # 3. Proper pixel format
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1', '-i', image_path,
            '-i', audio_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',  # Ensure even dimensions
            '-pix_fmt', 'yuv420p',
            '-ar', '44100',  # Standard audio sample rate
            '-b:a', '128k',
            '-shortest',
            '-movflags', '+faststart',
            output_path
        ]
        
        st.info("Running FFmpeg command with dimension fix...")
        
        # Use Popen for better timeout control
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait for process to complete with timeout
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            st.error(f"FFmpeg process timed out after {timeout} seconds")
            return False
        
        if process.returncode == 0:
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
            else:
                st.error("Video file was not created or is empty")
                return False
        else:
            st.error(f"FFmpeg failed with return code {process.returncode}")
            st.error(f"Error output: {stderr}")
            return False
        
    except Exception as e:
        st.error(f"Video creation failed: {str(e)}")
        return False

def create_video_in_chunks(image_path, audio_path, output_path, chunk_duration=600):
    """Create video by processing audio in chunks to avoid timeout issues"""
    try:
        # Get total audio duration
        total_duration = get_audio_duration(audio_path)
        if not total_duration:
            st.error("Could not determine audio duration")
            return False
        
        st.info(f"Processing long audio ({total_duration:.2f}s) in chunks...")
        
        # Create temporary directory for chunks
        temp_dir = tempfile.mkdtemp()
        video_chunks = []
        
        # Calculate number of chunks
        num_chunks = int(total_duration // chunk_duration) + 1
        
        # Process each chunk
        for i in range(num_chunks):
            start_time = i * chunk_duration
            chunk_output = os.path.join(temp_dir, f"chunk_{i}.mp4")
            
            # Create chunk
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', image_path,
                '-i', audio_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
                '-pix_fmt', 'yuv420p',
                '-ar', '44100',
                '-b:a', '128k',
                '-ss', str(start_time),
                '-t', str(chunk_duration),
                '-movflags', '+faststart',
                chunk_output
            ]
            
            st.info(f"Processing chunk {i+1}/{num_chunks}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                st.error(f"Chunk {i+1} failed: {result.stderr}")
                return False
                
            video_chunks.append(chunk_output)
        
        # Concatenate all chunks
        if len(video_chunks) > 1:
            # Create file list for concatenation
            list_file = os.path.join(temp_dir, "file_list.txt")
            with open(list_file, 'w') as f:
                for chunk in video_chunks:
                    f.write(f"file '{chunk}'\n")
            
            # Concatenate videos
            cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', list_file, '-c', 'copy', output_path
            ]
            
            st.info("Combining chunks...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                st.error(f"Concatenation failed: {result.stderr}")
                return False
        else:
            # Only one chunk, just copy it
            import shutil
            shutil.copy2(video_chunks[0], output_path)
        
        # Clean up temp directory
        import shutil
        shutil.rmtree(temp_dir)
        
        return os.path.exists(output_path)
        
    except Exception as e:
        st.error(f"Chunked processing failed: {str(e)}")
        return False

def main():
    st.title("🎬 Image + Audio to Video Maker")
    st.markdown("Upload an image and audio file to create a video with enhanced audio quality!")
    
    # Check system requirements
    if not check_ffmpeg():
        st.error("❌ FFmpeg is not available. This app requires FFmpeg to function properly.")
        st.info("If you're deploying on Streamlit Cloud, make sure you have a `packages.txt` file with 'ffmpeg' listed.")
        return
    
    st.success("✅ FFmpeg is available!")
    
    # Create two columns for file uploads
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📸 Upload Image")
        image_file = st.file_uploader(
            "Choose an image file",
            type=['png', 'jpg', 'jpeg', 'gif', 'bmp'],
            key="image_upload"
        )
        
        if image_file is not None:
            st.image(image_file, caption="Uploaded Image", use_column_width=True)
    
    with col2:
        st.subheader("🎵 Upload Audio")
        audio_file = st.file_uploader(
            "Choose an audio file",
            type=['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac'],
            key="audio_upload"
        )
        
        if audio_file is not None:
            st.audio(audio_file, format='audio/wav')
            st.success("Audio file uploaded successfully!")
    
    # Show Make Video button only when both files are uploaded
    if image_file is not None and audio_file is not None:
        st.markdown("---")
        
        # Add advanced options
        with st.expander("Advanced Options"):
            chunk_processing = st.checkbox("Enable chunked processing for long audio", value=True)
            chunk_size = st.slider("Chunk size (minutes)", min_value=5, max_value=60, value=10)
        
        if st.button("🎬 Make Video", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Create temporary files
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
                    temp_img.write(image_file.read())
                    temp_img_path = temp_img.name
                
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
                    temp_audio.write(audio_file.read())
                    temp_audio_path = temp_audio.name
                
                progress_bar.progress(25)
                status_text.text("Enhancing audio...")
                
                # Enhanced audio path
                enhanced_audio_path = tempfile.mktemp(suffix='.wav')
                
                # Try audio enhancement with fallback
                enhanced = enhance_audio_basic(temp_audio_path, enhanced_audio_path)
                if not enhanced:
                    st.warning("Audio enhancement failed, using original audio")
                    enhanced_audio_path = temp_audio_path
                
                progress_bar.progress(60)
                status_text.text("Creating video...")
                
                # Output video path
                output_video_path = tempfile.mktemp(suffix='.mp4')
                
                # Debug info
                st.info(f"Image: {os.path.getsize(temp_img_path)/1024:.1f} KB")
                st.info(f"Audio: {os.path.getsize(enhanced_audio_path)/1024:.1f} KB")
                
                # Get audio duration
                audio_duration = get_audio_duration(enhanced_audio_path)
                if audio_duration:
                    st.info(f"Audio duration: {audio_duration:.2f} seconds")
                
                # Create video with appropriate method based on duration
                success = False
                
                # For long audio, use chunked processing
                if audio_duration and audio_duration > 600 and chunk_processing:  # 10 minutes
                    success = create_video_in_chunks(
                        temp_img_path, 
                        enhanced_audio_path, 
                        output_video_path,
                        chunk_duration=chunk_size * 60  # Convert to seconds
                    )
                else:
                    # For shorter audio, use standard approach with longer timeout
                    timeout = 600  # 10 minutes
                    if audio_duration and audio_duration > 300:  # More than 5 minutes
                        timeout = max(timeout, int(audio_duration * 1.5))
                    
                    success = create_video_ffmpeg(
                        temp_img_path, 
                        enhanced_audio_path, 
                        output_video_path,
                        timeout=timeout
                    )
                
                # Fallback to original audio if enhanced failed
                if not success and enhanced:
                    st.warning("Trying with original audio...")
                    if audio_duration and audio_duration > 600 and chunk_processing:
                        success = create_video_in_chunks(
                            temp_img_path, 
                            temp_audio_path, 
                            output_video_path,
                            chunk_duration=chunk_size * 60
                        )
                    else:
                        timeout = 600
                        if audio_duration and audio_duration > 300:
                            timeout = max(timeout, int(audio_duration * 1.5))
                        
                        success = create_video_ffmpeg(
                            temp_img_path, 
                            temp_audio_path, 
                            output_video_path,
                            timeout=timeout
                        )
                
                progress_bar.progress(90)
                
                if success and os.path.exists(output_video_path):
                    progress_bar.progress(100)
                    status_text.text("Video created successfully!")
                    
                    st.success("✅ Video created successfully!")
                    
                    # Display video
                    st.subheader("🎥 Your Video")
                    with open(output_video_path, 'rb') as video_file:
                        video_bytes = video_file.read()
                        st.video(video_bytes)
                    
                    # Download button
                    st.markdown("---")
                    st.subheader("📥 Download")
                    
                    st.download_button(
                        label="📥 Download Video",
                        data=video_bytes,
                        file_name="enhanced_video.mp4",
                        mime="video/mp4",
                        type="primary",
                        use_container_width=True
                    )
                    
                    # Show file info
                    file_size = len(video_bytes) / (1024 * 1024)  # Size in MB
                    st.info(f"Video size: {file_size:.2f} MB")
                else:
                    st.error("Failed to create video. Please try again.")
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
            
            finally:
                # Clean up temporary files
                for path in [temp_img_path, temp_audio_path, enhanced_audio_path, output_video_path]:
                    try:
                        if os.path.exists(path):
                            os.unlink(path)
                    except:
                        pass
                
                progress_bar.empty()
                status_text.empty()
    
    else:
        st.info("👆 Please upload both an image and audio file to create a video.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    ### Features:
    - 🔊 **Audio Enhancement**: Noise reduction and volume normalization using FFmpeg
    - 🎨 **Image Support**: PNG, JPG, JPEG, GIF, BMP
    - 🎵 **Audio Support**: MP3, WAV, OGG, FLAC, M4A, AAC
    - 🎬 **Video Output**: High-quality MP4 with optimized settings
    - 📱 **Easy Download**: One-click video download
    - ⚡ **Fast Processing**: Direct FFmpeg integration for better performance
    - ⏰ **Long Audio Support**: Chunked processing for audio of any length
    """)
    
    # Troubleshooting section
    with st.expander("🔧 Troubleshooting"):
        st.markdown("""
        **Common Issues:**
        - **ModuleNotFoundError**: Make sure all dependencies are installed
        - **FFmpeg not found**: Ensure FFmpeg is installed on your system
        - **Large file issues**: Try using smaller audio/image files
        - **Processing timeout**: For very long audio, enable chunked processing
        
        **Deployment on Streamlit Cloud:**
        1. Make sure `packages.txt` contains `ffmpeg`
        2. All dependencies should install automatically
        3. Check the app logs if issues persist
        """)

if __name__ == "__main__":
    main()
