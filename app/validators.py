"""
Comprehensive input validation for Behavior-Based Authentication API.

This module provides validation functions and decorators for request data validation,
ensuring all inputs are properly sanitized and validated before processing.
"""

import re
import ipaddress
import uuid as uuid_lib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from email_validator import validate_email as validate_email_lib, EmailNotValidError
import phonenumbers
from urllib.parse import urlparse

from .error_handling import ValidationError


# ============================================================================
# Core Validation Functions
# ============================================================================


def validate_string(
    value: Any,
    field_name: str,
    min_length: int = 1,
    max_length: int = 255,
    allow_empty: bool = False,
    regex: Optional[str] = None,
) -> str:
    """
    Validate and sanitize a string value.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        allow_empty: Whether empty strings are allowed
        regex: Optional regex pattern to match

    Returns:
        Sanitized string

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if allow_empty:
            return ""
        raise ValidationError(
            message=f"{field_name} is required",
            field_errors={field_name: "This field is required"},
        )

    if not isinstance(value, str):
        raise ValidationError(
            message=f"{field_name} must be a string",
            field_errors={field_name: "Must be a string"},
        )

    # Trim whitespace
    sanitized = value.strip()

    if not allow_empty and not sanitized:
        raise ValidationError(
            message=f"{field_name} cannot be empty",
            field_errors={field_name: "Cannot be empty"},
        )

    if len(sanitized) < min_length:
        raise ValidationError(
            message=f"{field_name} must be at least {min_length} characters",
            field_errors={field_name: f"Must be at least {min_length} characters"},
        )

    if len(sanitized) > max_length:
        raise ValidationError(
            message=f"{field_name} must be at most {max_length} characters",
            field_errors={field_name: f"Must be at most {max_length} characters"},
        )

    if regex and not re.match(regex, sanitized):
        raise ValidationError(
            message=f"{field_name} does not match required pattern",
            field_errors={field_name: "Does not match required pattern"},
        )

    return sanitized


def validate_email(email: Any, field_name: str = "email") -> str:
    """
    Validate and normalize an email address.

    Args:
        email: Email address to validate
        field_name: Name of the field for error messages

    Returns:
        Normalized email address

    Raises:
        ValidationError: If email is invalid
    """
    email_str = validate_string(email, field_name, min_length=3, max_length=255)

    try:
        # Use email-validator library for comprehensive validation
        validated = validate_email_lib(email_str, check_deliverability=False)
        return validated.email.lower()
    except EmailNotValidError as e:
        raise ValidationError(
            message=f"Invalid email address: {str(e)}",
            field_errors={field_name: "Invalid email address"},
        )


def validate_password(password: Any, field_name: str = "password") -> str:
    """
    Validate password strength.

    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (!@#$%^&*)

    Args:
        password: Password to validate
        field_name: Name of the field for error messages

    Returns:
        Validated password

    Raises:
        ValidationError: If password doesn't meet requirements
    """
    password_str = validate_string(password, field_name, min_length=8, max_length=128)

    errors = []

    if not any(c.isupper() for c in password_str):
        errors.append("at least one uppercase letter")

    if not any(c.islower() for c in password_str):
        errors.append("at least one lowercase letter")

    if not any(c.isdigit() for c in password_str):
        errors.append("at least one digit")

    if not re.search(r"[!@#$%^&*]", password_str):
        errors.append("at least one special character (!@#$%^&*)")

    if errors:
        error_msg = f"Password must contain {', '.join(errors)}"
        raise ValidationError(message=error_msg, field_errors={field_name: error_msg})

    return password_str


def validate_phone_number(phone: Any, field_name: str = "phone") -> Optional[str]:
    """
    Validate and format phone number.

    Args:
        phone: Phone number to validate
        field_name: Name of the field for error messages

    Returns:
        Formatted phone number in E.164 format, or None if phone is None/empty

    Raises:
        ValidationError: If phone number is invalid
    """
    if phone is None or (isinstance(phone, str) and not phone.strip()):
        return None

    phone_str = str(phone).strip()

    try:
        # Try to parse as international number
        parsed = phonenumbers.parse(phone_str, None)
        if not phonenumbers.is_valid_number(parsed):
            raise ValidationError(
                message="Invalid phone number",
                field_errors={field_name: "Invalid phone number"},
            )
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        raise ValidationError(
            message="Invalid phone number format",
            field_errors={field_name: "Invalid phone number format"},
        )


def validate_integer(
    value: Any,
    field_name: str,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
    """
    Validate integer value.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Validated integer

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        raise ValidationError(
            message=f"{field_name} is required",
            field_errors={field_name: "This field is required"},
        )

    try:
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValidationError(
            message=f"{field_name} must be an integer",
            field_errors={field_name: "Must be an integer"},
        )

    if min_value is not None and int_value < min_value:
        raise ValidationError(
            message=f"{field_name} must be at least {min_value}",
            field_errors={field_name: f"Must be at least {min_value}"},
        )

    if max_value is not None and int_value > max_value:
        raise ValidationError(
            message=f"{field_name} must be at most {max_value}",
            field_errors={field_name: f"Must be at most {max_value}"},
        )

    return int_value


def validate_float(
    value: Any,
    field_name: str,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> float:
    """
    Validate float value.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Validated float

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        raise ValidationError(
            message=f"{field_name} is required",
            field_errors={field_name: "This field is required"},
        )

    try:
        float_value = float(value)
    except (ValueError, TypeError):
        raise ValidationError(
            message=f"{field_name} must be a number",
            field_errors={field_name: "Must be a number"},
        )

    if min_value is not None and float_value < min_value:
        raise ValidationError(
            message=f"{field_name} must be at least {min_value}",
            field_errors={field_name: f"Must be at least {min_value}"},
        )

    if max_value is not None and float_value > max_value:
        raise ValidationError(
            message=f"{field_name} must be at most {max_value}",
            field_errors={field_name: f"Must be at most {max_value}"},
        )

    return float_value


def validate_boolean(value: Any, field_name: str) -> bool:
    """
    Validate boolean value.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages

    Returns:
        Validated boolean

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        raise ValidationError(
            message=f"{field_name} is required",
            field_errors={field_name: "This field is required"},
        )

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        lower_val = value.lower()
        if lower_val in ("true", "yes", "1", "on"):
            return True
        elif lower_val in ("false", "no", "0", "off"):
            return False

    raise ValidationError(
        message=f"{field_name} must be a boolean",
        field_errors={field_name: "Must be a boolean (true/false)"},
    )


def validate_uuid(value: Any, field_name: str) -> str:
    """
    Validate UUID string.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages

    Returns:
        Validated UUID string

    Raises:
        ValidationError: If validation fails
    """
    uuid_str = validate_string(value, field_name, min_length=36, max_length=36)

    try:
        uuid_obj = uuid_lib.UUID(uuid_str)
        return str(uuid_obj)
    except ValueError:
        raise ValidationError(
            message=f"{field_name} must be a valid UUID",
            field_errors={field_name: "Must be a valid UUID"},
        )


def validate_datetime(
    value: Any,
    field_name: str,
    format: str = "%Y-%m-%dT%H:%M:%S",
    allow_none: bool = False,
) -> Optional[datetime]:
    """
    Validate datetime string.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        format: Expected datetime format
        allow_none: Whether None values are allowed

    Returns:
        Parsed datetime object, or None if allowed and value is None

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(
            message=f"{field_name} is required",
            field_errors={field_name: "This field is required"},
        )

    if isinstance(value, datetime):
        return value

    if not isinstance(value, str):
        raise ValidationError(
            message=f"{field_name} must be a string",
            field_errors={field_name: "Must be a string"},
        )

    try:
        return datetime.strptime(value, format)
    except ValueError:
        raise ValidationError(
            message=f"{field_name} must be in format {format}",
            field_errors={field_name: f"Must be in format {format}"},
        )


def validate_ip_address(value: Any, field_name: str) -> str:
    """
    Validate IP address.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages

    Returns:
        Validated IP address string

    Raises:
        ValidationError: If validation fails
    """
    ip_str = validate_string(value, field_name, min_length=7, max_length=45)

    try:
        ipaddress.ip_address(ip_str)
        return ip_str
    except ValueError:
        raise ValidationError(
            message=f"{field_name} must be a valid IP address",
            field_errors={field_name: "Must be a valid IP address"},
        )


def validate_url(value: Any, field_name: str, require_https: bool = False) -> str:
    """
    Validate URL.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        require_https: Whether HTTPS is required

    Returns:
        Validated URL string

    Raises:
        ValidationError: If validation fails
    """
    url_str = validate_string(value, field_name, min_length=1, max_length=2048)

    try:
        parsed = urlparse(url_str)
        if not parsed.scheme:
            raise ValidationError(
                message=f"{field_name} must be a valid URL with scheme",
                field_errors={field_name: "Must be a valid URL with scheme"},
            )

        if require_https and parsed.scheme != "https":
            raise ValidationError(
                message=f"{field_name} must use HTTPS",
                field_errors={field_name: "Must use HTTPS"},
            )

        return url_str
    except Exception:
        raise ValidationError(
            message=f"{field_name} must be a valid URL",
            field_errors={field_name: "Must be a valid URL"},
        )


# ============================================================================
# Schema Validation
# ============================================================================


def validate_schema(data: Dict[str, Any], schema: Dict[str, dict]) -> Dict[str, Any]:
    """
    Validate data against a schema definition.

    Args:
        data: Data to validate
        schema: Schema definition mapping field names to validation rules

    Returns:
        Validated and sanitized data

    Raises:
        ValidationError: If validation fails
    """
    validated_data = {}
    field_errors = {}

    for field_name, rules in schema.items():
        value = data.get(field_name)
        required = rules.get("required", True)
        field_type = rules.get("type", "string")
        default = rules.get("default")

        # Handle optional fields
        if value is None and not required:
            if default is not None:
                validated_data[field_name] = default
            continue

        try:
            if field_type == "string":
                validated = validate_string(
                    value,
                    field_name,
                    min_length=rules.get("min_length", 1),
                    max_length=rules.get("max_length", 255),
                    allow_empty=rules.get("allow_empty", False),
                    regex=rules.get("regex"),
                )
            elif field_type == "email":
                validated = validate_email(value, field_name)
            elif field_type == "password":
                validated = validate_password(value, field_name)
            elif field_type == "phone":
                validated = validate_phone_number(value, field_name)
            elif field_type == "integer":
                validated = validate_integer(
                    value,
                    field_name,
                    min_value=rules.get("min_value"),
                    max_value=rules.get("max_value"),
                )
            elif field_type == "float":
                validated = validate_float(
                    value,
                    field_name,
                    min_value=rules.get("min_value"),
                    max_value=rules.get("max_value"),
                )
            elif field_type == "boolean":
                validated = validate_boolean(value, field_name)
            elif field_type == "uuid":
                validated = validate_uuid(value, field_name)
            elif field_type == "datetime":
                validated = validate_datetime(
                    value,
                    field_name,
                    format=rules.get("format", "%Y-%m-%dT%H:%M:%S"),
                    allow_none=rules.get("allow_none", False),
                )
            elif field_type == "ip":
                validated = validate_ip_address(value, field_name)
            elif field_type == "url":
                validated = validate_url(
                    value, field_name, require_https=rules.get("require_https", False)
                )
            elif field_type == "list":
                validated = validate_list(value, field_name, rules.get("item_type"))
            elif field_type == "dict":
                validated = validate_dict(value, field_name, rules.get("schema"))
            else:
                raise ValidationError(
                    message=f"Unknown field type: {field_type}",
                    field_errors={field_name: f"Unknown field type: {field_type}"},
                )

            # Apply custom validator if provided
            custom_validator = rules.get("validator")
            if custom_validator and validated is not None:
                custom_validator(validated)

            validated_data[field_name] = validated

        except ValidationError as e:
            if field_name in e.details.get("field_errors", {}):
                field_errors[field_name] = e.details["field_errors"][field_name]
            else:
                field_errors[field_name] = e.message

    if field_errors:
        raise ValidationError(
            message="Schema validation failed", field_errors=field_errors
        )

    return validated_data


def validate_list(value: Any, field_name: str, item_type: Optional[str] = None) -> List:
    """
    Validate list value.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        item_type: Type of list items ('string', 'integer', 'float', 'uuid', etc.)

    Returns:
        Validated list

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        raise ValidationError(
            message=f"{field_name} is required",
            field_errors={field_name: "This field is required"},
        )

    if not isinstance(value, list):
        raise ValidationError(
            message=f"{field_name} must be a list",
            field_errors={field_name: "Must be a list"},
        )

    if item_type and value:
        _type_checks = {
            "string": (str, "string"),
            "integer": (int, "integer"),
            "float": ((int, float), "number"),
            "boolean": (bool, "boolean"),
        }
        if item_type in _type_checks:
            expected, label = _type_checks[item_type]
            for idx, item in enumerate(value):
                if not isinstance(item, expected):
                    raise ValidationError(
                        message=f"{field_name}[{idx}] must be a {label}",
                        field_errors={
                            field_name: f"Item at index {idx} must be a {label}"
                        },
                    )
        elif item_type == "uuid":
            for idx, item in enumerate(value):
                try:
                    validate_uuid(item, f"{field_name}[{idx}]")
                except ValidationError:
                    raise ValidationError(
                        message=f"{field_name}[{idx}] must be a valid UUID",
                        field_errors={
                            field_name: f"Item at index {idx} must be a valid UUID"
                        },
                    )

    return value


def validate_dict(value: Any, field_name: str, schema: Optional[Dict] = None) -> Dict:
    """
    Validate dictionary value.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        schema: Optional schema for nested validation

    Returns:
        Validated dictionary

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        raise ValidationError(
            message=f"{field_name} is required",
            field_errors={field_name: "This field is required"},
        )

    if not isinstance(value, dict):
        raise ValidationError(
            message=f"{field_name} must be a dictionary",
            field_errors={field_name: "Must be a dictionary"},
        )

    if schema:
        return validate_schema(value, schema)

    return value
