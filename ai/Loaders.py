from pathlib import Path
import json
from typing import List

from langchain_core.documents import Document
from langchain_community.document_loaders import UnstructuredMarkdownLoader


def _read_markdown(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def load_markdown(data_dir: str = "ai/dataset") -> List[Document]:
    base = Path(data_dir)
    docs: List[Document] = []
    for file_path in sorted(base.rglob("*.md")):
        source = str(file_path)
        docs.append(Document(page_content=_read_markdown(file_path), metadata={"source": source}))
        loader = UnstructuredMarkdownLoader(str(file_path), mode="elements")
        elements = list(loader.load())
        for idx, element in enumerate(elements):
            raw_content = element.page_content or ""
            content = raw_content.strip()
            if not content:
                continue
            metadata = dict(element.metadata or {})
            metadata["source"] = source
            category = metadata.get("category") or metadata.get("element_type") or metadata.get("type")
            if isinstance(category, str) and category.lower() == "table":
                metadata["is_table"] = True
                if idx + 1 < len(elements):
                    next_piece = (elements[idx + 1].page_content or "").strip()
                    if next_piece.startswith("{") or next_piece.startswith("["):
                        try:
                            metadata["table_json"] = json.loads(next_piece)
                        except Exception:
                            pass
                docs.append(Document(page_content=raw_content, metadata=metadata))
    return docs
