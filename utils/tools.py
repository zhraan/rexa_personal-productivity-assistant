"""
Rexa — Function Calling Tools

Definisi semua tool (fungsi) yang dapat dipanggil oleh model Gemini
melalui fitur Automatic Function Calling.

Pola ini mengikuti contoh dari notebook AI Agents (BaristaBot & SQL Agent):
- Setiap tool adalah fungsi Python biasa dengan docstring yang jelas
- Model membaca docstring untuk memahami kapan dan bagaimana memanggil tool
- SDK menangani loop function calling secara otomatis
"""

import streamlit as st
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Helper: Pastikan session state terisi
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_tasks():
    """Pastikan st.session_state.tasks ada."""
    if "tasks" not in st.session_state:
        st.session_state.tasks = []


def _ensure_schedules():
    """Pastikan st.session_state.schedules ada."""
    if "schedules" not in st.session_state:
        st.session_state.schedules = []


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 1: Task Management
# ═══════════════════════════════════════════════════════════════════════════════

def add_task(task: str, priority: str = "medium", due_date: str = "") -> str:
    """Menambahkan tugas baru ke daftar tugas user.

    Args:
        task: Deskripsi tugas yang akan ditambahkan.
        priority: Tingkat prioritas tugas (high, medium, low). Default: medium.
        due_date: Tanggal deadline tugas dalam format YYYY-MM-DD. Kosongkan jika tidak ada deadline.

    Returns:
        Pesan konfirmasi bahwa tugas berhasil ditambahkan beserta detailnya.
    """
    _ensure_tasks()

    task_id = len(st.session_state.tasks) + 1
    new_task = {
        "id": task_id,
        "task": task,
        "priority": priority.lower(),
        "due_date": due_date if due_date else "Tidak ada deadline",
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    st.session_state.tasks.append(new_task)

    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority.lower(), "🟡")
    print(f"[TOOL] add_task: '{task}' (priority: {priority}, due: {due_date})")

    return (
        f"✅ Tugas berhasil ditambahkan!\n"
        f"- **ID**: {task_id}\n"
        f"- **Tugas**: {task}\n"
        f"- **Prioritas**: {priority_emoji} {priority.capitalize()}\n"
        f"- **Deadline**: {due_date if due_date else 'Tidak ada'}\n"
    )


def list_tasks() -> str:
    """Menampilkan semua tugas yang ada di daftar tugas user.

    Returns:
        Daftar semua tugas beserta status, prioritas, dan deadline-nya.
        Mengembalikan pesan khusus jika belum ada tugas.
    """
    _ensure_tasks()

    if not st.session_state.tasks:
        return "📋 Daftar tugas masih kosong. Silakan tambahkan tugas baru!"

    print(f"[TOOL] list_tasks: {len(st.session_state.tasks)} tugas ditemukan")

    result = "📋 **Daftar Tugas Anda:**\n\n"
    result += "| No | Tugas | Prioritas | Deadline | Status |\n"
    result += "|:---:|:---|:---:|:---:|:---:|\n"

    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    status_emoji = {"pending": "⏳", "done": "✅"}

    for t in st.session_state.tasks:
        p_emoji = priority_emoji.get(t["priority"], "🟡")
        s_emoji = status_emoji.get(t["status"], "⏳")
        result += f"| {t['id']} | {t['task']} | {p_emoji} {t['priority'].capitalize()} | {t['due_date']} | {s_emoji} {t['status'].capitalize()} |\n"

    # Statistik
    total = len(st.session_state.tasks)
    done = sum(1 for t in st.session_state.tasks if t["status"] == "done")
    pending = total - done
    result += f"\n📊 **Total**: {total} tugas | ✅ Selesai: {done} | ⏳ Pending: {pending}"

    return result


def complete_task(task_id: int) -> str:
    """Menandai sebuah tugas sebagai selesai berdasarkan ID tugas.

    Args:
        task_id: Nomor ID tugas yang akan ditandai selesai.

    Returns:
        Pesan konfirmasi bahwa tugas berhasil ditandai selesai,
        atau pesan error jika tugas tidak ditemukan.
    """
    _ensure_tasks()

    for task in st.session_state.tasks:
        if task["id"] == task_id:
            if task["status"] == "done":
                return f"ℹ️ Tugas #{task_id} ('{task['task']}') sudah selesai sebelumnya."
            task["status"] = "done"
            print(f"[TOOL] complete_task: #{task_id} '{task['task']}'")
            return f"🎉 Tugas #{task_id} ('{task['task']}') berhasil ditandai **selesai**! Kerja bagus! 💪"

    return f"❌ Tugas dengan ID #{task_id} tidak ditemukan. Gunakan `list_tasks` untuk melihat daftar tugas."


