"""
Rexa — Gemini LLM Client & Chat Session Setup

Modul ini menangani inisialisasi client Gemini dan pembuatan chat session
menggunakan SDK google-genai (sesuai pola dari Gemini Part 2 & Streamlit notebook).
"""

from google import genai
from google.genai import types
from utils.prompts import SYSTEM_INSTRUCTION
from utils.tools import get_all_tools


def create_client(api_key: str) -> genai.Client:
    """
    Membuat Gemini client baru dengan API key yang diberikan.

    Args:
        api_key: Google AI API Key dari aistudio.google.com

    Returns:
        genai.Client yang sudah terinisialisasi
    """
    return genai.Client(api_key=api_key)


def create_chat_session(client: genai.Client, model_id: str = "gemini-2.5-flash",
                        temperature: float = 0.3):
    """
    Membuat chat session baru dengan system instruction dan tools.

    Chat session ini menyimpan konteks percakapan sehingga model
    dapat mengingat pesan-pesan sebelumnya.

    Args:
        client: Gemini client yang sudah terinisialisasi
        model_id: ID model Gemini yang digunakan
        temperature: Tingkat kreativitas respons (0.0 - 1.0)

    Returns:
        Chat session object
    """
    chat = client.chats.create(
        model=model_id,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=temperature,
            top_p=0.95,
            top_k=20,
            tools=get_all_tools(),
        ),
    )
    return chat


def send_message(chat, message: str, max_retries: int = 3) -> str:
    """
    Mengirim pesan ke chat session dan mendapatkan respons.

    Fungsi ini menangani automatic function calling — SDK akan otomatis
    mengeksekusi tool yang dipanggil oleh model.
    Juga dilengkapi dengan auto-retry jika terkena Rate Limit (429).

    Args:
        chat: Chat session object
        message: Pesan dari user
        max_retries: Jumlah maksimal percobaan ulang jika kena limit

    Returns:
        Teks respons dari model
    """
    import time
    import re

    retries = 0
    while retries < max_retries:
        try:
            response = chat.send_message(message)

            if hasattr(response, "text") and response.text:
                return response.text
            else:
                return str(response)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
                # Coba cari waktu tunggu dari pesan error (contoh: "retry in 17.5s")
                match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_str)
                if match:
                    wait_time = float(match.group(1)) + 1.0 # Tambah 1 detik untuk aman
                else:
                    wait_time = 15.0 # Default tunggu 15 detik

                retries += 1
                if retries >= max_retries:
                    return f"⚠️ Terjadi error: Kuota API habis (429). Mohon tunggu beberapa saat dan coba lagi."
                
                print(f"[Rate Limit] Menunggu {wait_time:.1f} detik sebelum mencoba lagi ({retries}/{max_retries})...")
                time.sleep(wait_time)
            else:
                return f"⚠️ Terjadi error: {error_str}"


def send_message_with_rag(chat, user_message: str, rag_context: str) -> str:
    """
    Mengirim pesan ke chat session dengan konteks RAG.

    Konteks dari dokumen yang di-upload digabungkan dengan pertanyaan user
    sebelum dikirim ke model.

    Args:
        chat: Chat session object
        user_message: Pesan/pertanyaan dari user
        rag_context: Konteks dokumen yang relevan dari RAG pipeline

    Returns:
        Teks respons dari model
    """
    from utils.prompts import RAG_CONTEXT_TEMPLATE

    augmented_message = RAG_CONTEXT_TEMPLATE.format(
        context=rag_context,
        question=user_message
    )

    return send_message(chat, augmented_message)
