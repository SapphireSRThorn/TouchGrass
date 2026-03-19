# =========================================
# TKiller420
# Required dependencies/packages:
# - Python 3.13 or later
# - tkinter (usually bundled with Python)
# - ctypes (Python standard library)
# - datetime (Python standard library)
# age verification script for TouchGrass
# =========================================
from datetime import datetime, timezone
import ctypes
import os
import math
import sys

try:
    import tkinter as tk
except ModuleNotFoundError:
    tk = None


MINIMUM_AGE = 16
MATRIX_PLACEHOLDER_CONFIG = {
    "homeserver_url": "https://matrix.example.com",
    "access_token": "REPLACE_ME",
    "database_table": "age_verifications",
    "room_id": "!replace:example.com",
}


def calculate_age(birth_year: int, birth_month: int, birth_day: int) -> int:
    """Calculate age from birth date."""
    today = datetime.today()
    age = today.year - birth_year

    if (today.month, today.day) < (birth_month, birth_day):
        age -= 1

    return age


def verify_age(birth_year: int, birth_month: int, birth_day: int) -> dict:
    """
    Verify whether the user is at least 16 years old.
    Returns a result object that can later be sent to JS/TS.
    """
    try:
        if not 1 <= birth_month <= 12:
            raise ValueError("Birth month must be between 1 and 12.")
        if not 1 <= birth_day <= 31:
            raise ValueError("Birth day must be between 1 and 31.")

        birth_date = datetime(birth_year, birth_month, birth_day)
        if birth_date.date() > datetime.today().date():
            raise ValueError("Birth date cannot be in the future.")

        age = calculate_age(birth_year, birth_month, birth_day)
        if age > 120:
            raise ValueError("Birth year is too old. Maximum realistic age is 120.")

        return {
            "success": True,
            "age": age,
            "is_16_plus": age >= MINIMUM_AGE,
            "message": "Welcome to TouchGrass!" if age >= MINIMUM_AGE else "You Shall Not PASS!. Must be 16 or older."
        }

    except Exception as e:
        return {
            "success": False,
            "age": None,
            "is_16_plus": False,
            "message": f"Error verifying age: {str(e)}"
        }


def send_result_to_js_ts(result: dict):
    """
    PLACEHOLDER:
    Replace this with your JavaScript/TypeScript integration.
    
    """
    print("\n[PLACEHOLDER] Send this result to JS/TS:")
    print(result)


def build_matrix_verification_record(result: dict) -> dict:
    """Build the payload that would be written to Matrix-backed storage."""
    timestamp_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "event_type": "touchgrass.age_verification",
        "timestamp": timestamp_utc,
        "verified": result["is_16_plus"],
        "age": result["age"],
        "message": result["message"],
        "matrix_room_id": MATRIX_PLACEHOLDER_CONFIG["room_id"],
    }


def save_result_to_matrix_database(result: dict):
    """
    PLACEHOLDER:
    Replace this with Matrix database or Matrix homeserver persistence.

    Suggested future implementation points:
    - insert the record into a Matrix-linked database table
    - send an event to a Matrix room timeline
    - call a backend API that persists verification state for a Matrix user
    """
    payload = build_matrix_verification_record(result)
    print("\n[PLACEHOLDER] Save this record to Matrix integration:")
    print(payload)


def load_matrix_user_context() -> dict:
    """
    PLACEHOLDER:
    Replace this with lookup logic for the current Matrix user/session.
    """
    return {
        "matrix_user_id": "@example:matrix.org",
        "device_id": "DEVICE_PLACEHOLDER",
        "access_token": MATRIX_PLACEHOLDER_CONFIG["access_token"],
    }


