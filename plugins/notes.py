"""
Chhiti Notes Plugin

Voice examples:
- "Chhiti, save a note: Buy a new keyboard"
- "Chhiti, remember that my DBMS exam is on Monday"
- "Chhiti, show my notes"
- "Chhiti, search my notes for DBMS"
- "Chhiti, delete note 2"
- "Chhiti, clear all notes"
"""

from pathlib import Path
import json
from datetime import datetime


# ---------------------------------------------------------
# Storage
# ---------------------------------------------------------

# Project root = parent of plugins/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
NOTES_FILE = DATA_DIR / "notes.json"


def _ensure_storage():
    """Create notes storage if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not NOTES_FILE.exists():
        NOTES_FILE.write_text(
            "[]",
            encoding="utf-8"
        )


def _load_notes():
    """Load notes from local JSON file."""
    _ensure_storage()

    try:
        data = json.loads(
            NOTES_FILE.read_text(encoding="utf-8")
        )

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []


def _save_notes(notes):
    """Save notes to local JSON file."""
    _ensure_storage()

    NOTES_FILE.write_text(
        json.dumps(
            notes,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ---------------------------------------------------------
# Plugin definition
# ---------------------------------------------------------

PLUGIN = {
    "name": "notes",
    "description": (
        "Manage Chhiti's personal notes. "
        "Use this plugin when the user explicitly asks to save, "
        "remember, show, list, search, delete, or clear a note. "
        "Examples include 'save a note', 'remember this', "
        "'show my notes', 'search my notes', or 'delete note 2'. "
        "Do not use this for scheduled reminders; use the reminder "
        "tool instead."
    ),

    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Operation to perform: "
                    "add, list, search, delete, or clear."
                ),
            },

            "note": {
                "type": "STRING",
                "description": (
                    "The note text to save. Required for add."
                ),
            },

            "query": {
                "type": "STRING",
                "description": (
                    "Text to search for inside saved notes. "
                    "Required for search."
                ),
            },

            "note_id": {
                "type": "STRING",
                "description": (
                    "ID of the note to delete."
                ),
            },
        },

        "required": ["action"],
    },
}


# ---------------------------------------------------------
# Plugin runner
# ---------------------------------------------------------

def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    Execute the notes plugin.

    parameters:
        Gemini extracted arguments.

    player:
        JarvisUI instance. Optional.

    session_memory:
        Reserved for future use.

    Returns:
        Short natural-language response for Chhiti.
    """

    try:
        action = str(
            parameters.get("action", "")
        ).strip().lower()

        # -------------------------------------------------
        # ADD NOTE
        # -------------------------------------------------

        if action in ("add", "save", "remember", "create"):
            note_text = str(
                parameters.get("note", "")
            ).strip()

            if not note_text:
                return "Boss, please tell me what you want me to save."

            notes = _load_notes()

            # Generate simple numeric ID
            next_id = 1

            if notes:
                try:
                    next_id = max(
                        int(item.get("id", 0))
                        for item in notes
                    ) + 1
                except Exception:
                    next_id = len(notes) + 1

            new_note = {
                "id": str(next_id),
                "text": note_text,
                "created_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }

            notes.append(new_note)

            _save_notes(notes)

            result = (
                f"Boss, note {next_id} save kar diya."
            )

        # -------------------------------------------------
        # LIST NOTES
        # -------------------------------------------------

        elif action in ("list", "show", "all"):
            notes = _load_notes()

            if not notes:
                result = "Boss, abhi koi notes saved nahi hain."

            else:
                result = f"Boss, aapke {len(notes)} notes hain:\n"

                for item in notes:
                    result += (
                        f"Note {item.get('id')}: "
                        f"{item.get('text')}\n"
                    )

        # -------------------------------------------------
        # SEARCH NOTES
        # -------------------------------------------------

        elif action in ("search", "find"):
            query = str(
                parameters.get("query", "")
            ).strip().lower()

            if not query:
                return "Boss, batao kis note ko search karna hai."

            notes = _load_notes()

            matches = [
                item
                for item in notes
                if query in item.get("text", "").lower()
            ]

            if not matches:
                result = (
                    f"Boss, '{query}' se related koi note nahi mila."
                )

            else:
                result = (
                    f"Boss, {len(matches)} matching note mile:\n"
                )

                for item in matches:
                    result += (
                        f"Note {item.get('id')}: "
                        f"{item.get('text')}\n"
                    )

        # -------------------------------------------------
        # DELETE NOTE
        # -------------------------------------------------

        elif action in ("delete", "remove"):
            note_id = str(
                parameters.get("note_id", "")
            ).strip()

            if not note_id:
                return "Boss, batao kaunsa note delete karna hai."

            notes = _load_notes()

            remaining = [
                item
                for item in notes
                if str(item.get("id")) != note_id
            ]

            if len(remaining) == len(notes):
                result = (
                    f"Boss, note {note_id} nahi mila."
                )

            else:
                _save_notes(remaining)

                result = (
                    f"Boss, note {note_id} delete kar diya."
                )

        # -------------------------------------------------
        # CLEAR ALL NOTES
        # -------------------------------------------------

        elif action in ("clear", "clear_all", "delete_all"):
            notes = _load_notes()

            if not notes:
                result = "Boss, delete karne ke liye koi note nahi hai."

            else:
                _save_notes([])

                result = (
                    f"Boss, {len(notes)} notes delete kar diye."
                )

        # -------------------------------------------------
        # UNKNOWN ACTION
        # -------------------------------------------------

        else:
            result = (
                f"Boss, notes plugin mein '{action}' "
                "action supported nahi hai."
            )

    except Exception as e:
        result = f"Boss, notes plugin mein error aa gaya: {e}"

    # -----------------------------------------------------
    # Activity log
    # -----------------------------------------------------

    if player:
        try:
            player.write_log(
                f"CHHITI: {result}"
            )
        except Exception:
            pass

    return result