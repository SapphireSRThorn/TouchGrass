from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
import ctypes
import hashlib
import json
import math
import os
import re
import secrets
import smtplib
import sys

try:
	import tkinter as tk
except ModuleNotFoundError:
	tk = None

try:
	import bcrypt
except ModuleNotFoundError:
	bcrypt = None


BASE_DIR = Path(__file__).resolve().parent

ACCOUNT_CONFIG = {
	"accounts_file": str(BASE_DIR / "accounts.json"),
	"codes_file": str(BASE_DIR / "confirmation_codes.json"),
	"code_expiry_minutes": 15,
	"max_code_attempts": 5,
	# Email config: set env vars to enable real delivery.
	"email_sender": os.getenv("TOUCHGRASS_EMAIL_SENDER", "noreply@touchgrass.app"),
	"email_password": os.getenv("TOUCHGRASS_EMAIL_PASSWORD", "REPLACE_ME"),
	"smtp_server": os.getenv("TOUCHGRASS_SMTP_SERVER", "smtp.gmail.com"),
	"smtp_port": int(os.getenv("TOUCHGRASS_SMTP_PORT", "587")),
	# SMS config: set env vars to enable Twilio.
	"sms_provider": os.getenv("TOUCHGRASS_SMS_PROVIDER", "placeholder"),
	"twilio_account_sid": os.getenv("TOUCHGRASS_TWILIO_SID", "REPLACE_ME"),
	"twilio_auth_token": os.getenv("TOUCHGRASS_TWILIO_TOKEN", "REPLACE_ME"),
	"twilio_phone_number": os.getenv("TOUCHGRASS_TWILIO_FROM", "+1234567890"),
}

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 20
PASSWORD_MIN_LENGTH = 8


def _read_json(path: str, default_value):
	try:
		with open(path, "r", encoding="utf-8") as fh:
			return json.load(fh)
	except (FileNotFoundError, json.JSONDecodeError, OSError):
		return default_value


def _write_json(path: str, payload) -> None:
	with open(path, "w", encoding="utf-8") as fh:
		json.dump(payload, fh, indent=2)


def load_accounts() -> list[dict]:
	return _read_json(ACCOUNT_CONFIG["accounts_file"], [])


def save_accounts(accounts: list[dict]) -> None:
	_write_json(ACCOUNT_CONFIG["accounts_file"], accounts)


def load_confirmation_codes() -> dict:
	return _read_json(ACCOUNT_CONFIG["codes_file"], {})


def save_confirmation_codes(codes: dict) -> None:
	_write_json(ACCOUNT_CONFIG["codes_file"], codes)


def normalize_phone(phone: str) -> str:
	return re.sub(r"[\s\-().]", "", phone)


def validate_username(username: str) -> tuple[bool, str]:
	if not username:
		return False, "Username cannot be empty."
	if len(username) < USERNAME_MIN_LENGTH:
		return False, f"Username must be at least {USERNAME_MIN_LENGTH} characters."
	if len(username) > USERNAME_MAX_LENGTH:
		return False, f"Username cannot exceed {USERNAME_MAX_LENGTH} characters."
	if not re.match(r"^[a-zA-Z0-9_-]+$", username):
		return False, "Username can only contain letters, numbers, underscores, and hyphens."

	accounts = load_accounts()
	if any(acc["username"].lower() == username.lower() for acc in accounts):
		return False, "Username already taken."
	return True, ""


def validate_email(email: str) -> tuple[bool, str]:
	pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
	if not re.match(pattern, email):
		return False, "Invalid email format."

	accounts = load_accounts()
	if any(acc["email"].lower() == email.lower() for acc in accounts):
		return False, "Email already registered."
	return True, ""


def validate_phone(phone: str) -> tuple[bool, str]:
	cleaned = normalize_phone(phone)
	if not re.match(r"^\+?1?\d{9,15}$", cleaned):
		return False, "Invalid phone number. Use format +1234567890 or 1234567890."

	accounts = load_accounts()
	if any(acc["phone"] == cleaned for acc in accounts):
		return False, "Phone number already registered."
	return True, ""


