import streamlit as st
import tempfile
import os
import subprocess
import numpy as np
import io
import base64
from PIL import Image
import wave

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

def enhance_audio_basic(audio_file_path, output_path):
    """Basic audio enhancement using ffmpeg"""
    try:
        # Basic audio enhancement with ffmpeg
        cmd = [
            'ffmpeg', '-i', audio_file_path,
            '-af', 'highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11',
            '-y', output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0
    except Exception as e:
        st.error(f"Audio enhancement failed: {str(e)}")
        return False

def create_video_ffmpeg(image_path, audio_path, output_path):
    """Create video using ffmpeg directly"""
    try:
        # Get audio duration first
        duration_cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', 
            audio_path
        ]
        
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=30)
        if duration_result.returncode != 0:
            st.error("Failed to get audio duration")
            return False
            
        duration = float(duration_result.stdout.strip())
        
        # Create video with ffmpeg
        cmd = [
            'ffmpeg', '-loop', '1', '-i', image_path,
            '-i', audio_path,
            '-c:v', 'libx264', '-tune', 'stillimage',
            '-c:a', 'aac', '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-shortest', '-y', output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
        
    except Exception as e:
        st.error(f"Video creation failed: {str(e)}")
        return False

def fallback_audio_enhancement(input_file, output_file):
    """Fallback audio enhancement without external libraries"""
    try:
        # Simple copy with basic normalization using ffmpeg
        cmd = [
            'ffmpeg', '-i', input_file,
            '-filter:a', 'dynaudnorm',
            '-y', output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0
    except:
        # If all else fails, just copy the file
        import shutil
        shutil.copy2(input_file, output_file)
        return True

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
                
                # Try advanced audio enhancement first, fallback to basic
                enhanced = enhance_audio_basic(temp_audio_path, enhanced_audio_path)
                if not enhanced:
                    enhanced = fallback_audio_enhancement(temp_audio_path, enhanced_audio_path)
                
                if not enhanced:
                    st.error("Failed to enhance audio")
                    return
                
                progress_bar.progress(60)
                status_text.text("Creating video...")
                
                # Output video path
                output_video_path = tempfile.mktemp(suffix='.mp4')
                
                # Create video
                success = create_video_ffmpeg(temp_img_path, enhanced_audio_path, output_video_path)
                
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
    """)
    
    # Troubleshooting section
    with st.expander("🔧 Troubleshooting"):
        st.markdown("""
        **Common Issues:**
        - **ModuleNotFoundError**: Make sure all dependencies are installed
        - **FFmpeg not found**: Ensure FFmpeg is installed on your system
        - **Large file issues**: Try using smaller audio/image files
        - **Processing timeout**: Check your internet connection and file sizes
        
        **Deployment on Streamlit Cloud:**
        1. Make sure `packages.txt` contains `ffmpeg`
        2. All dependencies should install automatically
        3. Check the app logs if issues persist
        """)

if __name__ == "__main__":
    main()
