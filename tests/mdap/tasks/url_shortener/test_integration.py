"""Integration tests for the assembled URL shortener module."""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest


# The assembled module will be importable as 'module'
from module import (
    validate_url,
    encode_base62,
    UrlStorage,
    generate_short_code,
)


class TestValidateUrl:
    def test_valid_https(self):
        assert validate_url("https://example.com") is True

    def test_valid_http(self):
        assert validate_url("http://example.com") is True

    def test_invalid_scheme(self):
        assert validate_url("ftp://example.com") is False

    def test_no_scheme(self):
        assert validate_url("example.com") is False

    def test_not_a_url(self):
        assert validate_url("not-a-url") is False

    def test_empty(self):
        assert validate_url("") is False


class TestBase62:
    def test_zero(self):
        assert encode_base62(0) == "0"

    def test_small_number(self):
        result = encode_base62(61)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_large_number(self):
        result = encode_base62(999999)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_deterministic(self):
        assert encode_base62(12345) == encode_base62(12345)


class TestStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        return UrlStorage(db_path)

    def test_store_and_lookup(self, storage):
        storage.store("abc", "https://example.com", None)
        assert storage.lookup("abc") == "https://example.com"

    def test_lookup_missing(self, storage):
        assert storage.lookup("nonexistent") is None

    def test_expired_url_returns_none(self, storage):
        past = datetime.now() - timedelta(hours=1)
        storage.store("expired", "https://example.com", past)
        assert storage.lookup("expired") is None

    def test_non_expired_url_returns_url(self, storage):
        future = datetime.now() + timedelta(hours=1)
        storage.store("valid", "https://example.com", future)
        assert storage.lookup("valid") == "https://example.com"

    def test_delete_expired(self, storage):
        past = datetime.now() - timedelta(hours=1)
        storage.store("exp1", "https://a.com", past)
        storage.store("exp2", "https://b.com", past)
        storage.store("keep", "https://c.com", None)
        count = storage.delete_expired()
        assert count == 2
        assert storage.lookup("keep") == "https://c.com"


class TestGenerateShortCode:
    @pytest.fixture
    def storage(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        return UrlStorage(db_path)

    def test_generates_string(self, storage):
        code = generate_short_code("https://example.com", storage)
        assert isinstance(code, str)
        assert len(code) > 0

    def test_same_url_same_code(self, storage):
        code1 = generate_short_code("https://example.com", storage)
        code2 = generate_short_code("https://example.com", storage)
        assert code1 == code2

    def test_different_urls_different_codes(self, storage):
        code1 = generate_short_code("https://example.com", storage)
        code2 = generate_short_code("https://other.com", storage)
        assert code1 != code2


class TestEndToEnd:
    @pytest.fixture
    def storage(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        return UrlStorage(db_path)

    def test_full_workflow(self, storage):
        url = "https://example.com/some/long/path"
        code = generate_short_code(url, storage)
        storage.store(code, url, None)
        assert storage.lookup(code) == url

    def test_full_workflow_with_expiry(self, storage):
        url = "https://example.com"
        code = generate_short_code(url, storage)
        future = datetime.now() + timedelta(hours=24)
        storage.store(code, url, future)
        assert storage.lookup(code) == url
