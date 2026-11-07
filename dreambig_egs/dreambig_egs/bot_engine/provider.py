# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import json
import logging
import os
from abc import ABC, abstractmethod
import requests
import frappe

logger = logging.getLogger("dreambig_bot_engine")


class BaseMessagingProvider(ABC):
	"""
	Abstract base class for messaging platform adapters (Telegram, WhatsApp, etc.).
	Provides platform-agnostic communication interface for the 5Ds Bot Engine.
	"""

	@abstractmethod
	def send_text(self, chat_id: str, text: str) -> dict:
		"""
		Sends a plain text or markdown message to the user.
		"""
		pass

	@abstractmethod
	def send_interactive_message(self, chat_id: str, text: str, buttons: list) -> dict:
		"""
		Sends a message accompanied by standardized interactive button choices.
		buttons format: [{"id": "btn_1", "title": "Option 1"}]
		"""
		pass

	def send_contact_request(self, chat_id: str, text: str, button_text: str = "📱 Share Contact") -> dict:
		"""
		Sends a native contact sharing request button.
		"""
		pass

	def send_interactive_buttons(self, chat_id: str, text: str, buttons: list) -> dict:
		"""
		Backward-compatible alias for send_interactive_message.
		"""
		return self.send_interactive_message(chat_id, text, buttons)

	@abstractmethod
	def parse_incoming_webhook(self, request_data: dict) -> dict:
		"""
		Parses raw webhook request payload from the platform and returns
		standardized format:
		{
			"chat_id": str,
			"text": str,
			"payload": str,
			"sender_name": str,
			"is_button": bool,
			"raw": dict
		}
		"""
		pass


class TelegramProvider(BaseMessagingProvider):
	"""
	Telegram Bot API provider implementation using InlineKeyboardMarkup for buttons.
	"""

	def __init__(self, bot_token: str = None):
		self.bot_token = (
			bot_token
			or frappe.conf.get("telegram_bot_token")
			or os.environ.get("TELEGRAM_BOT_TOKEN")
		)
		self.api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

	def send_text(self, chat_id: str, text: str) -> dict:
		if not self.bot_token or getattr(frappe.flags, "in_test", False):
			return {
				"status": "mock_sent",
				"provider": "telegram",
				"chat_id": str(chat_id),
				"text": text,
			}

		url = f"{self.api_url}/sendMessage"
		payload = {
			"chat_id": str(chat_id),
			"text": text,
			"parse_mode": "Markdown",
		}

		try:
			resp = requests.post(url, json=payload, timeout=10)
			return resp.json()
		except Exception as e:
			frappe.log_error(f"Telegram send_text failed: {e}", "TelegramProvider")
			return {"status": "error", "message": str(e)}

	def send_interactive_message(self, chat_id: str, text: str, buttons: list) -> dict:
		"""
		Maps standardized buttons [{"id": "...", "title": "..."}] to Telegram InlineKeyboardMarkup.
		Supports inline URL buttons if 'url' key is present in button dict.
		"""
		inline_keyboard = []
		for i, b in enumerate(buttons or []):
			title = str(b.get("title") or b.get("text") or b.get("id") or f"Option {i+1}")
			if b.get("url"):
				inline_keyboard.append([{"text": title, "url": str(b["url"])}])
			else:
				btn_id = str(b.get("id") or b.get("payload") or b.get("callback_data") or b.get("title") or f"btn_{i}")
				inline_keyboard.append([{"text": title, "callback_data": btn_id[:64]}])

		if not self.bot_token or getattr(frappe.flags, "in_test", False):
			return {
				"status": "mock_sent",
				"provider": "telegram",
				"chat_id": str(chat_id),
				"text": text,
				"buttons": buttons,
				"reply_markup": {"inline_keyboard": inline_keyboard},
			}

		url = f"{self.api_url}/sendMessage"
		payload = {
			"chat_id": str(chat_id),
			"text": text,
			"parse_mode": "Markdown",
			"reply_markup": {"inline_keyboard": inline_keyboard},
		}

		try:
			resp = requests.post(url, json=payload, timeout=10)
			return resp.json()
		except Exception as e:
			frappe.log_error(f"Telegram send_interactive_message failed: {e}", "TelegramProvider")
			return {"status": "error", "message": str(e)}

	def send_contact_request(self, chat_id: str, text: str, button_text: str = "📱 Share Contact") -> dict:
		"""
		Sends a native Telegram ReplyKeyboardMarkup requesting contact sharing.
		"""
		reply_markup = {
			"keyboard": [
				[{"text": button_text, "request_contact": True}]
			],
			"resize_keyboard": True,
			"one_time_keyboard": True,
		}

		if not self.bot_token or getattr(frappe.flags, "in_test", False):
			return {
				"status": "mock_sent",
				"provider": "telegram",
				"chat_id": str(chat_id),
				"text": text,
				"button_text": button_text,
				"reply_markup": reply_markup,
				"type": "contact_request",
			}

		url = f"{self.api_url}/sendMessage"
		payload = {
			"chat_id": str(chat_id),
			"text": text,
			"parse_mode": "Markdown",
			"reply_markup": reply_markup,
		}

		try:
			resp = requests.post(url, json=payload, timeout=10)
			return resp.json()
		except Exception as e:
			frappe.log_error(f"Telegram send_contact_request failed: {e}", "TelegramProvider")
			return {"status": "error", "message": str(e)}

	def parse_incoming_webhook(self, request_data: dict) -> dict:
		"""
		Normalizes incoming Telegram updates (message, contact, or callback_query).
		"""
		if not isinstance(request_data, dict):
			try:
				request_data = json.loads(request_data)
			except Exception:
				request_data = {}

		# Check for button callback_query
		if "callback_query" in request_data:
			cb = request_data["callback_query"]
			msg = cb.get("message", {})
			chat_id = str(msg.get("chat", {}).get("id") or cb.get("from", {}).get("id") or "")
			payload = str(cb.get("data", "")).strip()
			from_user = cb.get("from", {})
			first_name = from_user.get("first_name", "")
			last_name = from_user.get("last_name", "")
			sender_name = f"{first_name} {last_name}".strip() or from_user.get("username", "User")

			# Acknowledge button click if live
			if self.bot_token and "id" in cb and not getattr(frappe.flags, "in_test", False):
				try:
					requests.post(
						f"{self.api_url}/answerCallbackQuery",
						json={"callback_query_id": cb["id"]},
						timeout=3,
					)
				except Exception:
					pass

			return {
				"chat_id": chat_id,
				"text": payload,
				"payload": payload,
				"sender_name": sender_name,
				"is_button": True,
				"raw": request_data,
			}

		# Standard text or contact message
		message = request_data.get("message", {})
		chat_id = str(message.get("chat", {}).get("id") or "")
		from_user = message.get("from", {})
		first_name = from_user.get("first_name", "")
		last_name = from_user.get("last_name", "")
		sender_name = f"{first_name} {last_name}".strip() or from_user.get("username", "User")

		# Check for native contact object
		if "contact" in message:
			contact = message["contact"]
			phone_number = str(contact.get("phone_number", "")).strip()
			return {
				"chat_id": chat_id,
				"text": phone_number,
				"payload": phone_number,
				"contact": contact,
				"phone_number": phone_number,
				"sender_name": sender_name,
				"is_button": False,
				"raw": request_data,
			}

		text = str(message.get("text", "")).strip()
		return {
			"chat_id": chat_id,
			"text": text,
			"payload": text,
			"sender_name": sender_name,
			"is_button": False,
			"raw": request_data,
		}