def validate_password(password: str) -> tuple[bool, str]:
	if len(password) < PASSWORD_MIN_LENGTH:
		return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
	if not re.search(r"[a-z]", password):
		return False, "Password must contain at least one lowercase letter."
	if not re.search(r"[A-Z]", password):
		return False, "Password must contain at least one uppercase letter."
	if not re.search(r"\d", password):
		return False, "Password must contain at least one number."
	if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\",.<>?/\\|`~]", password):
		return False, "Password must contain at least one special character."
	return True, ""


def hash_password(password: str) -> str:
	if bcrypt:
		return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
	return hashlib.sha256(password.encode("utf-8")).hexdigest()


def generate_confirmation_code() -> str:
	return str(secrets.randbelow(1000000)).zfill(6)


def create_confirmation_code(email: str) -> tuple[str, str]:
	code = generate_confirmation_code()
	now = datetime.now(timezone.utc)
	codes = load_confirmation_codes()

	codes[email] = {
		"code": code,
		"created_at": now.isoformat(),
		"expires_at": (now + timedelta(minutes=ACCOUNT_CONFIG["code_expiry_minutes"])).isoformat(),
		"attempts": 0,
		"verified": False,
	}
	save_confirmation_codes(codes)
	return code, ""


def verify_confirmation_code(email: str, code: str) -> tuple[bool, str]:
	codes = load_confirmation_codes()
	entry = codes.get(email)
	if not entry:
		return False, "No confirmation code found for this email."

	expires_at = datetime.fromisoformat(entry["expires_at"])
	if datetime.now(timezone.utc) > expires_at:
		del codes[email]
		save_confirmation_codes(codes)
		return False, "Confirmation code expired. Request a new one."

	if entry["attempts"] >= ACCOUNT_CONFIG["max_code_attempts"]:
		del codes[email]
		save_confirmation_codes(codes)
		return False, "Too many attempts. Request a new code."

	if entry["code"] == code:
		entry["verified"] = True
		save_confirmation_codes(codes)
		return True, "Code verified successfully."

	entry["attempts"] += 1
	save_confirmation_codes(codes)
	remaining = ACCOUNT_CONFIG["max_code_attempts"] - entry["attempts"]
	return False, f"Invalid code. {remaining} attempts remaining."


def send_confirmation_email(email: str, code: str) -> tuple[bool, str]:
	if ACCOUNT_CONFIG["email_password"] == "REPLACE_ME":
		print(f"[PLACEHOLDER] Email code for {email}: {code}")
		return True, "Email code sent (dev placeholder: check terminal output)."

	try:
		body = (
			"TouchGrass verification code\n\n"
			f"Your confirmation code is: {code}\n"
			f"It expires in {ACCOUNT_CONFIG['code_expiry_minutes']} minutes.\n"
		)
		msg = MIMEText(body)
		msg["Subject"] = "TouchGrass Confirmation Code"
		msg["From"] = ACCOUNT_CONFIG["email_sender"]
		msg["To"] = email

		with smtplib.SMTP(ACCOUNT_CONFIG["smtp_server"], ACCOUNT_CONFIG["smtp_port"]) as server:
			server.starttls()
			server.login(ACCOUNT_CONFIG["email_sender"], ACCOUNT_CONFIG["email_password"])
			server.sendmail(ACCOUNT_CONFIG["email_sender"], [email], msg.as_string())
		return True, "Email confirmation code sent."
	except Exception as exc:
		return False, f"Failed to send email: {exc}"


