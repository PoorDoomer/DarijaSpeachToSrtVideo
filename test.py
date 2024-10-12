import os
import json
from pathlib import Path
import yt_dlp
from tafrigh import Config, TranscriptType, farrigh
import ffmpeg

def get_user_input():
    url = input("Enter the YouTube video URL: ")
    ar_key = input("Enter the Wit.ai API key for Arabic: ")
    return url, {'ar': ar_key}

def download_video(url, output_path):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def download_audio(url, output_path):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'outtmpl': output_path,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    # Check if the file has a double extension and rename it
    if os.path.exists(output_path + '.wav'):
        os.rename(output_path + '.wav', output_path)

def transcribe_arabic(audio_file, api_key):
    output_dir = 'output_ar'
    os.makedirs(output_dir, exist_ok=True)
    input_config = Config.Input(
        urls_or_paths=[audio_file],
        skip_if_output_exist=False,
        playlist_items="",
        download_retries=0,
        verbose=False
    )

    whisper_config = Config.Whisper(
        model_name_or_path="",
        task="",
        language="",
        use_faster_whisper=False,
        beam_size=0,
        ct2_compute_type=""
    )

    wit_config = Config.Wit(
        wit_client_access_tokens=[api_key],
        max_cutting_duration=5
    )

    output_config = Config.Output(
        min_words_per_segment=1,
        save_files_before_compact=False,
        save_yt_dlp_responses=False,
        output_sample=0,
        output_formats=[TranscriptType.JSON.value],
        output_dir=output_dir
    )
    config = Config(
            input=input_config,
            whisper=whisper_config,
            wit=wit_config,
            output=output_config
        )
    
    list(farrigh(config))

    json_files = list(Path(output_dir).glob('*.json'))
    return str(json_files[0]) if json_files else None

def generate_srt(transcription_result):
    with open(transcription_result, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    srt_content = ""
    for i, segment in enumerate(data, 1):
        if 'text' in segment:
            start_time = segment.get('start', 0)
            end_time = segment.get('end', start_time + 1)
            text = segment['text']
            srt_content += f"{i}\n{format_time(start_time)} --> {format_time(end_time)}\n{text}\n\n"
    
    srt_file = 'output.srt'
    with open(srt_file, 'w', encoding='utf-8') as f:
        f.write(srt_content)
    
    return srt_file

def format_time(seconds):
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace('.', ',')

def burn_subtitles(video_file, srt_file, output_file):
    try:
        (
            ffmpeg
            .input(video_file)
            .output(output_file, vf=f"subtitles='{srt_file}':force_style='FontName=Arial,FontSize=36,PrimaryColour=&H00FFFFFF,OutlineColour=&H000000FF,BackColour=&H80000000,Outline=3,Shadow=0,MarginV=30'")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        print(f"Video with high-resolution burned-in subtitles has been generated as '{output_file}'")
    except ffmpeg.Error as e:
        print('stdout:', e.stdout.decode('utf8'))
        print('stderr:', e.stderr.decode('utf8'))
        raise

def main():
    url, api_keys = get_user_input()

    # Download video
    video_file = 'video.mp4'
    print(f"Downloading video from {url}")
    download_video(url, video_file)

    # Download audio from YouTube
    audio_file = 'audio.wav'
    print(f"Downloading audio from {url}")
    download_audio(url, audio_file)

    # Ensure the audio file exists
    if not os.path.exists(audio_file):
        print(f"Error: Audio file '{audio_file}' not found.")
        return

    # Transcribe audio
    print("Transcribing audio in Arabic")
    transcription_result = transcribe_arabic(audio_file, api_keys['ar'])

    if transcription_result:
        print("Transcription complete. Result saved in JSON file:")
        print(f"Arabic: {transcription_result}")
        
        # Generate SRT file
        srt_file = generate_srt(transcription_result)
        
        # Burn subtitles into video
        output_video = 'output_with_subtitles.mp4'
        burn_subtitles(video_file, srt_file, output_video)
    else:
        print("Transcription failed for Arabic")

    # Clean up
    os.remove(audio_file)
    os.remove(video_file)

if __name__ == "__main__":
    main()