class WhatsAppProvider(BaseMessagingProvider):
	"""
	WhatsApp Business API / Meta Cloud API Provider implementation.
	Supports interactive Buttons (1-3 options) and List Messages (>3 options).
	"""

	def __init__(self, access_token: str = None, phone_number_id: str = None):
		self.access_token = access_token or frappe.conf.get("whatsapp_access_token") or os.environ.get("WHATSAPP_ACCESS_TOKEN")
		self.phone_number_id = phone_number_id or frappe.conf.get("whatsapp_phone_number_id") or os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
		self.api_url = (
			f"https://graph.facebook.com/v19.0/{self.phone_number_id}/messages"
			if self.phone_number_id
			else None
		)

	def send_text(self, chat_id: str, text: str) -> dict:
		payload = {
			"messaging_product": "whatsapp",
			"recipient_type": "individual",
			"to": str(chat_id),
			"type": "text",
			"text": {"preview_url": False, "body": text},
		}

		if not self.access_token or not self.phone_number_id or getattr(frappe.flags, "in_test", False):
			return {
				"status": "mock_sent",
				"provider": "whatsapp",
				"chat_id": str(chat_id),
				"text": text,
				"payload": payload,
			}

		try:
			headers = {
				"Authorization": f"Bearer {self.access_token}",
				"Content-Type": "application/json",
			}
			resp = requests.post(self.api_url, json=payload, headers=headers, timeout=10)
			return resp.json()
		except Exception as e:
			frappe.log_error(f"WhatsApp send_text failed: {e}", "WhatsAppProvider")
			return {"status": "error", "message": str(e)}

	def send_contact_request(self, chat_id: str, text: str, button_text: str = "📱 Share Contact") -> dict:
		return self.send_text(chat_id, text)

	def send_interactive_message(self, chat_id: str, text: str, buttons: list) -> dict:
		"""
		Maps standardized buttons to WhatsApp Interactive Messages:
		- 1 to 3 options: Interactive Buttons (reply buttons)
		- >3 options: Interactive List Messages (section rows)
		"""
		buttons = buttons or []
		num_options = len(buttons)

		if num_options <= 3:
			# WhatsApp Interactive Buttons
			wa_buttons = []
			for i, b in enumerate(buttons):
				btn_id = str(b.get("id") or b.get("payload") or f"btn_{i}")[:256]
				btn_title = str(b.get("title") or b.get("text") or f"Option {i+1}")[:20]
				wa_buttons.append({
					"type": "reply",
					"reply": {
						"id": btn_id,
						"title": btn_title,
					}
				})

			interactive_obj = {
				"type": "button",
				"body": {"text": text},
				"action": {"buttons": wa_buttons},
			}
		else:
			# WhatsApp Interactive List Messages (>3 options)
			rows = []
			for i, b in enumerate(buttons):
				row_id = str(b.get("id") or b.get("payload") or f"row_{i}")[:200]
				row_title = str(b.get("title") or b.get("text") or f"Option {i+1}")[:24]
				row_data = {"id": row_id, "title": row_title}
				if b.get("description"):
					row_data["description"] = str(b["description"])[:72]
				rows.append(row_data)

			interactive_obj = {
				"type": "list",
				"body": {"text": text},
				"action": {
					"button": "Select Option"[:20],
					"sections": [
						{
							"title": "Options"[:24],
							"rows": rows[:10],  # WhatsApp max 10 rows per section
						}
					],
				},
			}

		payload = {
			"messaging_product": "whatsapp",
			"recipient_type": "individual",
			"to": str(chat_id),
			"type": "interactive",
			"interactive": interactive_obj,
		}

		if not self.access_token or not self.phone_number_id or getattr(frappe.flags, "in_test", False):
			return {
				"status": "mock_sent",
				"provider": "whatsapp",
				"chat_id": str(chat_id),
				"text": text,
				"buttons": buttons,
				"interactive_type": interactive_obj["type"],
				"payload": payload,
			}

		try:
			headers = {
				"Authorization": f"Bearer {self.access_token}",
				"Content-Type": "application/json",
			}
			resp = requests.post(self.api_url, json=payload, headers=headers, timeout=10)
			return resp.json()
		except Exception as e:
			frappe.log_error(f"WhatsApp send_interactive_message failed: {e}", "WhatsAppProvider")
			return {"status": "error", "message": str(e)}

	def parse_incoming_webhook(self, request_data: dict) -> dict:
		"""
		Parses WhatsApp webhook payload, handling both Meta Cloud API structure
		and simplified/mock webhook payloads.
		"""
		if not isinstance(request_data, dict):
			try:
				request_data = json.loads(request_data)
			except Exception:
				request_data = {}

		# Check for Meta Cloud API nested structure
		if "entry" in request_data:
			try:
				entry = request_data.get("entry", [])[0]
				changes = entry.get("changes", [])[0]
				value = changes.get("value", {})
				contacts = value.get("contacts", [])
				sender_name = contacts[0].get("profile", {}).get("name", "WhatsApp User") if contacts else "WhatsApp User"
				messages = value.get("messages", [])

				if messages:
					msg = messages[0]
					chat_id = str(msg.get("from", ""))
					msg_type = msg.get("type", "text")

					if msg_type == "interactive":
						inter = msg.get("interactive", {})
						inter_type = inter.get("type")
						if inter_type == "button_reply":
							br = inter.get("button_reply", {})
							return {
								"chat_id": chat_id,
								"text": br.get("title", ""),
								"payload": br.get("id", ""),
								"sender_name": sender_name,
								"is_button": True,
								"raw": request_data,
							}
						elif inter_type == "list_reply":
							lr = inter.get("list_reply", {})
							return {
								"chat_id": chat_id,
								"text": lr.get("title", ""),
								"payload": lr.get("id", ""),
								"sender_name": sender_name,
								"is_button": True,
								"raw": request_data,
							}

					if msg_type == "text":
						text_body = msg.get("text", {}).get("body", "").strip()
						return {
							"chat_id": chat_id,
							"text": text_body,
							"payload": text_body,
							"sender_name": sender_name,
							"is_button": False,
							"raw": request_data,
						}

					return {
						"chat_id": chat_id,
						"text": "",
						"payload": "",
						"sender_name": sender_name,
						"is_button": False,
						"raw": request_data,
					}
			except Exception as e:
				frappe.log_error(f"Error parsing Meta WhatsApp webhook: {e}", "WhatsAppProvider")

		# Simplified / mock webhook structure fallback
		chat_id = str(request_data.get("from") or request_data.get("chat_id") or "")
		text = str(request_data.get("text", "")).strip()
		payload = str(request_data.get("payload") or request_data.get("id") or text).strip()
		is_button = bool(request_data.get("is_button", False))
		sender_name = str(request_data.get("sender_name", "WhatsApp User"))

		# If interactive object passed directly
		if "interactive" in request_data:
			inter = request_data["interactive"]
			is_button = True
			if "button_reply" in inter:
				payload = inter["button_reply"].get("id", payload)
				text = inter["button_reply"].get("title", text)
			elif "list_reply" in inter:
				payload = inter["list_reply"].get("id", payload)
				text = inter["list_reply"].get("title", text)

		return {
			"chat_id": chat_id,
			"text": text,
			"payload": payload,
			"sender_name": sender_name,
			"is_button": is_button,
			"raw": request_data,
		}


def get_messaging_provider(platform: str = "Telegram") -> BaseMessagingProvider:
	platform_norm = (platform or "telegram").strip().lower()
	if platform_norm == "telegram":
		return TelegramProvider()
	elif platform_norm in ("whatsapp", "wa"):
		return WhatsAppProvider()
	else:
		return TelegramProvider()
