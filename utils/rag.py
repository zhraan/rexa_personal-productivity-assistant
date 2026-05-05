"""
Rexa — RAG Pipeline (Retrieval-Augmented Generation)

Pipeline untuk memproses dokumen PDF:
1. Membaca PDF → Ekstrak teks
2. Chunking → Potong teks menjadi bagian-bagian kecil
3. Embedding → Ubah teks menjadi vector (google-genai SDK)
4. Simpan di memory (numpy cosine similarity)
5. Retrieval → Cari chunk yang relevan dengan pertanyaan user

Mendukung dua cara menambah dokumen:
- Upload file via Streamlit file_uploader (multi-file)
- Pre-load file dari path lokal (hardcoded di RAG_DOCUMENTS)

Note:
- Menggunakan google-genai SDK langsung untuk embedding
  (langchain-google-genai v4.2.2 punya bug embed_documents)
"""

import os
import tempfile
import numpy as np
import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from google import genai


# ═══════════════════════════════════════════════════════════════════════════════
# KONFIGURASI: Dokumen Pre-loaded (hardcoded)
# Tambahkan path file PDF di sini agar otomatis dimuat saat app dijalankan.
# Gunakan path relatif terhadap root project atau path absolut.
# ═══════════════════════════════════════════════════════════════════════════════

RAG_DOCUMENTS = [
    "RAG_dokumen/CV_Zahran Fikri.pdf",
    # Tambahkan file lain di sini, contoh:
    # "RAG_dokumen/laporan_proyek.pdf",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Helper: Embedding & Similarity
# ═══════════════════════════════════════════════════════════════════════════════

def _embed_texts(api_key: str, texts: list[str]) -> list[list[float]]:
    """
    Embed teks menggunakan google-genai SDK langsung.

    Args:
        api_key: Google AI API Key
        texts: List of strings untuk di-embed

    Returns:
        List of embedding vectors (list of floats)
    """
    import time
    import re
    client = genai.Client(api_key=api_key)
    all_embeddings = []
    
    for i, text in enumerate(texts):
        retries = 0
        while retries < 3:
            try:
                result = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=text,
                    config={"output_dimensionality": 768},
                )
                all_embeddings.append(result.embeddings[0].values)
                break # Berhasil
            except Exception as e:
                error_str = str(e)
                if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
                    match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_str)
                    wait_time = float(match.group(1)) + 1.0 if match else 15.0
                    retries += 1
                    if retries >= 3:
                        print(f"[RAG] Gagal embed setelah 3x retry: {e}")
                        raise e
                    print(f"[RAG] Rate limit (429) pada chunk {i}. Menunggu {wait_time:.1f}s sebelum retry ({retries}/3)...")
                    time.sleep(wait_time)
                else:
                    raise e
                    
    return all_embeddings


def _cosine_similarity(query_vec, doc_vecs):
    """Hitung cosine similarity antara query vector dan semua document vectors."""
    query = np.array(query_vec)
    docs = np.array(doc_vecs)

    query_norm = query / (np.linalg.norm(query) + 1e-10)
    docs_norm = docs / (np.linalg.norm(docs, axis=1, keepdims=True) + 1e-10)

    similarities = docs_norm @ query_norm
    return similarities


def _init_rag_store():
    """Inisialisasi RAG store di session state jika belum ada."""
    if "_rag_texts" not in st.session_state:
        st.session_state._rag_texts = []
    if "_rag_embeddings" not in st.session_state:
        st.session_state._rag_embeddings = []
    if "_rag_sources" not in st.session_state:
        st.session_state._rag_sources = []  # Track nama file yang sudah diproses
    if "_rag_doc_info" not in st.session_state:
        st.session_state._rag_doc_info = []  # Info per dokumen