def delete_task(task_id: int) -> str:
    """Menghapus sebuah tugas dari daftar berdasarkan ID tugas.

    Args:
        task_id: Nomor ID tugas yang akan dihapus.

    Returns:
        Pesan konfirmasi bahwa tugas berhasil dihapus,
        atau pesan error jika tugas tidak ditemukan.
    """
    _ensure_tasks()

    for i, task in enumerate(st.session_state.tasks):
        if task["id"] == task_id:
            removed = st.session_state.tasks.pop(i)
            print(f"[TOOL] delete_task: #{task_id} '{removed['task']}'")
            return f"🗑️ Tugas #{task_id} ('{removed['task']}') berhasil dihapus."

    return f"❌ Tugas dengan ID #{task_id} tidak ditemukan."


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 2: Schedule / Jadwal
# ═══════════════════════════════════════════════════════════════════════════════

def add_schedule(event: str, date: str, time: str = "") -> str:
    """Menambahkan jadwal atau acara baru ke kalender user.

    Args:
        event: Nama atau deskripsi acara/kegiatan.
        date: Tanggal acara dalam format YYYY-MM-DD.
        time: Waktu acara dalam format HH:MM. Kosongkan jika seharian penuh.

    Returns:
        Pesan konfirmasi bahwa jadwal berhasil ditambahkan.
    """
    _ensure_schedules()

    schedule_id = len(st.session_state.schedules) + 1
    new_schedule = {
        "id": schedule_id,
        "event": event,
        "date": date,
        "time": time if time else "Sepanjang hari",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    st.session_state.schedules.append(new_schedule)

    print(f"[TOOL] add_schedule: '{event}' on {date} at {time}")

    return (
        f"📅 Jadwal berhasil ditambahkan!\n"
        f"- **ID**: {schedule_id}\n"
        f"- **Acara**: {event}\n"
        f"- **Tanggal**: {date}\n"
        f"- **Waktu**: {time if time else 'Sepanjang hari'}\n"
    )


def list_schedules() -> str:
    """Menampilkan semua jadwal dan acara yang sudah dicatat.

    Returns:
        Daftar semua jadwal beserta tanggal dan waktunya.
        Mengembalikan pesan khusus jika belum ada jadwal.
    """
    _ensure_schedules()

    if not st.session_state.schedules:
        return "📅 Belum ada jadwal yang dicatat. Silakan tambahkan jadwal baru!"

    print(f"[TOOL] list_schedules: {len(st.session_state.schedules)} jadwal ditemukan")

    result = "📅 **Jadwal Anda:**\n\n"
    result += "| No | Acara | Tanggal | Waktu |\n"
    result += "|:---:|:---|:---:|:---:|\n"

    for s in st.session_state.schedules:
        result += f"| {s['id']} | {s['event']} | {s['date']} | {s['time']} |\n"

    return result


def delete_schedule(schedule_id: int) -> str:
    """Menghapus sebuah jadwal dari daftar berdasarkan ID jadwal.

    Args:
        schedule_id: Nomor ID jadwal yang akan dihapus.

    Returns:
        Pesan konfirmasi bahwa jadwal berhasil dihapus,
        atau pesan error jika jadwal tidak ditemukan.
    """
    _ensure_schedules()

    for i, schedule in enumerate(st.session_state.schedules):
        if schedule["id"] == schedule_id:
            removed = st.session_state.schedules.pop(i)
            print(f"[TOOL] delete_schedule: #{schedule_id} '{removed['event']}'")
            return f"🗑️ Jadwal #{schedule_id} ('{removed['event']}') berhasil dihapus."

    return f"❌ Jadwal dengan ID #{schedule_id} tidak ditemukan."


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 3: Daily Summary
# ═══════════════════════════════════════════════════════════════════════════════

def get_daily_summary() -> str:
    """Menampilkan ringkasan harian yang mencakup semua tugas pending dan jadwal hari ini.

    Returns:
        Ringkasan lengkap berisi tugas-tugas yang belum selesai dan jadwal hari ini.
    """
    _ensure_tasks()
    _ensure_schedules()

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%A, %d %B %Y")

    print(f"[TOOL] get_daily_summary: tanggal {today}")

    result = f"📊 **Ringkasan Harian — {now}**\n\n"

    # Tugas pending
    pending_tasks = [t for t in st.session_state.tasks if t["status"] == "pending"]
    result += f"### 📝 Tugas Pending ({len(pending_tasks)})\n"
    if pending_tasks:
        for t in pending_tasks:
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t["priority"], "🟡")
            overdue = ""
            if t["due_date"] != "Tidak ada deadline" and t["due_date"] < today:
                overdue = " ⚠️ **TERLAMBAT**"
            result += f"- {priority_emoji} {t['task']} (deadline: {t['due_date']}){overdue}\n"
    else:
        result += "- 🎉 Semua tugas sudah selesai!\n"

    # Tugas selesai hari ini
    done_tasks = [t for t in st.session_state.tasks if t["status"] == "done"]
    result += f"\n### ✅ Tugas Selesai ({len(done_tasks)})\n"
    if done_tasks:
        for t in done_tasks:
            result += f"- ~~{t['task']}~~\n"
    else:
        result += "- Belum ada tugas yang diselesaikan\n"

    # Jadwal hari ini
    today_schedules = [s for s in st.session_state.schedules if s["date"] == today]
    result += f"\n### 📅 Jadwal Hari Ini ({len(today_schedules)})\n"
    if today_schedules:
        for s in today_schedules:
            result += f"- 🕐 **{s['time']}** — {s['event']}\n"
    else:
        result += "- Tidak ada jadwal untuk hari ini\n"

    # Upcoming
    upcoming = [s for s in st.session_state.schedules if s["date"] > today]
    if upcoming:
        upcoming_sorted = sorted(upcoming, key=lambda x: x["date"])[:3]
        result += f"\n### 🔮 Jadwal Mendatang\n"
        for s in upcoming_sorted:
            result += f"- 📅 **{s['date']}** {s['time']} — {s['event']}\n"

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 4: Productivity Tips
# ═══════════════════════════════════════════════════════════════════════════════

