from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_email_with_plus_address() -> None:
    out = scrub_text("Send a copy to student+lab@sub.vinuni.edu.vn.")
    assert "student+lab@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    out = scrub_text("CCCD: 079203001234")
    assert "079203001234" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card_formats() -> None:
    for card_number in ("4111111111111111", "4111 1111 1111 1111", "4111-1111-1111-1111"):
        out = scrub_text(f"Card: {card_number}")
        assert card_number not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_phone_pattern_does_not_scrub_longer_number() -> None:
    out = scrub_text("Reference: 09012345678")
    assert "REDACTED_PHONE_VN" not in out


def test_scrub_passport() -> None:
    out = scrub_text("Passport: A12345678")
    assert "A12345678" not in out
    assert "REDACTED_PASSPORT" in out or "REDACTED_VIETNAMESE_PASSPORT" in out


def test_scrub_vietnamese_id() -> None:
    out = scrub_text("ID: 123456789")
    assert "123456789" not in out
    assert "REDACTED_VIETNAMESE_ID" in out


def test_scrub_vietnamese_passport() -> None:
    out = scrub_text("Passport: B98765432")
    assert "B98765432" not in out
    assert "REDACTED_VIETNAMESE_PASSPORT" in out


def test_scrub_vietnamese_driver_license() -> None:
    out = scrub_text("Driver License: AB123456")
    assert "AB123456" not in out
    assert "REDACTED_VIETNAMESE_DRIVER_LICENSE" in out


def test_scrub_vietnamese_health_insurance() -> None:
    out = scrub_text("Health Insurance: 1234567890")
    assert "1234567890" not in out
    assert "REDACTED_VIETNAMESE_HEALTH_INSURANCE" in out


def test_scrub_vietnamese_address() -> None:
    for address in (
        "so 8 pho Hoang Hoa Tham",
        "duong Nguyen Trai, quan 1",
        "hem 12 Le Loi",
    ):
        out = scrub_text(f"Ship to {address}")
        assert "REDACTED_VIETNAMESE_ADDRESS" in out


def test_scrub_text_does_not_mangle_ordinary_numerics() -> None:
    # Regression guard: an over-greedy address pattern used to redact "1.2.3".
    for text in (
        "version 1.2.3 build 2024",
        "latency 1234ms cost 0.000123 usd",
        "ts 2026-09-29T10:00:00Z",
        "user u_student_01 session s_demo_01",
    ):
        assert scrub_text(text) == text


def test_scrub_multiple_pii_types() -> None:
    text = "Email: test@example.com, Phone: 0901234567, CCCD: 079203001234"
    out = scrub_text(text)
    assert "test@example.com" not in out
    assert "0901234567" not in out
    assert "079203001234" not in out
    assert "REDACTED_EMAIL" in out
    assert "REDACTED_PHONE_VN" in out
    assert "REDACTED_CCCD" in out
