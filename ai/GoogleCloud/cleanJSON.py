import json
import os
import re
from pathlib import Path
from deep_translator import GoogleTranslator
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

def translate_prefix(text: str, translator: GoogleTranslator) -> str:
    """
    Translate the Prefix part in the text field from English to Vietnamese.
    Keep the Original part unchanged.
    
    Format: "Prefix: <english text>; Original: <original content>"
    """
    if not text or "Prefix:" not in text:
        return text
    
    # Split by "; Original:"
    parts = text.split("; Original:", 1)
    if len(parts) != 2:
        return text
    
    prefix_part = parts[0]  # "Prefix: <english text>"
    original_part = parts[1]  # "<original content>"
    
    # Extract the English text after "Prefix: "
    if prefix_part.startswith("Prefix: "):
        english_text = prefix_part[8:]  # Remove "Prefix: "
        
        try:
            # Translate to Vietnamese
            vietnamese_text = translator.translate(english_text)
            
            # Add small delay to avoid rate limiting
            time.sleep(0.1)
            
            # Reconstruct the text with Vietnamese prefix
            return f"Prefix: {vietnamese_text}; Original: {original_part}"
        except Exception as e:
            print(f"Translation error: {e}")
            return text
    
    return text

def count_tokens(text: str) -> int:
    """Simple token count approximation (split by whitespace)"""
    return len(text.split())

def should_keep_record(text: str, min_tokens: int = 0) -> bool:
    """Check if record should be kept based on Original text length"""
    if not text or "; Original:" not in text:
        return True
    
    # Extract Original part
    parts = text.split("; Original:", 1)
    if len(parts) != 2:
        return True
    
    original_text = parts[1].strip()
    token_count = count_tokens(original_text)
    
    return token_count >= min_tokens

def process_json_file(file_path: str, translator: GoogleTranslator) -> None:
    """Process a single JSON file and translate all Prefix parts"""
    print(f"Processing: {os.path.basename(file_path)}")
    
    try:
        # Read JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print(f"Skipping {file_path}: Not a list format")
            return
        
        original_count = len(data)
        
        # Filter and translate records
        filtered_data = []
        translated_count = 0
        removed_count = 0
        
        for record in data:
            if isinstance(record, dict) and 'text' in record:
                original_text = record['text']
                
                # Check if record should be kept
                if not should_keep_record(original_text):
                    removed_count += 1
                    continue
                
                # Translate prefix
                translated_text = translate_prefix(original_text, translator)
                
                if original_text != translated_text:
                    record['text'] = translated_text
                    translated_count += 1
                
                filtered_data.append(record)
            else:
                filtered_data.append(record)
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {os.path.basename(file_path)}: Translated {translated_count} | Removed {removed_count} | Kept {len(filtered_data)}/{original_count}")
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")

def clean_json_folder(folder_path: str, max_workers: int = 4) -> None:
    """Process all JSON files in the folder using multiple threads"""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"Folder not found: {folder_path}")
        return
    
    json_files = list(folder.glob("*.json"))
    
    if not json_files:
        print(f"No JSON files found in {folder_path}")
        return
    
    print(f"Found {len(json_files)} JSON files")
    print(f"Processing with {max_workers} threads")
    print("=" * 80)
    
    # Create a lock for thread-safe printing
    print_lock = Lock()
    
    def process_file_wrapper(json_file):
        """Wrapper function to process file with its own translator"""
        translator = GoogleTranslator(source='en', target='vi')
        
        with print_lock:
            print(f"Starting: {json_file.name}")
        
        process_json_file(str(json_file), translator)
        
        with print_lock:
            print("-" * 80)
        
        return json_file.name
    
    # Process files in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(process_file_wrapper, json_file): json_file 
                         for json_file in json_files}
        
        completed = 0
        total = len(json_files)
        
        for future in as_completed(future_to_file):
            file = future_to_file[future]
            completed += 1
            try:
                future.result()
                with print_lock:
                    print(f"Progress: {completed}/{total} files completed")
            except Exception as e:
                with print_lock:
                    print(f"❌ Error processing {file.name}: {e}")
    
    print("\n✅ All files processed!")

if __name__ == "__main__":
    folder_path = "ai/dataset/CS311"
    clean_json_folder(folder_path)