def get_productivity_tip() -> str:
    """Memberikan tips dan saran produktivitas secara acak untuk membantu user
    meningkatkan efisiensi kerja.

    Returns:
        Sebuah tips produktivitas yang bermanfaat.
    """
    import random

    tips = [
        "🎯 **Teknik Pomodoro**: Bekerja fokus selama 25 menit, lalu istirahat 5 menit. Setelah 4 siklus, ambil istirahat panjang 15-30 menit.",
        "📋 **Eat That Frog**: Kerjakan tugas yang paling sulit atau paling penting di pagi hari saat energi masih penuh.",
        "🧹 **Two-Minute Rule**: Jika sebuah tugas bisa diselesaikan dalam 2 menit atau kurang, kerjakan langsung — jangan ditunda!",
        "📱 **Digital Detox**: Matikan notifikasi non-esensial selama jam kerja fokus. Cek pesan hanya pada waktu yang ditentukan.",
        "🎯 **Eisenhower Matrix**: Kategorikan tugas berdasarkan urgensi dan kepentingan. Fokus pada yang penting, bukan yang mendesak saja.",
        "🧘 **Mindful Break**: Luangkan 5 menit setiap jam untuk stretching atau meditasi singkat. Ini membantu menjaga fokus dan energi.",
        "📝 **Brain Dump**: Tulis semua yang ada di pikiran sebelum mulai bekerja. Ini membebaskan working memory dan mengurangi stres.",
        "🌅 **Morning Routine**: Bangun lebih awal dan lakukan ritual pagi (olahraga, meditasi, journaling) sebelum mulai bekerja.",
        "📊 **Weekly Review**: Setiap Minggu, review pencapaian minggu ini dan rencanakan prioritas minggu depan.",
        "💤 **Sleep Hygiene**: Tidur cukup 7-8 jam. Produktivitas yang sesungguhnya dimulai dari kualitas tidur yang baik.",
        "🔄 **Batch Processing**: Kelompokkan tugas-tugas sejenis dan kerjakan sekaligus. Misalnya, balas semua email di satu waktu.",
        "🎵 **Focus Music**: Gunakan musik ambient atau lo-fi saat bekerja untuk meningkatkan konsentrasi.",
    ]

    tip = random.choice(tips)
    print(f"[TOOL] get_productivity_tip")

    return f"💡 **Tips Produktivitas Hari Ini:**\n\n{tip}"


# ═══════════════════════════════════════════════════════════════════════════════
# Get All Tools — untuk didaftarkan ke Gemini
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_tools():
    """
    Mengembalikan list semua tool yang tersedia untuk Function Calling.
    List ini akan didaftarkan ke Gemini saat membuat chat session.
    """
    return [
        add_task,
        list_tasks,
        complete_task,
        delete_task,
        add_schedule,
        list_schedules,
        delete_schedule,
        get_daily_summary,
        get_productivity_tip,
    ]
