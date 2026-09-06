import os
import sys
import time
import urllib.request

def download_file(url, target_path):
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        print(f"Already exists: {target_path}")
        return True
    
    print(f"Downloading: {url} -> {target_path}")
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    temp_path = target_path + ".tmp"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp, open(temp_path, "wb") as f:
                f.write(resp.read())
            if os.path.exists(target_path):
                os.remove(target_path)
            os.rename(temp_path, target_path)
            print("OK.")
            return True
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(1)
    return False

if __name__ == "__main__":
    base_url = "https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/resolve/main"
    dest_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub", "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2", "snapshots", "e8f8c211226b894fcb81acc59f3b34ba3efd5f42")
    
    files = [
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.txt",
        "special_tokens_map.json",
        "sentencepiece.bpe.model"
    ]
    
    for fname in files:
        url = f"{base_url}/{fname}"
        download_file(url, os.path.join(dest_dir, fname))
        
    print("All tokenizer files checked/downloaded!")
