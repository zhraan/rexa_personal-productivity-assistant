# ═══════════════════════════════════════════════════════════════════════════════
# ProdiBot — Personal Productivity Assistant
# Streamlit Chatbot dengan RAG & Function Calling
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import os
from dotenv import load_dotenv

# Import modul ProdiBot
from utils.llm import create_client, create_chat_session, send_message, send_message_with_rag
from utils.prompts import WELCOME_MESSAGE
from utils.rag import (
    process_uploaded_pdf, load_preloaded_documents, query_documents,
    is_rag_query, has_documents, get_loaded_docs_info, get_total_chunks,
)
from utils.tools import _ensure_tasks, _ensure_schedules

# Load environment variables
load_dotenv()

# ── 1. Konfigurasi Halaman ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Rixa — Personal Productivity Assistant",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── 2. Custom CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1A1D26 0%, #0E1117 100%);
    }
    .status-card {
        background: rgba(108, 99, 255, 0.1);
        border: 1px solid rgba(108, 99, 255, 0.3);
        border-radius: 10px;
        padding: 12px 16px;
        margin: 8px 0;
    }
    .upload-success {
        background: rgba(0, 200, 83, 0.1);
        border: 1px solid rgba(0, 200, 83, 0.3);
        border-radius: 10px;
        padding: 12px 16px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# ── 3. Sidebar: Pengaturan ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Pengaturan")

    # API Key — dari .env atau input manual
    default_key = os.getenv("GEMINI_API_KEY", "")
    google_api_key = st.text_input(
        "Google AI API Key",
        value=default_key,
        type="password",
        help="Dapatkan API key dari https://aistudio.google.com",
    )

    st.divider()

    # Model selection
    model_id = st.selectbox(
        "Model Gemini",
        ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"],
        index=0,
        help="Pilih model Gemini yang akan digunakan",
    )

    # Temperature
    temperature = st.slider(
        "Temperature",
        min_value=0.0, max_value=1.0, value=0.3, step=0.1,
        help="Semakin tinggi = semakin kreatif, semakin rendah = semakin konsisten",
    )

    st.divider()

    # ── Pre-load Dokumen dari RAG_DOCUMENTS ────────────────────────────────
    if google_api_key and not st.session_state.get("_preloaded_done"):
        with st.spinner("📚 Memuat dokumen pre-loaded..."):
            results = load_preloaded_documents(google_api_key)
            for r in results:
                if "error" in r:
                    st.warning(f"⚠️ {r['error']}")
            st.session_state._preloaded_done = True

    # ── Upload PDF untuk RAG ─────────────────────────────────────────────────
    st.markdown("### 📄 Upload Dokumen (RAG)")
    uploaded_files = st.file_uploader(
        "Upload PDF untuk tanya jawab",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload satu atau lebih file PDF, lalu tanyakan isinya ke Rexa",
    )

    # Proses setiap file yang di-upload
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_key = f"{uploaded_file.name}_{uploaded_file.size}"
            if file_key not in st.session_state.get("_processed_uploads", set()):
                with st.spinner(f"📚 Memproses {uploaded_file.name}..."):
                    result = process_uploaded_pdf(uploaded_file, google_api_key)
                    if "error" in result:
                        st.error(result["error"])
                    elif not result.get("already_loaded"):
                        # Track file yang sudah diproses
                        if "_processed_uploads" not in st.session_state:
                            st.session_state._processed_uploads = set()
                        st.session_state._processed_uploads.add(file_key)

    # Tampilkan semua dokumen yang sudah dimuat
    loaded_docs = get_loaded_docs_info()
    if loaded_docs:
        total_chunks = get_total_chunks()
        st.markdown(f"**📚 {len(loaded_docs)} dokumen dimuat · 🧩 {total_chunks} chunks total**")
        for doc in loaded_docs:
            st.markdown(f"""
            <div class="upload-success">
                ✅ <strong>{doc['name']}</strong><br>
                📄 {doc['pages']} halaman · 🧩 {doc['chunks']} chunks
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── Tombol Reset ─────────────────────────────────────────────────────────
    reset_button = st.button(
        "🔄 Reset Percakapan",
        help="Hapus semua pesan dan mulai dari awal",
        use_container_width=True,
    )

    # ── Tampilkan Tugas Aktif ────────────────────────────────────────────────
    _ensure_tasks()
    _ensure_schedules()

    pending = [t for t in st.session_state.get("tasks", []) if t["status"] == "pending"]
    schedules = st.session_state.get("schedules", [])

    if pending:
        st.divider()
        st.markdown("### 📝 Tugas Pending")
        for t in pending:
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t["priority"], "🟡")
            st.markdown(f"{emoji} {t['task']}")

    if schedules:
        st.divider()
        st.markdown("### 📅 Jadwal")
        for s in schedules:
            st.markdown(f"🕐 **{s['date']}** {s['time']} — {s['event']}")

# ── 4. Validasi API Key ─────────────────────────────────────────────────────
if not google_api_key:
    st.title("💬 Rexa")
    st.caption("Personal Productivity Assistant powered by Gemini AI")
    st.info("Masukkan Google AI API Key di sidebar untuk mulai chat.", icon="🗝️")
    st.stop()

# ── 5. Inisialisasi Gemini Client ────────────────────────────────────────────
needs_reinit = (
    "genai_client" not in st.session_state
    or st.session_state.get("_last_key") != google_api_key
    or st.session_state.get("_last_model") != model_id
    or st.session_state.get("_last_temp") != temperature
)

if needs_reinit:
    try:
        st.session_state.genai_client = create_client(google_api_key)
        st.session_state._last_key = google_api_key
        st.session_state._last_model = model_id
        st.session_state._last_temp = temperature
        st.session_state.pop("chat", None)
    except Exception as e:
        st.error(f"API Key tidak valid: {e}")
        st.stop()

# ── 6. Inisialisasi Chat Session ─────────────────────────────────────────────
if "chat" not in st.session_state:
    st.session_state.chat = create_chat_session(
        st.session_state.genai_client,
        model_id=model_id,
        temperature=temperature,
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

# ── 7. Handle Reset ─────────────────────────────────────────────────────────
if reset_button:
    for key in ["chat", "messages", "tasks", "schedules",
                "_rag_texts", "_rag_embeddings", "_rag_api_key",
                "_rag_sources", "_rag_doc_info",
                "_processed_uploads", "_preloaded_done"]:
        st.session_state.pop(key, None)
    st.rerun()

# ── 8. Header ────────────────────────────────────────────────────────────────
st.title("💬 Rexa")
st.caption("Personal Productivity Assistant powered by Gemini AI — RAG & Function Calling")

# ── 9. Welcome Message ──────────────────────────────────────────────────────
if not st.session_state.messages:
    with st.chat_message("assistant", avatar="💬"):
        st.markdown(WELCOME_MESSAGE)

# ── 10. Tampilkan Riwayat Percakapan ─────────────────────────────────────────
for msg in st.session_state.messages:
    avatar = "💬" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ── 11. Input & Respons ─────────────────────────────────────────────────────
prompt = st.chat_input("Ketik pesanmu di sini... (cth: 'tambah tugas belajar Python')")

if prompt:
    # Tambah pesan user ke riwayat
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Tentukan apakah perlu RAG
    use_rag = is_rag_query(prompt, has_documents())

    with st.chat_message("assistant", avatar="💬"):
        with st.spinner("Sedang berpikir..."):
            try:
                if use_rag:
                    # Ambil konteks dari dokumen
                    rag_context = query_documents(prompt)
                    answer = send_message_with_rag(
                        st.session_state.chat, prompt, rag_context
                    )
                else:
                    answer = send_message(st.session_state.chat, prompt)
            except Exception as e:
                answer = f"⚠️ Terjadi error: {e}"

        st.markdown(answer)

    # Simpan respons ke riwayat
    st.session_state.messages.append({"role": "assistant", "content": answer})

    # Rerun untuk update sidebar (tugas/jadwal baru)
    st.rerun()
