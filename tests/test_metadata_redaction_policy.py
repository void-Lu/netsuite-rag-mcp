import json
from datetime import date, datetime

from netsuite_rag_mcp.metadata import from_chroma_metadata, metadata_matches_filters, to_chroma_metadata
from netsuite_rag_mcp.policy import build_answer_policy
from netsuite_rag_mcp.redaction import redact_sensitive_text


def test_metadata_round_trip_array_fields():
    original = {
        "type": "script",
        "script_type": "restlet",
        "related_records": ["salesorder", "itemfulfillment"],
        "related_script_ids": ["customscript_order_sync_mr"],
        "tags": ["netsuite", "restlet"],
    }

    stored = to_chroma_metadata(original)
    restored = from_chroma_metadata(stored)

    assert stored["related_records_json"] == '["salesorder", "itemfulfillment"]'
    assert restored["related_records"] == ["salesorder", "itemfulfillment"]
    assert restored["related_script_ids"] == ["customscript_order_sync_mr"]
    assert metadata_matches_filters(restored, {"script_type": "restlet", "related_records": "salesorder"})
    assert not metadata_matches_filters(restored, {"related_records": "invoice"})


def test_to_chroma_metadata_serializes_date_and_datetime_as_iso_strings():
    stored = to_chroma_metadata(
        {
            "business_date": date(2026, 5, 13),
            "indexed_at": datetime(2026, 5, 13, 9, 30),
        }
    )

    assert stored["business_date"] == "2026-05-13"
    assert stored["indexed_at"] == "2026-05-13T09:30:00"


def test_to_chroma_metadata_serializes_nested_date_and_datetime_metadata():
    stored = to_chroma_metadata(
        {
            "complex": {
                "business_date": date(2026, 5, 13),
                "events": [{"indexed_at": datetime(2026, 5, 13, 9, 30)}],
            }
        }
    )

    complex_metadata = json.loads(stored["complex"])
    assert complex_metadata["business_date"] == "2026-05-13"
    assert complex_metadata["events"][0]["indexed_at"] == "2026-05-13 09:30:00"


def test_redact_sensitive_text_masks_private_values():
    text = "手机号 13812345678, token sk-abc1234567890, email user@example.com"

    redacted = redact_sensitive_text(text)

    assert "13812345678" not in redacted