def send_confirmation_sms(phone: str, code: str) -> tuple[bool, str]:
	if ACCOUNT_CONFIG["sms_provider"] == "placeholder" or ACCOUNT_CONFIG["twilio_account_sid"] == "REPLACE_ME":
		print(f"[PLACEHOLDER] SMS code for {phone}: {code}")
		return True, "SMS code sent (dev placeholder: check terminal output)."

	if ACCOUNT_CONFIG["sms_provider"] == "twilio":
		try:
			from twilio.rest import Client

			client = Client(ACCOUNT_CONFIG["twilio_account_sid"], ACCOUNT_CONFIG["twilio_auth_token"])
			client.messages.create(
				body=f"Your TouchGrass confirmation code is: {code}",
				from_=ACCOUNT_CONFIG["twilio_phone_number"],
				to=phone,
			)
			return True, "SMS confirmation code sent."
		except Exception as exc:
			return False, f"Failed to send SMS: {exc}"

	return False, "Unsupported SMS provider configuration."


def create_account(username: str, email: str, phone: str, password: str) -> tuple[bool, str]:
	checks = [
		validate_username(username),
		validate_email(email),
		validate_phone(phone),
		validate_password(password),
	]
	for ok, message in checks:
		if not ok:
			return False, message

	codes = load_confirmation_codes()
	if email not in codes or not codes[email].get("verified"):
		return False, "Email/phone confirmation is required before account creation."

	accounts = load_accounts()
	accounts.append(
		{
			"account_id": secrets.token_hex(16),
			"username": username,
			"email": email,
			"phone": normalize_phone(phone),
			"password_hash": hash_password(password),
			"created_at": datetime.now(timezone.utc).isoformat(),
			"verified": True,
		}
	)
	save_accounts(accounts)

	del codes[email]
	save_confirmation_codes(codes)
	return True, "Account created successfully."


def run_cli_account_creation_demo() -> None:
	"""
	Quick CLI demo for wiring to your age verification flow.
	Call this only after age verification passes.
	"""
	print("\n=== Account Creation ===")
	username = input("Username: ").strip()
	email = input("Email: ").strip()
	phone = input("Phone number: ").strip()
	password = input("Password: ").strip()

	checks = [
		validate_username(username),
		validate_email(email),
		validate_phone(phone),
		validate_password(password),
	]
	for ok, message in checks:
		if not ok:
			print(f"Validation error: {message}")
			return

	method = input("Send confirmation code via email or sms? (email/sms): ").strip().lower()
	if method not in {"email", "sms"}:
		print("Invalid choice.")
		return

	code, err = create_confirmation_code(email)
	if err:
		print(f"Code creation failed: {err}")
		return

	if method == "sms":
		sent_ok, sent_msg = send_confirmation_sms(phone, code)
	else:
		sent_ok, sent_msg = send_confirmation_email(email, code)

	print(sent_msg)
	if not sent_ok:
		return

	entered = input("Enter 6-digit confirmation code: ").strip()
	verified, verify_msg = verify_confirmation_code(email, entered)
	print(verify_msg)
	if not verified:
		return

	created, create_msg = create_account(username, email, phone, password)
	print(create_msg)


def run_borderless_ui() -> None:
	if tk is None:
		raise RuntimeError("tkinter is not available in this Python environment.")

	root = tk.Tk()
	root.title("Touch Grass Account Creation")
	window_w = 560
	window_h = 690
	root.geometry(f"{window_w}x{window_h}")
	root.resizable(False, False)
	root.overrideredirect(True)

	frame_color = "#00FF00"
	gradient_start = "#001900"
	gradient_end = "#006600"
	text_outline = "#3E990B"
	text_fill = "#000000"

	shell_bg = gradient_start
	card_bg = "#003300"
	input_bg = "#005000"
	text_primary = text_fill
	text_secondary = text_outline
	accent = "#00A844"
	accent_hover = "#008A39"

	def center_window():
		root.update_idletasks()
		screen_w = root.winfo_screenwidth()
		screen_h = root.winfo_screenheight()
		pos_x = max(0, (screen_w - window_w) // 2)
		pos_y = max(0, (screen_h - window_h) // 2)
		root.geometry(f"{window_w}x{window_h}+{pos_x}+{pos_y}")

	use_native_round_region = hasattr(ctypes, "windll")
	use_linux_x11_shape = sys.platform.startswith("linux")

	if use_native_round_region:
		root.configure(bg=gradient_start)
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
			x1 + radius,
			y1,
			x2 - radius,
			y1,
			x2,
			y1,
			x2,
			y1 + radius,
			x2,
			y2 - radius,
			x2,
			y2,
			x2 - radius,
			y2,
			x1 + radius,
			y2,
			x1,
			y2,
			x1,
			y2 - radius,
			x1,
			y1 + radius,
			x1,
			y1,
		]
		return canvas.create_polygon(points, smooth=True, splinesteps=36, **kwargs)

	def hex_to_rgb(hex_color: str):
		raw = hex_color.lstrip("#")
		return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))

	def rgb_to_hex(rgb):
		return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

	def draw_horizontal_gradient(canvas, x1: int, y1: int, x2: int, y2: int, start_hex: str, end_hex: str, tag: str):
		canvas.delete(tag)
		width = max(1, x2 - x1)
		start = hex_to_rgb(start_hex)
		end = hex_to_rgb(end_hex)
		for i in range(width):
			t = i / max(1, width - 1)
			color = (
				int(start[0] + (end[0] - start[0]) * t),
				int(start[1] + (end[1] - start[1]) * t),
				int(start[2] + (end[2] - start[2]) * t),
			)
			x = x1 + i
			canvas.create_line(x, y1, x, y2, fill=rgb_to_hex(color), tags=tag)

	def draw_outlined_text(canvas, x: int, y: int, text: str, font, fill: str, outline: str):
		for ox, oy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
			canvas.create_text(x + ox, y + oy, text=text, fill=outline, font=font, anchor="w")
		canvas.create_text(x, y, text=text, fill=fill, font=font, anchor="w")

	shell_canvas = tk.Canvas(root, highlightthickness=0, bd=0, bg=root["bg"])
	shell_canvas.pack(fill="both", expand=True)
	draw_horizontal_gradient(shell_canvas, 0, 0, window_w, window_h, gradient_start, gradient_end, "shell_gradient")
	shell_canvas.tag_lower("shell_gradient")

	last_region_size = {"w": 0, "h": 0}

	def apply_native_round_region(radius_px: int = 68):
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
		outline=frame_color,
		width=1,
	)

	frame = tk.Frame(shell_canvas, bg=shell_bg)
	frame_window = shell_canvas.create_window(0, 0, window=frame, anchor="nw", width=window_w, height=window_h)

	content = tk.Frame(frame, bg=shell_bg)
	content.pack(fill="both", expand=True, padx=20, pady=20)

	hero = tk.Frame(content, bg=shell_bg)
	hero.pack(fill="x", pady=(0, 10))

	title_canvas = tk.Canvas(hero, height=34, bg=shell_bg, highlightthickness=0, bd=0)
	title_canvas.pack(fill="x")
	draw_outlined_text(
		title_canvas,
		0,
		17,
		"Touch Grass Account Creation",
		("Segoe UI Semibold", 18),
		text_fill,
		text_outline,
	)

	hero_subtitle = tk.Label(
		hero,
		text="Create your account and verify with email or SMS.",
		bg=shell_bg,
		fg=text_secondary,
		font=("Segoe UI", 10),
	)
	hero_subtitle.pack(anchor="w", pady=(2, 0))

	card_canvas = tk.Canvas(content, highlightthickness=0, bd=0, bg=shell_bg, height=470)
	card_canvas.pack(fill="x", expand=False)
	card_shape = draw_rounded_rect(card_canvas, 0, 0, window_w - 40, 460, radius=20, fill=card_bg, outline="#1a1b1e", width=1)
	card = tk.Frame(card_canvas, bg=card_bg)
	card_window = card_canvas.create_window(14, 14, window=card, anchor="nw", width=window_w - 68)

	username_var = tk.StringVar()
	email_var = tk.StringVar()
	phone_var = tk.StringVar()
	password_var = tk.StringVar()
	method_var = tk.StringVar(value="email")
	code_var = tk.StringVar()
	status_var = tk.StringVar(value="Fill in your details, then send a confirmation code.")
	pending = {"email": "", "phone": ""}
	account_done = {"value": False}

	def create_input_row(parent, label_text, var, show: str = ""):
		row = tk.Frame(parent, bg=card_bg)
		row.pack(fill="x", pady=6)

		tk.Label(
			row,
			text=label_text,
			bg=card_bg,
			fg=text_secondary,
			font=("Segoe UI", 9, "bold"),
			width=12,
			anchor="w",
		).pack(side="left", padx=(0, 10))

		bubble = tk.Frame(row, bg=input_bg, bd=0)
		bubble.pack(side="left", fill="x", expand=True)

		entry = tk.Entry(
			bubble,
			textvariable=var,
			bg=input_bg,
			fg=text_primary,
			insertbackground=text_primary,
			relief="flat",
			bd=0,
			font=("Segoe UI", 11),
			show=show,
		)
		entry.pack(fill="x", padx=14, pady=10)
		return entry

	username_entry = create_input_row(card, "Username", username_var)
	email_entry = create_input_row(card, "Email", email_var)
	phone_entry = create_input_row(card, "Phone", phone_var)
	password_entry = create_input_row(card, "Password", password_var, show="*")

	method_row = tk.Frame(card, bg=card_bg)
	method_row.pack(fill="x", pady=(8, 2))
	tk.Label(method_row, text="Code Via", bg=card_bg, fg=text_secondary, font=("Segoe UI", 9, "bold"), width=12, anchor="w").pack(side="left", padx=(0, 10))
	method_select = tk.Frame(method_row, bg=card_bg)
	method_select.pack(side="left")
	tk.Radiobutton(
		method_select,
		text="Email",
		variable=method_var,
		value="email",
		bg=card_bg,
		fg=text_secondary,
		selectcolor=input_bg,
		activebackground=card_bg,
		activeforeground=text_secondary,
		font=("Segoe UI", 9),
	).pack(side="left", padx=(0, 12))
	tk.Radiobutton(
		method_select,
		text="SMS",
		variable=method_var,
		value="sms",
		bg=card_bg,
		fg=text_secondary,
		selectcolor=input_bg,
		activebackground=card_bg,
		activeforeground=text_secondary,
		font=("Segoe UI", 9),
	).pack(side="left")

	create_input_row(card, "Code", code_var)

	status_label = tk.Label(
		card,
		textvariable=status_var,
		bg=card_bg,
		fg=text_secondary,
		wraplength=440,
		justify="left",
		font=("Segoe UI", 9),
	)
	status_label.pack(fill="x", pady=(8, 10))

	button_row = tk.Frame(card, bg=card_bg)
	button_row.pack(fill="x", pady=(4, 0))

	def send_code():
		username = username_var.get().strip()
		email = email_var.get().strip()
		phone = phone_var.get().strip()
		password = password_var.get()

		checks = [
			validate_username(username),
			validate_email(email),
			validate_phone(phone),
			validate_password(password),
		]
		for ok, message in checks:
			if not ok:
				status_var.set(message)
				status_label.configure(fg="#ed4245")
				return

		code, err = create_confirmation_code(email)
		if err:
			status_var.set(err)
			status_label.configure(fg="#ed4245")
			return

		if method_var.get() == "sms":
			sent_ok, sent_msg = send_confirmation_sms(phone, code)
		else:
			sent_ok, sent_msg = send_confirmation_email(email, code)

		if not sent_ok:
			status_var.set(sent_msg)
			status_label.configure(fg="#ed4245")
			return

		pending["email"] = email
		pending["phone"] = phone
		status_var.set(f"{sent_msg} Enter the code and click Create Account.")
		status_label.configure(fg="#43b581")

	def finish_account_creation():
		email = email_var.get().strip()
		if not pending["email"] or pending["email"] != email:
			status_var.set("Send a confirmation code first.")
			status_label.configure(fg="#ed4245")
			return

		entered_code = code_var.get().strip()
		if not re.match(r"^\d{6}$", entered_code):
			status_var.set("Enter a valid 6-digit confirmation code.")
			status_label.configure(fg="#ed4245")
			return

		verified, verify_msg = verify_confirmation_code(email, entered_code)
		if not verified:
			status_var.set(verify_msg)
			status_label.configure(fg="#ed4245")
			return

		created, create_msg = create_account(
			username_var.get().strip(),
			email,
			phone_var.get().strip(),
			password_var.get(),
		)
		if not created:
			status_var.set(create_msg)
			status_label.configure(fg="#ed4245")
			return

		account_done["value"] = True
		status_var.set(create_msg)
		status_label.configure(fg="#43b581")
		root.after(1200, root.destroy)

	tk.Button(
		button_row,
		text="Send Code",
		command=send_code,
		bg=input_bg,
		fg=text_primary,
		relief="flat",
		font=("Segoe UI", 9, "bold"),
	).pack(side="left")

	tk.Button(
		button_row,
		text="Create Account",
		command=finish_account_creation,
		bg=accent,
		fg=text_fill,
		relief="flat",
		font=("Segoe UI", 9, "bold"),
	).pack(side="right")

	def attempt_close():
		if account_done["value"]:
			root.destroy()
			return
		status_var.set("Complete account creation before closing.")
		status_label.configure(fg="#ed4245")

	def resize_rounded_rect(canvas, item_id, width, height, radius):
		radius = min(radius, max(2, width // 2), max(2, height // 2))
		points = [
			1 + radius,
			1,
			width - 1 - radius,
			1,
			width - 1,
			1,
			width - 1,
			1 + radius,
			width - 1,
			height - 1 - radius,
			width - 1,
			height - 1,
			width - 1 - radius,
			height - 1,
			1 + radius,
			height - 1,
			1,
			height - 1,
			1,
			height - 1 - radius,
			1,
			1 + radius,
			1,
			1,
		]
		canvas.coords(item_id, *points)

	def on_shell_resize(event):
		draw_horizontal_gradient(shell_canvas, 0, 0, event.width, event.height, gradient_start, gradient_end, "shell_gradient")
		shell_canvas.tag_lower("shell_gradient")
		shell_canvas.itemconfigure(frame_window, width=event.width, height=event.height)
		resize_rounded_rect(shell_canvas, shell_shape, event.width, event.height, radius=34)
		apply_native_round_region()
		apply_linux_x11_round_region()

	def update_card_layout(card_w: int):
		card_w = max(280, card_w)
		required_h = card.winfo_reqheight() + 28
		card_h = max(440, required_h)
		if abs(card_canvas.winfo_height() - card_h) > 1:
			card_canvas.configure(height=card_h)
		resize_rounded_rect(card_canvas, card_shape, card_w, card_h, radius=20)
		card_canvas.itemconfigure(card_window, width=max(240, card_w - 28))
		status_label.configure(wraplength=max(240, card_w - 36))

	def on_card_resize(event):
		update_card_layout(event.width)

	shell_canvas.bind("<Configure>", on_shell_resize)
	card_canvas.bind("<Configure>", on_card_resize)

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

	for drag_widget in (hero, title_canvas, hero_subtitle):
		drag_widget.bind("<ButtonPress-1>", start_drag)
		drag_widget.bind("<B1-Motion>", do_drag)

	for entry_widget in (username_entry, email_entry, phone_entry, password_entry):
		entry_widget.bind("<Return>", lambda _event: send_code())

	root.bind("<Escape>", lambda _event: attempt_close())
	root.protocol("WM_DELETE_WINDOW", attempt_close)
	username_entry.focus_set()
	root.mainloop()


if __name__ == "__main__":
	if tk is None:
		run_cli_account_creation_demo()
	else:
		run_borderless_ui()
