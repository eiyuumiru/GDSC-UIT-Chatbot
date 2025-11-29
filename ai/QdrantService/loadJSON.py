import json
from langchain_core.documents import Document
from pathlib import Path
from typing import List

def load_json(data_dir: str) -> List[Document]:
    """
    Load documents from JSON files, extracting text and metadata.
    
    Args:
        data_dir: Directory containing JSON files
        
    Returns:
        List of Document objects with text and metadata
    """
    documents = []
    data_path = Path(data_dir)
    
    # Find all JSON files in directory
    json_files = list(data_path.rglob("*.json"))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Process each element in the JSON array
            for element in data:
                if isinstance(element, dict) and 'text' in element:
                    # Extract required fields
                    text = element.get('text', '')
                    element_id = element.get('element_id', '')
                    metadata = element.get('metadata', {})
                    page_number = metadata.get('page_number', None)
                    filename = metadata.get('filename', None)

                    # Create document with required metadata
                    doc = Document(
                        page_content=text,
                        metadata={
                            'filename': filename,
                            'page_number': page_number,
                            'element_id': element_id
                        }
                    )
                    
                    documents.append(doc)
                    
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            print(f"Error processing file {json_file}: {e}")
            continue
    
    return documents

if __name__ == "__main__":
    data_directory = "ai/dataset/CS311"
    docs = load_json(data_directory)
    print(docs[:5]) 