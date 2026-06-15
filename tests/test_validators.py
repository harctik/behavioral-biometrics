"""Tests for app/validators.py — input validation functions.

Exercises core validators (string, email, password, phone, integer, float,
boolean, UUID, datetime, IP, URL) and schema validation.
"""

import os
import sys
import pytest

root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if root not in sys.path:
    sys.path.insert(0, root)

from app.validators import (
    validate_string,
    validate_email,
    validate_password,
    validate_integer,
    validate_float,
    validate_boolean,
    validate_uuid,
    validate_ip_address,
    validate_url,
    validate_list,
    validate_dict,
    validate_schema,
)
from app.error_handling import ValidationError


# ============================================================================
# validate_string
# ============================================================================


class TestValidateString:
    def test_valid_string(self):
        assert validate_string("hello", "name") == "hello"

    def test_strips_whitespace(self):
        assert validate_string("  hello  ", "name") == "hello"

    def test_none_required_raises(self):
        with pytest.raises(ValidationError):
            validate_string(None, "name")

    def test_none_optional_returns_empty(self):
        result = validate_string(None, "name", allow_empty=True)
        assert result == ""

    def test_too_short_raises(self):
        with pytest.raises(ValidationError):
            validate_string("a", "name", min_length=3)

    def test_too_long_raises(self):
        with pytest.raises(ValidationError):
            validate_string("a" * 300, "name", max_length=255)

    def test_non_string_raises(self):
        with pytest.raises(ValidationError):
            validate_string(123, "name")

    def test_regex_match(self):
        result = validate_string("abc123", "code", regex=r"^[a-z]+\d+$")
        assert result == "abc123"

    def test_regex_mismatch_raises(self):
        with pytest.raises(ValidationError):
            validate_string("ABC!", "code", regex=r"^[a-z]+$")


# ============================================================================
# validate_email
# ============================================================================


class TestValidateEmail:
    def test_valid_email(self):
        result = validate_email("User@Example.COM")
        assert "@" in result
        assert result == result.lower()

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            validate_email("not-an-email")

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            validate_email(None)


# ============================================================================
# validate_password
# ============================================================================


class TestValidatePassword:
    def test_strong_password(self):
        result = validate_password("MyP@ss1234")
        assert result == "MyP@ss1234"

    def test_too_short_raises(self):
        with pytest.raises(ValidationError):
            validate_password("Ab1!")

    def test_no_uppercase_raises(self):
        with pytest.raises(ValidationError):
            validate_password("lowercase1!")

    def test_no_lowercase_raises(self):
        with pytest.raises(ValidationError):
            validate_password("UPPERCASE1!")

    def test_no_digit_raises(self):
        with pytest.raises(ValidationError):
            validate_password("NoDigits!!")

    def test_no_special_char_raises(self):
        with pytest.raises(ValidationError):
            validate_password("NoSpecial1x")


# ============================================================================
# validate_integer
# ============================================================================


class TestValidateInteger:
    def test_valid_int(self):
        assert validate_integer(42, "age") == 42

    def test_string_int(self):
        assert validate_integer("10", "count") == 10

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            validate_integer(None, "count")

    def test_non_numeric_raises(self):
        with pytest.raises(ValidationError):
            validate_integer("abc", "count")

    def test_below_min_raises(self):
        with pytest.raises(ValidationError):
            validate_integer(-1, "age", min_value=0)

    def test_above_max_raises(self):
        with pytest.raises(ValidationError):
            validate_integer(200, "age", max_value=150)


# ============================================================================
# validate_float
# ============================================================================


class TestValidateFloat:
    def test_valid_float(self):
        assert validate_float(3.14, "score") == 3.14

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            validate_float(None, "score")

    def test_below_min_raises(self):
        with pytest.raises(ValidationError):
            validate_float(-0.5, "score", min_value=0.0)


# ============================================================================
# validate_boolean
# ============================================================================


class TestValidateBoolean:
    def test_true(self):
        assert validate_boolean(True, "flag") is True

    def test_false(self):
        assert validate_boolean(False, "flag") is False

    def test_string_true(self):
        assert validate_boolean("yes", "flag") is True

    def test_string_false(self):
        assert validate_boolean("no", "flag") is False

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            validate_boolean(None, "flag")

    def test_invalid_raises(self):
        with pytest.raises(ValidationError):
            validate_boolean("maybe", "flag")


# ============================================================================
# validate_uuid
# ============================================================================


class TestValidateUuid:
    def test_valid_uuid(self):
        import uuid

        uid = str(uuid.uuid4())
        assert validate_uuid(uid, "id") == uid

    def test_invalid_uuid_raises(self):
        with pytest.raises(ValidationError):
            validate_uuid("not-a-uuid-at-all-but-36-chars!!!!!", "id")


# ============================================================================
# validate_ip_address
# ============================================================================


class TestValidateIpAddress:
    def test_valid_ipv4(self):
        assert validate_ip_address("192.168.1.1", "ip") == "192.168.1.1"

    def test_valid_ipv6(self):
        result = validate_ip_address("::1", "ip")
        assert result == "::1"

    def test_invalid_ip_raises(self):
        with pytest.raises(ValidationError):
            validate_ip_address("999.999.999.999", "ip")


# ============================================================================
# validate_url
# ============================================================================


class TestValidateUrl:
    def test_valid_url(self):
        assert validate_url("https://example.com", "link") == "https://example.com"

    def test_no_scheme_raises(self):
        with pytest.raises(ValidationError):
            validate_url("example.com", "link")

    def test_require_https(self):
        with pytest.raises(ValidationError):
            validate_url("http://example.com", "link", require_https=True)


# ============================================================================
# validate_list
# ============================================================================


class TestValidateList:
    def test_valid_list(self):
        assert validate_list([1, 2, 3], "items") == [1, 2, 3]

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            validate_list(None, "items")

    def test_not_list_raises(self):
        with pytest.raises(ValidationError):
            validate_list("not a list", "items")

    def test_typed_items(self):
        result = validate_list(["a", "b"], "tags", item_type="string")
        assert result == ["a", "b"]

    def test_typed_item_mismatch_raises(self):
        with pytest.raises(ValidationError):
            validate_list([1, "two"], "tags", item_type="string")


# ============================================================================
# validate_dict
# ============================================================================


class TestValidateDict:
    def test_valid_dict(self):
        assert validate_dict({"key": "val"}, "data") == {"key": "val"}

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            validate_dict(None, "data")

    def test_not_dict_raises(self):
        with pytest.raises(ValidationError):
            validate_dict("string", "data")


# ============================================================================
# validate_schema
# ============================================================================


class TestValidateSchema:
    def test_basic_schema(self):
        schema = {
            "name": {"type": "string", "min_length": 2, "max_length": 50},
            "age": {"type": "integer", "min_value": 0, "max_value": 150},
        }
        result = validate_schema({"name": "Alice", "age": 30}, schema)
        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_missing_required_field_raises(self):
        schema = {"name": {"type": "string", "required": True}}
        with pytest.raises(ValidationError):
            validate_schema({}, schema)

    def test_optional_field_with_default(self):
        schema = {
            "role": {"type": "string", "required": False, "default": "user"},
        }
        result = validate_schema({}, schema)
        assert result["role"] == "user"
