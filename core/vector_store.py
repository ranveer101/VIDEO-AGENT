import uuid
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


CHROMA_DIR = str(Path(__file__).resolve().parent.parent / "vector_db")
COLLECTION_PREFIX = "video_mind"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
    )


def new_collection_name() -> str:
    return f"{COLLECTION_PREFIX}_{uuid.uuid4().hex}"


def build_vector_store(transcript: str, collection_name: str | None = None) -> Chroma:
    print("Building isolated vector store")
    collection = collection_name or new_collection_name()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120,
    )
    chunks = splitter.split_text(transcript)
    docs = [
        Document(page_content=chunk, metadata={"chunk_index": i, "collection": collection})
        for i, chunk in enumerate(chunks)
    ]

    return Chroma.from_documents(
        documents=docs,
        embedding=get_embeddings(),
        collection_name=collection,
        persist_directory=CHROMA_DIR,
    )


def load_vector_store(collection_name: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_DIR,
    )


def get_retriever(vector_store: Chroma, k: int = 6):
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )
