from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
import hashlib
import json
import os
import re
import secrets
import smtplib

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


if __name__ == "__main__":
	run_cli_account_creation_demo()
