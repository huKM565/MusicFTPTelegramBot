import os
import paramiko
from yt_dlp import YoutubeDL
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = "downloads"
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_TARGET_DIR = os.getenv("FTP_TARGET_DIR")
PROXY_URL = os.getenv("PROXY_URL")

def download_audio(url):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "proxy": PROXY_URL,
        "outtmpl": f"{OUTPUT_DIR}/%(title)s.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "quiet": True,
        "no_warnings": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        audio_file = os.path.splitext(filename)[0] + ".mp3"
        return audio_file

def search_youtube(query, limit=5):
    ydl_opts = {
        "format": "bestaudio/best",
        "proxy": PROXY_URL,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,  # Не скачивать, только получить инфо
    }

    with YoutubeDL(ydl_opts) as ydl:
        # ytsearchN:query - поиск N результатов
        search_query = f"ytsearch{limit}:{query}"
        info = ydl.extract_info(search_query, download=False)
        
        results = []
        if 'entries' in info:
            for entry in info['entries']:
                results.append({
                    'title': entry.get('title'),
                    'url': entry.get('url'),
                    'duration': entry.get('duration'),
                    'id': entry.get('id')
                })
        return results

def upload_via_sftp(file_path):
    transport = paramiko.Transport((FTP_HOST, 22))
    transport.connect(username=FTP_USER, password=FTP_PASS)

    sftp = paramiko.SFTPClient.from_transport(transport)

    try:
        sftp.chdir(FTP_TARGET_DIR)
    except IOError:
        # Если директории нет, можно попробовать создать или просто упасть с ошибкой
        # В данном случае просто логируем, что директория может не существовать
        print(f"Directory {FTP_TARGET_DIR} might not exist.")

    sftp.put(file_path, os.path.basename(file_path))

    sftp.close()
    transport.close()
    return True
    