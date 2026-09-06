import os
import sys
import time
import urllib.request

def download_file_with_resume(url, target_path):
    print(f"Target file: {target_path}")
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    temp_path = target_path + ".tmp"
    
    downloaded = 0
    if os.path.exists(temp_path):
        downloaded = os.path.getsize(temp_path)
        print(f"Resuming download from byte {downloaded} ({downloaded / (1024*1024):.1f} MB)...")
    
    max_retries = 20
    chunk_size = 1024 * 1024  # 1MB
    
    for attempt in range(1, max_retries + 1):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0'
            }
            if downloaded > 0:
                headers['Range'] = f"bytes={downloaded}-"
            
            req = urllib.request.Request(url, headers=headers)
            start_time = time.time()
            
            with urllib.request.urlopen(req, timeout=45) as resp:
                status = resp.status
                content_range = resp.headers.get("Content-Range")
                content_length = int(resp.headers.get("Content-Length", 0))
                
                if content_range:
                    # Content-Range: bytes 245366784-470641599/470641600
                    total_size = int(content_range.split('/')[-1])
                else:
                    total_size = downloaded + content_length
                
                mode = "ab" if downloaded > 0 else "wb"
                with open(temp_path, mode) as f:
                    last_percent = -1
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int(downloaded * 100 / total_size)
                            if percent != last_percent and percent % 5 == 0:
                                speed = (len(chunk) / (1024 * 1024)) / max(0.01, time.time() - start_time)
                                print(f"Progress: {percent}% ({downloaded / (1024*1024):.1f}/{total_size / (1024*1024):.1f} MB)")
                                last_percent = percent
                                start_time = time.time()
                
                # If finished
                if downloaded >= total_size:
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    os.rename(temp_path, target_path)
                    print(f"Download completed successfully! Saved to {target_path}")
                    return True
        except Exception as e:
            print(f"[Attempt {attempt}/{max_retries}] Connection dropped ({e}). Reconnecting in 3s...")
            time.sleep(3)
            if os.path.exists(temp_path):
                downloaded = os.path.getsize(temp_path)
                
    raise RuntimeError("Failed to complete download after max retries")

if __name__ == "__main__":
    url = "https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/resolve/main/model.safetensors"
    dest = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub", "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2", "snapshots", "e8f8c211226b894fcb81acc59f3b34ba3efd5f42", "model.safetensors")
    download_file_with_resume(url, dest)
