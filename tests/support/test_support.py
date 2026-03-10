import pytest

from app.support.capitated_rejection_codes import CapitatedRejectionCodes
from app.support.format_service import FormatService
from app.support.helpers.misc import env_any
from app.support.json_decode import JsonDecode
from app.support.password_policy import PasswordPolicy
from app.support.realm import Realm, _current_realm_var


# ── Realm ─────────────────────────────────────────────────────────────────────

class TestRealm:
    def setup_method(self):
        _current_realm_var.set(None)

    def test_constants(self):
        assert Realm.ADMIN == "admin"
        assert Realm.CUSTOMER == "customer"

    def test_all(self):
        assert Realm.all() == ["admin", "customer"]

    def test_is_valid(self):
        assert Realm.is_valid("admin") is True
        assert Realm.is_valid("customer") is True
        assert Realm.is_valid("other") is False
        assert Realm.is_valid(None) is False

    def test_set_and_get_current(self):
        Realm.set_current("admin")
        assert Realm.current() == "admin"

    def test_set_invalid_returns_none(self):
        Realm.set_current("hacker")
        assert Realm.current() is None

    def test_is_admin(self):
        Realm.set_current("admin")
        assert Realm.is_admin() is True
        assert Realm.is_customer() is False

    def test_is_customer(self):
        Realm.set_current("customer")
        assert Realm.is_customer() is True
        assert Realm.is_admin() is False


# ── CapitatedRejectionCodes ───────────────────────────────────────────────────

class TestCapitatedRejectionCodes:
    def test_constants_exist(self):
        assert CapitatedRejectionCodes.PLAN_INVALID_PRODUCT == "PLAN_INVALID_PRODUCT"
        assert CapitatedRejectionCodes.PERSON_SEX_INVALID == "PERSON_SEX_INVALID"
        assert CapitatedRejectionCodes.UNKNOWN_ERROR == "UNKNOWN_ERROR"
        assert CapitatedRejectionCodes.CONTINUITY_BREAK == "CONTINUITY_BREAK"

    def test_not_instantiable(self):
        with pytest.raises(TypeError):
            CapitatedRejectionCodes()


# ── JsonDecode ────────────────────────────────────────────────────────────────

class TestJsonDecode:
    def test_attribute_access(self):
        obj = JsonDecode({"name": "GFA", "active": True})
        assert obj.name == "GFA"
        assert obj.active is True
        assert obj.missing is None

    def test_item_access(self):
        obj = JsonDecode({"key": "value"})
        assert obj["key"] == "value"
        assert obj["missing"] is None

    def test_iteration(self):
        obj = JsonDecode({"a": 1, "b": 2})
        assert set(obj) == {"a", "b"}

    def test_to_array(self):
        data = {"x": 1}
        obj = JsonDecode(data)
        assert obj.to_array() == data

    def test_get_empty(self):
        assert JsonDecode.get(None) == []
        assert JsonDecode.get("") == []
        assert JsonDecode.get("   ") == []

    def test_get_object(self):
        result = JsonDecode.get('{"name": "test", "value": 42}')
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_get_array(self):
        result = JsonDecode.get('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_get_nested(self):
        result = JsonDecode.get('{"outer": {"inner": "yes"}}')
        assert result["outer"].inner == "yes"

    def test_get_invalid_json(self):
        assert JsonDecode.get("not json") == []


# ── FormatService ─────────────────────────────────────────────────────────────

class TestFormatService:
    def test_date_es(self):
        fmt = FormatService("es")
        assert fmt.date("2026-03-10") == "10/03/2026"

    def test_date_en(self):
        fmt = FormatService("en")
        assert fmt.date("2026-03-10") == "03/10/2026"

    def test_date_none(self):
        fmt = FormatService("es")
        assert fmt.date(None) is None

    def test_integer_es(self):
        fmt = FormatService("es")
        result = fmt.integer(12345)
        assert "12" in result and "345" in result

    def test_decimal_es(self):
        fmt = FormatService("es")
        result = fmt.decimal(1234.5)
        assert result is not None

    def test_decimal_none_nullable(self):
        fmt = FormatService("es")
        assert fmt.decimal(None, nullable=True) is None

    def test_decimal_none_not_nullable(self):
        fmt = FormatService("es")
        result = fmt.decimal(None, nullable=False)
        assert result is not None

    def test_decimal_or_dash_none(self):
        fmt = FormatService("es")
        assert fmt.decimal_or_dash(None) == "–"

    def test_money(self):
        fmt = FormatService("en")
        result = fmt.money(1000.0, "USD")
        assert result is not None
        assert "1" in result


# ── PasswordPolicy ────────────────────────────────────────────────────────────

class TestPasswordPolicy:
    def setup_method(self):
        self.policy = PasswordPolicy()

    def test_valid_password(self):
        errors = self.policy.validate("SecurePass1!")
        assert errors == []

    def test_too_short(self):
        errors = self.policy.validate("Ab1!")
        assert any("caracteres" in e for e in errors)

    def test_no_uppercase(self):
        errors = self.policy.validate("securepass1!")
        assert any("mayúscula" in e for e in errors)

    def test_no_lowercase(self):
        errors = self.policy.validate("SECUREPASS1!")
        assert any("minúscula" in e for e in errors)

    def test_no_numbers(self):
        errors = self.policy.validate("SecurePass!!")
        assert any("número" in e for e in errors)

    def test_no_symbols(self):
        errors = self.policy.validate("SecurePass11")
        assert any("símbolo" in e for e in errors)

    def test_banned_word(self):
        errors = self.policy.validate("Password1!")
        assert any("patrones inseguros" in e for e in errors)

    def test_user_parts_forbidden(self):
        errors = self.policy.validate("JohnPass1!", context={"first_name": "John"})
        assert any("personal" in e for e in errors)

    def test_for_frontend(self):
        data = self.policy.for_frontend()
        assert "min" in data
        assert "require" in data
        assert "messages" in data


# ── env_any ───────────────────────────────────────────────────────────────────

class TestEnvAny:
    def test_false_when_not_set(self):
        assert env_any("NONEXISTENT_VAR_XYZ") is False

    def test_true_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_FLAG", "true")
        assert env_any("TEST_FLAG") is True

    def test_list_param(self, monkeypatch):
        monkeypatch.setenv("FLAG_A", "false")
        monkeypatch.setenv("FLAG_B", "true")
        assert env_any(["FLAG_A", "FLAG_B"]) is True

    def test_invalid_param(self):
        with pytest.raises(ValueError):
            env_any(123)
