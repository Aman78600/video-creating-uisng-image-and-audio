import streamlit as st
import tempfile
import os
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, filtfilt
import io
import base64

# Set page config
st.set_page_config(
    page_title="Image + Audio to Video Maker",
    page_icon="🎬",
    layout="wide"
)

def enhance_audio(audio_file):
    """Enhanced audio processing with noise reduction and normalization"""
    try:
        # Load audio with pydub
        audio = AudioSegment.from_file(audio_file)
        
        # Convert to mono if stereo
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Normalize volume
        audio = normalize(audio)
        
        # Convert to numpy array for advanced processing
        samples = np.array(audio.get_array_of_samples())
        sample_rate = audio.frame_rate
        
        # Simple noise reduction using high-pass filter
        def butter_highpass_filter(data, cutoff, fs, order=4):
            nyquist = 0.5 * fs
            normal_cutoff = cutoff / nyquist
            b, a = butter(order, normal_cutoff, btype='high', analog=False)
            y = filtfilt(b, a, data)
            return y
        
        # Apply high-pass filter to reduce low-frequency noise
        filtered_samples = butter_highpass_filter(samples, 80, sample_rate)
        
        # Normalize again after filtering
        filtered_samples = filtered_samples / np.max(np.abs(filtered_samples))
        filtered_samples = (filtered_samples * 32767).astype(np.int16)
        
        # Convert back to AudioSegment
        enhanced_audio = AudioSegment(
            filtered_samples.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,
            channels=1
        )
        
        # Final normalization
        enhanced_audio = normalize(enhanced_audio)
        
        return enhanced_audio
        
    except Exception as e:
        st.error(f"Error enhancing audio: {str(e)}")
        return None

def create_video(image_file, audio_file, output_path):
    """Create video from image and enhanced audio"""
    try:
        with st.spinner("Enhancing audio..."):
            # Enhance audio
            enhanced_audio = enhance_audio(audio_file)
            if enhanced_audio is None:
                return False
            
            # Save enhanced audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                enhanced_audio.export(temp_audio.name, format='wav')
                temp_audio_path = temp_audio.name
        
        with st.spinner("Creating video..."):
            # Load audio clip
            audio_clip = AudioFileClip(temp_audio_path)
            
            # Load image and create video clip with same duration as audio
            image_clip = ImageClip(image_file).set_duration(audio_clip.duration)
            
            # Set audio to the video
            final_video = image_clip.set_audio(audio_clip)
            
            # Write video file
            final_video.write_videofile(
                output_path,
                fps=24,
                codec='libx264',
                audio_codec='aac',
                verbose=False,
                logger=None
            )
            
            # Clean up
            audio_clip.close()
            image_clip.close()
            final_video.close()
            os.unlink(temp_audio_path)
            
            return True
            
    except Exception as e:
        st.error(f"Error creating video: {str(e)}")
        return False

def get_download_link(file_path, file_name):
    """Generate download link for the video file"""
    with open(file_path, "rb") as f:
        video_bytes = f.read()
    b64 = base64.b64encode(video_bytes).decode()
    href = f'<a href="data:video/mp4;base64,{b64}" download="{file_name}">📥 Download Video</a>'
    return href

def main():
    st.title("🎬 Image + Audio to Video Maker")
    st.markdown("Upload an image and audio file to create a video with enhanced audio quality!")
    
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
            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
                temp_img.write(image_file.read())
                temp_img_path = temp_img.name
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
                temp_audio.write(audio_file.read())
                temp_audio_path = temp_audio.name
            
            # Output video path
            output_video_path = tempfile.mktemp(suffix='.mp4')
            
            # Create video
            success = create_video(temp_img_path, temp_audio_path, output_video_path)
            
            if success:
                st.success("✅ Video created successfully!")
                
                # Display video
                st.subheader("🎥 Your Video")
                with open(output_video_path, 'rb') as video_file:
                    video_bytes = video_file.read()
                    st.video(video_bytes)
                
                # Download button
                st.markdown("---")
                st.subheader("📥 Download")
                
                # Create download button
                with open(output_video_path, 'rb') as f:
                    video_data = f.read()
                
                st.download_button(
                    label="📥 Download Video",
                    data=video_data,
                    file_name="enhanced_video.mp4",
                    mime="video/mp4",
                    type="primary",
                    use_container_width=True
                )
                
                # Show file info
                file_size = len(video_data) / (1024 * 1024)  # Size in MB
                st.info(f"Video size: {file_size:.2f} MB")
            
            # Clean up temporary files
            try:
                os.unlink(temp_img_path)
                os.unlink(temp_audio_path)
                if os.path.exists(output_video_path):
                    os.unlink(output_video_path)
            except:
                pass
    
    else:
        st.info("👆 Please upload both an image and audio file to create a video.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    ### Features:
    - 🔊 **Audio Enhancement**: Noise reduction and volume normalization
    - 🎨 **Image Support**: PNG, JPG, JPEG, GIF, BMP
    - 🎵 **Audio Support**: MP3, WAV, OGG, FLAC, M4A, AAC
    - 🎬 **Video Output**: High-quality MP4 with optimized settings
    - 📱 **Easy Download**: One-click video download
    """)

if __name__ == "__main__":
    main()
