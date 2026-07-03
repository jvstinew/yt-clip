import os
import re
import subprocess
import json
import uuid
from flask import Flask, request, jsonify, send_file, after_this_request

app = Flask(__name__)

# Folder penyimpanan sementara klip
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def is_valid_youtube_url(url):
    pattern = r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$'
    return re.match(pattern, url) is not None

@app.route("/api/info", methods=["GET"])
def get_info():
    url = request.args.get("url")
    if not url or not is_valid_youtube_url(url):
        return jsonify({"error": "URL YouTube tidak valid atau kosong"}), 400
    try:
        # Mengambil metadata JSON video secara instan tanpa mendownload video
        cmd = ["yt-dlp", "--dump-json", "--no-playlist", url]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        return jsonify({
            "id": data.get("id"),
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "channel": data.get("uploader") or data.get("channel")
        })
    except Exception as e:
        return jsonify({"error": f"Gagal mengambil info video: {str(e)}"}), 500

@app.route("/api/download", methods=["GET"])
def download_clip():
    url = request.args.get("url")
    start = request.args.get("start", "00:00:00")
    end = request.args.get("end", "00:00:10")
    fmt = request.args.get("format", "mp4")
    
    if not url or not is_valid_youtube_url(url):
        return jsonify({"error": "URL YouTube tidak valid"}), 400
    
    file_id = f"clip_{uuid.uuid4().hex[:8]}"
    ext = "mp3" if fmt == "mp3" else "mp4"
    output_filename = f"{file_id}.{ext}"
    output_path = os.path.join(DOWNLOADS_DIR, output_filename)
    
    # Fitur download section yt-dlp (Sangat Hemat Bandwidth & RAM Server)
    download_section_arg = f"*{start}-{end}"
    
    try:
        if fmt == "mp3":
            cmd = [
                "yt-dlp", "-f", "ba",
                "--download-sections", download_section_arg,
                "--extract-audio", "--audio-format", "mp3",
                "-o", output_path, url
            ]
        else:
            cmd = [
                "yt-dlp", 
                "-f", "bv*[ext=mp4]+ba*[ext=m4a]/b[ext=mp4]/best",
                "--download-sections", download_section_arg,
                "-o", output_path, url
            ]
        
        # Eksekusi yt-dlp server-side
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        
        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except Exception:
                pass
            return response
            
        return send_file(output_path, as_attachment=True, download_name=f"clip_{file_id}.{ext}")
    except Exception as e:
        return jsonify({"error": f"Gagal memotong video: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
