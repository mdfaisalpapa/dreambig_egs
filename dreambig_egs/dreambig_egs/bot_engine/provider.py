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
	def send_interactive_buttons(self, chat_id: str, text: str, buttons: list) -> dict:
		"""
		Sends a message accompanied by interactive button choices.
		buttons format: [{"title": "Button Title", "payload": "CALLBACK_VALUE"}]
		"""
		pass

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
		if not self.bot_token:
			# Mock/testing fallback if token is not configured in environment
			return {
				"status": "mock_sent",
				"provider": "telegram",
				"chat_id": chat_id,
				"text": text,
			}

		url = f"{self.api_url}/sendMessage"
		payload = {
			"chat_id": chat_id,
			"text": text,
			"parse_mode": "Markdown",
		}

		try:
			resp = requests.post(url, json=payload, timeout=10)
			return resp.json()
		except Exception as e:
			frappe.log_error(f"Telegram send_text failed: {e}", "TelegramProvider")
			return {"status": "error", "message": str(e)}

	def send_interactive_buttons(self, chat_id: str, text: str, buttons: list) -> dict:
		"""
		Converts generic buttons [{"title": "...", "payload": "..."}] into
		Telegram InlineKeyboardMarkup vertical rows.
		"""
		if not self.bot_token:
			return {
				"status": "mock_sent",
				"provider": "telegram",
				"chat_id": chat_id,
				"text": text,
				"buttons": buttons,
			}

		inline_keyboard = []
		for b in buttons:
			title = b.get("title") or b.get("text") or "Select"
			callback = b.get("payload") or b.get("callback_data") or title
			inline_keyboard.append([{"text": title, "callback_data": str(callback)}])

		url = f"{self.api_url}/sendMessage"
		payload = {
			"chat_id": chat_id,
			"text": text,
			"parse_mode": "Markdown",
			"reply_markup": {"inline_keyboard": inline_keyboard},
		}

		try:
			resp = requests.post(url, json=payload, timeout=10)
			return resp.json()
		except Exception as e:
			frappe.log_error(f"Telegram send_interactive_buttons failed: {e}", "TelegramProvider")
			return {"status": "error", "message": str(e)}

	def parse_incoming_webhook(self, request_data: dict) -> dict:
		"""
		Normalizes incoming Telegram updates (message or callback_query).
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
			chat_id = str(msg.get("chat", {}).get("id") or cb.get("from", {}).get("id"))
			payload = str(cb.get("data", "")).strip()
			from_user = cb.get("from", {})
			first_name = from_user.get("first_name", "")
			last_name = from_user.get("last_name", "")
			sender_name = f"{first_name} {last_name}".strip() or from_user.get("username", "User")

			# Attempt answerCallbackQuery to acknowledge button click
			if self.bot_token and "id" in cb:
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

		# Standard text message
		message = request_data.get("message", {})
		chat_id = str(message.get("chat", {}).get("id") or "")
		text = str(message.get("text", "")).strip()
		from_user = message.get("from", {})
		first_name = from_user.get("first_name", "")
		last_name = from_user.get("last_name", "")
		sender_name = f"{first_name} {last_name}".strip() or from_user.get("username", "User")

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
	WhatsApp Business API / Cloud API Provider adapter stub.
	Ready for plug-and-play integration.
	"""

	def __init__(self, access_token: str = None, phone_number_id: str = None):
		self.access_token = access_token or frappe.conf.get("whatsapp_access_token")
		self.phone_number_id = phone_number_id or frappe.conf.get("whatsapp_phone_number_id")

	def send_text(self, chat_id: str, text: str) -> dict:
		return {
			"status": "mock_sent",
			"provider": "whatsapp",
			"chat_id": chat_id,
			"text": text,
		}

	def send_interactive_buttons(self, chat_id: str, text: str, buttons: list) -> dict:
		return {
			"status": "mock_sent",
			"provider": "whatsapp",
			"chat_id": chat_id,
			"text": text,
			"buttons": buttons,
		}

	def parse_incoming_webhook(self, request_data: dict) -> dict:
		# Generic WhatsApp cloud webhook parser structure
		return {
			"chat_id": str(request_data.get("from", "")),
			"text": str(request_data.get("text", "")),
			"payload": str(request_data.get("payload", "")),
			"sender_name": "WhatsApp User",
			"is_button": False,
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