def run_borderless_ui():
    if tk is None:
        raise RuntimeError("tkinter is not available in this Python environment.")

    root = tk.Tk()
    root.title("16+ Age Verification")
    window_w = 520
    window_h = 560
    root.geometry(f"{window_w}x{window_h}")
    root.resizable(False, False)

    def center_window():
        root.update_idletasks()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        pos_x = max(0, (screen_w - window_w) // 2)
        pos_y = max(0, (screen_h - window_h) // 2)
        root.geometry(f"{window_w}x{window_h}+{pos_x}+{pos_y}")

    root.overrideredirect(True)

    shell_bg = "#2b2d31"
    card_bg = "#232428"
    input_bg = "#383a40"
    text_primary = "#f2f3f5"
    text_secondary = "#b5bac1"
    accent = "#5865f2"
    accent_hover = "#4752c4"

    use_native_round_region = hasattr(ctypes, "windll")
    use_linux_x11_shape = sys.platform.startswith("linux")

    if use_native_round_region:
        root.configure(bg=shell_bg)
    else:
        transparent_color = "#010203"
        root.configure(bg=transparent_color)
        try:
            root.wm_attributes("-transparentcolor", transparent_color)
        except tk.TclError:
            root.configure(bg=shell_bg)

    class XRectangle(ctypes.Structure):
        _fields_ = [
            ("x", ctypes.c_short),
            ("y", ctypes.c_short),
            ("width", ctypes.c_ushort),
            ("height", ctypes.c_ushort),
        ]

    x11_state = {
        "available": False,
        "display": None,
        "xlib": None,
        "xext": None,
        "warned": False,
    }

    def init_linux_x11_shape():
        if not use_linux_x11_shape:
            return

        try:
            xlib = ctypes.CDLL("libX11.so.6")
            xext = ctypes.CDLL("libXext.so.6")

            xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            xlib.XOpenDisplay.restype = ctypes.c_void_p
            xlib.XFlush.argtypes = [ctypes.c_void_p]
            xlib.XFlush.restype = ctypes.c_int

            xext.XShapeCombineRectangles.argtypes = [
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(XRectangle),
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            xext.XShapeCombineRectangles.restype = None

            display = xlib.XOpenDisplay(None)
            if not display:
                return

            x11_state["available"] = True
            x11_state["display"] = display
            x11_state["xlib"] = xlib
            x11_state["xext"] = xext
        except Exception:
            return

    def apply_linux_x11_round_region(radius_px: int = 34):
        if not x11_state["available"]:
            if use_linux_x11_shape and not x11_state["warned"]:
                x11_state["warned"] = True
            return

        root.update_idletasks()
        w = root.winfo_width()
        h = root.winfo_height()
        if w <= 1 or h <= 1:
            return

        r = min(radius_px, max(2, w // 2), max(2, h // 2))
        rect_count = max(1, h)
        rects = (XRectangle * rect_count)()

        for y in range(h):
            if y < r:
                dy = r - y - 1
                inset = int(max(0, r - math.sqrt(max(0, (r * r) - (dy * dy)))))
            elif y >= h - r:
                dy = y - (h - r)
                inset = int(max(0, r - math.sqrt(max(0, (r * r) - (dy * dy)))))
            else:
                inset = 0

            width = max(1, w - (2 * inset))
            rects[y].x = inset
            rects[y].y = y
            rects[y].width = width
            rects[y].height = 1

        window_id = ctypes.c_ulong(root.winfo_id())
        x11_state["xext"].XShapeCombineRectangles(
            x11_state["display"],
            window_id,
            0,
            0,
            0,
            rects,
            h,
            0,
            0,
        )
        x11_state["xlib"].XFlush(x11_state["display"])

    init_linux_x11_shape()

    def draw_rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, splinesteps=36, **kwargs)

    shell_canvas = tk.Canvas(root, highlightthickness=0, bd=0, bg=root["bg"])
    shell_canvas.pack(fill="both", expand=True)

    last_region_size = {"w": 0, "h": 0}

    def apply_native_round_region(radius_px: int = 68):
        """Force rounded outer corners on Windows using a native window region."""
        if not use_native_round_region:
            return

        root.update_idletasks()
        w = root.winfo_width()
        h = root.winfo_height()
        if w <= 1 or h <= 1:
            return
        if last_region_size["w"] == w and last_region_size["h"] == h:
            return

        try:
            region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, radius_px, radius_px)
            ctypes.windll.user32.SetWindowRgn(root.winfo_id(), region, True)
            last_region_size["w"] = w
            last_region_size["h"] = h
        except Exception:
            pass

    shell_shape = draw_rounded_rect(
        shell_canvas,
        1,
        1,
        window_w - 1,
        window_h - 1,
        radius=34,
        fill=shell_bg,
        outline="#202225",
        width=1,
    )

    frame = tk.Frame(shell_canvas, bg=shell_bg)
    frame_window = shell_canvas.create_window(0, 0, window=frame, anchor="nw", width=window_w, height=window_h)

    content = tk.Frame(frame, bg=shell_bg)
    content.pack(fill="both", expand=True, padx=20, pady=20)

    hero = tk.Frame(content, bg=shell_bg)
    hero.pack(fill="x", pady=(0, 10))

    logo_label = tk.Label(hero, bg=shell_bg)
    logo_label.pack(anchor="center", pady=(0, 8))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(script_dir, "touchgrass-logo.png")
    logo_image = None

    if os.path.exists(logo_path):
        try:
            loaded_logo = tk.PhotoImage(file=logo_path)
            # Scale down larger images while preserving aspect ratio.
            sample_factor = max(1, loaded_logo.width() // 300, loaded_logo.height() // 170)
            logo_image = loaded_logo.subsample(sample_factor)
            logo_label.configure(image=logo_image)
        except tk.TclError:
            logo_label.configure(
                text="Logo file found but could not be loaded.",
                fg="#ed4245",
                font=("Segoe UI", 9),
            )
    else:
        logo_label.configure(
            text="Missing logo: place touchgrass-logo.png next to this script.",
            fg=text_secondary,
            font=("Segoe UI", 9),
        )

    hero_title = tk.Label(
        hero,
        text="Touch Grass Age Verification",
        bg=shell_bg,
        fg=text_primary,
        font=("Segoe UI Semibold", 18),
    )
    hero_title.pack(anchor="w")
    hero_subtitle = tk.Label(
        hero,
        text="Enter your birth date to continue.",
        bg=shell_bg,
        fg=text_secondary,
        font=("Segoe UI", 10),
    )
    hero_subtitle.pack(anchor="w", pady=(2, 0))

    card_canvas = tk.Canvas(content, highlightthickness=0, bd=0, bg=shell_bg, height=300)
    card_canvas.pack(fill="x", expand=False)
    card_shape = draw_rounded_rect(card_canvas, 0, 0, window_w - 40, 280, radius=20, fill=card_bg, outline="#1a1b1e", width=1)

    card = tk.Frame(card_canvas, bg=card_bg)
    card_window = card_canvas.create_window(14, 14, window=card, anchor="nw", width=window_w - 68)

    year_var = tk.StringVar()
    month_var = tk.StringVar()
    day_var = tk.StringVar()
    status_var = tk.StringVar(value="Fill all fields, then hit Verify.")
    is_verified = {"value": False}
    close_scheduled = {"value": False}

    def create_input_row(parent, label_text, var):
        row = tk.Frame(parent, bg=card_bg) # type: ignore
        row.pack(fill="x", pady=6)

        tk.Label( # type: ignore
            row,
            text=label_text,
            bg=card_bg,
            fg=text_secondary,
            font=("Segoe UI", 9, "bold"),
            width=12,
            anchor="w",
        ).pack(side="left", padx=(0, 10))

        bubble = tk.Frame(row, bg=input_bg, bd=0) # type: ignore
        bubble.pack(side="left", fill="x", expand=True)

        entry = tk.Entry( # type: ignore
            bubble,
            textvariable=var,
            bg=input_bg,
            fg=text_primary,
            insertbackground=text_primary,
            relief="flat",
            bd=0,
            font=("Segoe UI", 11),
        )
        entry.pack(fill="x", padx=14, pady=10)
        return entry

    year_entry = create_input_row(card, "Birth Year", year_var)
    month_entry = create_input_row(card, "Birth Month", month_var)
    day_entry = create_input_row(card, "Birth Day", day_var)

    card.grid_columnconfigure(0, weight=1)

    status_label = tk.Label(
        card,
        textvariable=status_var,
        bg=card_bg,
        fg=text_secondary,
        wraplength=400,
        justify="left",
        font=("Segoe UI", 9),
    )
    status_label.pack(fill="x", pady=(8, 8))

    button_canvas = tk.Canvas(card, width=180, height=44, highlightthickness=0, bd=0, bg=card_bg)
    button_canvas.pack(anchor="center", pady=(4, 0))

    button_shape = draw_rounded_rect(
        button_canvas,
        1,
        1,
        179,
        43,
        radius=22,
        fill=accent,
        outline=accent,
        width=1,
    )
    button_text = button_canvas.create_text(
        90,
        22,
        text="Verify",
        fill="#ffffff",
        font=("Segoe UI", 10, "bold"),
    )

    def on_verify():
        try:
            year = int(year_var.get().strip())
            month = int(month_var.get().strip())
            day = int(day_var.get().strip())

            matrix_user_context = load_matrix_user_context()
            result = verify_age(year, month, day)
            result["matrix_user_id"] = matrix_user_context["matrix_user_id"]
            if result["is_16_plus"]:
                is_verified["value"] = True
                status_label.configure(fg="#43b581")
                status_var.set(f"Age {result['age']}  |  Verified: True  |  {result['message']}")
                if not close_scheduled["value"]:
                    close_scheduled["value"] = True
                    root.after(1500, root.destroy)
            else:
                status_label.configure(fg="#faa61a")
                status_var.set(f"Age {result['age']}  |  Verified: False  |  {result['message']}")
            send_result_to_js_ts(result)
            save_result_to_matrix_database(result)

        except ValueError:
            status_label.configure(fg="#ed4245")
            status_var.set("Invalid input. Please enter numbers only.")

    def attempt_close():
        if is_verified["value"]:
            root.destroy()
            return

        status_label.configure(fg="#ed4245")
        status_var.set("You must complete verification before closing this window.")

    def hover_on(_event):
        button_canvas.itemconfig(button_shape, fill=accent_hover, outline=accent_hover)

    def hover_off(_event):
        button_canvas.itemconfig(button_shape, fill=accent, outline=accent)

    button_canvas.tag_bind(button_shape, "<Button-1>", lambda _event: on_verify())
    button_canvas.tag_bind(button_text, "<Button-1>", lambda _event: on_verify())
    button_canvas.tag_bind(button_shape, "<Enter>", hover_on)
    button_canvas.tag_bind(button_text, "<Enter>", hover_on)
    button_canvas.tag_bind(button_shape, "<Leave>", hover_off)
    button_canvas.tag_bind(button_text, "<Leave>", hover_off)

    def resize_rounded_rect(canvas, item_id, width, height, radius):
        radius = min(radius, max(2, width // 2), max(2, height // 2))
        points = [
            1 + radius, 1,
            width - 1 - radius, 1,
            width - 1, 1,
            width - 1, 1 + radius,
            width - 1, height - 1 - radius,
            width - 1, height - 1,
            width - 1 - radius, height - 1,
            1 + radius, height - 1,
            1, height - 1,
            1, height - 1 - radius,
            1, 1 + radius,
            1, 1,
        ]
        canvas.coords(item_id, *points)

    def on_shell_resize(event):
        shell_canvas.itemconfigure(frame_window, width=event.width, height=event.height)
        resize_rounded_rect(shell_canvas, shell_shape, event.width, event.height, radius=34)
        apply_native_round_region()
        apply_linux_x11_round_region()

    def update_card_layout(card_w: int):
        card_w = max(250, card_w)
        required_h = card.winfo_reqheight() + 28
        card_h = max(260, required_h)

        if abs(card_canvas.winfo_height() - card_h) > 1:
            card_canvas.configure(height=card_h)
        resize_rounded_rect(card_canvas, card_shape, card_w, card_h, radius=20)
        card_canvas.itemconfigure(card_window, width=max(220, card_w - 28))
        status_label.configure(wraplength=max(220, card_w - 36))

    def on_card_resize(event):
        update_card_layout(event.width)

    def refresh_card_height():
        card_canvas.update_idletasks()
        update_card_layout(card_canvas.winfo_width())

    shell_canvas.bind("<Configure>", on_shell_resize)
    card_canvas.bind("<Configure>", on_card_resize)
    root.after(0, refresh_card_height)
    root.after(0, center_window)
    root.after(0, apply_native_round_region)
    root.after(0, apply_linux_x11_round_region)

    drag_state = {"x": 0, "y": 0}

    def start_drag(event):
        drag_state["x"] = event.x_root - root.winfo_x()
        drag_state["y"] = event.y_root - root.winfo_y()

    def do_drag(event):
        x = event.x_root - drag_state["x"]
        y = event.y_root - drag_state["y"]
        root.geometry(f"+{x}+{y}")

    for drag_widget in (hero, hero_title, hero_subtitle):
        drag_widget.bind("<ButtonPress-1>", start_drag)
        drag_widget.bind("<B1-Motion>", do_drag)

    for entry_widget in (year_entry, month_entry, day_entry):
        entry_widget.bind("<Return>", lambda _event: on_verify())

    root.bind("<Return>", lambda _event: on_verify())
    root.bind("<Escape>", lambda _event: attempt_close())
    root.protocol("WM_DELETE_WINDOW", attempt_close)
    year_entry.focus_set()

    root.mainloop()


def run_cli_fallback():
    """Fallback mode for environments where tkinter is unavailable."""
    print("Running in terminal mode because tkinter is not installed.")

    try:
        year = int(input("Birth Year (YYYY): ").strip())
        month = int(input("Birth Month (1-12): ").strip())
        day = int(input("Birth Day (1-31): ").strip())
    except ValueError:
        print("Invalid input. Please enter numbers only.")
        return

    matrix_user_context = load_matrix_user_context()
    result = verify_age(year, month, day)
    result["matrix_user_id"] = matrix_user_context["matrix_user_id"]
    print(
        f"Age {result['age']} | Verified: {result['is_16_plus']} | {result['message']}"
    )
    send_result_to_js_ts(result)
    save_result_to_matrix_database(result)


if __name__ == "__main__":
    if tk is None:
        run_cli_fallback()
    else:
        run_borderless_ui()