def _add_to_store(texts, embeddings, filename, num_pages, num_chunks):
    """Tambahkan texts dan embeddings ke RAG store (akumulasi, bukan replace)."""
    _init_rag_store()
    st.session_state._rag_texts.extend(texts)
    st.session_state._rag_embeddings.extend(embeddings)
    st.session_state._rag_sources.append(filename)
    st.session_state._rag_doc_info.append({
        "name": filename,
        "pages": num_pages,
        "chunks": num_chunks,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Proses PDF dari Upload (Streamlit file_uploader)
# ═══════════════════════════════════════════════════════════════════════════════

def process_uploaded_pdf(uploaded_file, api_key: str) -> dict:
    """
    Memproses file PDF yang di-upload via Streamlit: baca → chunk → embed → akumulasi.

    Args:
        uploaded_file: File PDF dari st.file_uploader
        api_key: Google AI API Key untuk embedding model

    Returns:
        Dictionary berisi num_chunks, num_pages, atau 'error'.
    """
    _init_rag_store()

    # Cek apakah file ini sudah diproses
    if uploaded_file.name in st.session_state._rag_sources:
        return {"already_loaded": True, "name": uploaded_file.name}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

    try:
        return _process_pdf_path(tmp_path, uploaded_file.name, api_key)
    finally:
        os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════════════
# Proses PDF dari Path Lokal (hardcoded)
# ═══════════════════════════════════════════════════════════════════════════════

def process_local_pdf(file_path: str, api_key: str) -> dict:
    """
    Memproses file PDF dari path lokal: baca → chunk → embed → akumulasi.

    Args:
        file_path: Path ke file PDF
        api_key: Google AI API Key untuk embedding model

    Returns:
        Dictionary berisi num_chunks, num_pages, atau 'error'.
    """
    _init_rag_store()

    filename = os.path.basename(file_path)

    # Cek apakah file ini sudah diproses
    if filename in st.session_state._rag_sources:
        return {"already_loaded": True, "name": filename}

    if not os.path.exists(file_path):
        return {"error": f"File tidak ditemukan: {file_path}"}

    return _process_pdf_path(file_path, filename, api_key)


def load_preloaded_documents(api_key: str) -> list[dict]:
    """
    Memuat semua dokumen dari RAG_DOCUMENTS yang belum diproses.

    Args:
        api_key: Google AI API Key

    Returns:
        List of result dictionaries untuk setiap dokumen
    """
    results = []
    for path in RAG_DOCUMENTS:
        if os.path.exists(path):
            result = process_local_pdf(path, api_key)
            result["path"] = path
            results.append(result)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Core: Proses PDF (shared logic)
# ═══════════════════════════════════════════════════════════════════════════════

def _process_pdf_path(pdf_path: str, filename: str, api_key: str) -> dict:
    """
    Core logic: baca PDF → chunk → embed → tambah ke store.

    Args:
        pdf_path: Path ke file PDF
        filename: Nama file untuk tracking
        api_key: Google AI API Key

    Returns:
        Dictionary berisi num_chunks, num_pages, atau 'error'.
    """
    loader = PyPDFLoader(pdf_path)
    pages = loader.load_and_split()
    num_pages = len(pages)

    if num_pages == 0:
        return {"error": f"PDF '{filename}' kosong atau tidak bisa dibaca."}

    # Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = text_splitter.split_documents(pages)

    if not chunks:
        return {"error": f"Tidak ada teks yang bisa diekstrak dari '{filename}'."}

    # Embedding
    texts = [doc.page_content for doc in chunks]
    all_embeddings = _embed_texts(api_key, texts)

    # Akumulasi ke store
    _add_to_store(texts, all_embeddings, filename, num_pages, len(chunks))

    # Simpan API key untuk query nanti
    st.session_state._rag_api_key = api_key

    return {
        "name": filename,
        "num_chunks": len(chunks),
        "num_pages": num_pages,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Query & Retrieval
# ═══════════════════════════════════════════════════════════════════════════════

def query_documents(question: str, top_k: int = 5) -> str:
    """
    Mencari chunk dokumen yang paling relevan dengan pertanyaan user
    menggunakan cosine similarity.

    Args:
        question: Pertanyaan user
        top_k: Jumlah chunk teratas yang diambil

    Returns:
        String berisi gabungan chunk-chunk yang relevan
    """
    try:
        texts = st.session_state.get("_rag_texts")
        embeddings = st.session_state.get("_rag_embeddings")
        api_key = st.session_state.get("_rag_api_key")

        if not texts or not embeddings or not api_key:
            return ""

        query_embedding = _embed_texts(api_key, [question])[0]
        similarities = _cosine_similarity(query_embedding, embeddings)

        top_indices = np.argsort(similarities)[::-1][:top_k]
        relevant_chunks = [texts[i] for i in top_indices]

        return "\n\n---\n\n".join(relevant_chunks)

    except Exception as e:
        print(f"[RAG] Error saat query: {e}")
        return ""


def get_loaded_docs_info() -> list[dict]:
    """Mengembalikan info semua dokumen yang sudah dimuat."""
    _init_rag_store()
    return st.session_state._rag_doc_info


def get_total_chunks() -> int:
    """Mengembalikan total jumlah chunks di store."""
    _init_rag_store()
    return len(st.session_state._rag_texts)


def has_documents() -> bool:
    """Cek apakah ada dokumen yang sudah dimuat."""
    _init_rag_store()
    return len(st.session_state._rag_texts) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Utilitas Lainnya
# ═══════════════════════════════════════════════════════════════════════════════

def format_docs(docs) -> str:
    """Menggabungkan list Document menjadi satu string konteks."""
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def is_rag_query(message: str, has_docs: bool) -> bool:
    """
    Menentukan apakah pesan user kemungkinan adalah pertanyaan tentang dokumen.

    Args:
        message: Pesan dari user
        has_docs: Apakah ada dokumen yang sudah dimuat

    Returns:
        True jika pesan kemungkinan pertanyaan tentang dokumen
    """
    if not has_docs:
        return False

    doc_keywords = [
        "dokumen", "document", "pdf", "file", "upload",
        "apa isi", "apa yang", "jelaskan", "rangkum", "ringkas",
        "menurut", "berdasarkan", "sebutkan", "dalam dokumen",
        "di dokumen", "tentang apa", "topik", "summary", "summarize",
        "explain", "what", "describe", "content",
    ]

    message_lower = message.lower()
    return any(keyword in message_lower for keyword in doc_keywords)
