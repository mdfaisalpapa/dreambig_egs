# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import functools
import frappe
from frappe import _


def portal_api(fn):
    """
    Decorator for EGS portal & chatbot APIs:
    1. Returns standard Python dictionary if called internally.
    2. Catches exceptions and formats uniform JSON response for headless HTTP clients & universal_chatbot:
       {"success": True, "data": ...} or {"success": False, "error_code": ..., "message": ...}
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        is_api_request = (
            frappe.request
            and (
                getattr(frappe.request, "path", "").startswith("/api/method/")
                or frappe.get_request_header("Accept") == "application/json"
                or getattr(frappe, "form_dict", {}).get("cmd")
            )
        )

        try:
            result = fn(*args, **kwargs)
            if is_api_request and isinstance(result, dict) and "success" not in result:
                return {"success": True, "data": result}
            return result

        except frappe.PermissionError as pe:
            if not is_api_request:
                raise pe
            frappe.response["http_status_code"] = 403
            return {
                "success": False,
                "error_code": "PERMISSION_DENIED",
                "message": str(pe) or _("You do not have permission to perform this action."),
            }

        except frappe.ValidationError as ve:
            if not is_api_request:
                raise ve
            frappe.response["http_status_code"] = 400
            return {
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "message": str(ve) or _("Invalid data submitted."),
            }

        except Exception as e:
            if not is_api_request:
                raise e
            frappe.log_error(title=f"EGS API Exception in {fn.__name__}", message=frappe.get_traceback())
            frappe.response["http_status_code"] = 500
            return {
                "success": False,
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": str(e) or _("An unexpected error occurred. Please contact program coordinators."),
            }

    return wrapper
