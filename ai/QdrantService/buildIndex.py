import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ai.QdrantService.QdrantBase import QdrantBase
from ai.QdrantService.loadJSON import load_json
import dotenv

dotenv.load_dotenv()

def test_query(qdrant_service: QdrantBase, query: str, k: int = 5):
    """Test search functionality with a query"""
    print(f"\n{'='*80}")
    print(f"Query: {query}")
    print(f"{'='*80}\n")
    
    results = qdrant_service.search(query=query, k=k)
    
    print(f"Found {len(results)} results:\n")
    for idx, doc in enumerate(results, 1):
        print(f"Result {idx}:")
        # print(f"Content: {doc.page_content[:200]}..." if len(doc.page_content) > 200 else f"Content: {doc.page_content}")
        print(f"Content: {doc.page_content}")
        print(f"Metadata: {doc.metadata}")
        print("-" * 80)

if __name__ == "__main__":
    API_KEY = os.getenv("QDRANT_API_KEY")
    URL = os.getenv("QDRANT_URL")
    if not API_KEY or not URL:
        raise ValueError("QDRANT_API_KEY and QDRANT_URL must be set in environment variables.")

    # Example usage
    docs = load_json("ai/dataset/CS311")
    qdrant_service = QdrantBase(api_key=API_KEY, url=URL)
    try:
        qdrant_service.delete_all_points()
        qdrant_service.build_index(documents=docs)
        print("Index built successfully.")
        
        # Test queries
        # test_query(qdrant_service, "Khoa học máy tính là gì?")
        # test_query(qdrant_service, "Điều kiện tốt nghiệp", k=3)
        
    except Exception as e:
        print(f"Failed to build index: {e}")

    # test_query(qdrant_service, "Môn toán cho Khoa học máy tính do ai dạy?", k=2)