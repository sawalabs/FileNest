import pytest
from httpx import AsyncClient

from backend.app.core.security import safe_regex_search, validate_regex_pattern
from backend.app.services.rules_automation import RulesAutomationService


def test_validate_regex_pattern_valid():
    """Verify standard legitimate regex patterns are permitted."""
    valid_patterns = [
        r"^Invoice_[0-9]{4}\.pdf$",
        r"\.(jpe?g|png|webp)$",
        r"^backup_.*",
        r"^[a-zA-Z0-9_-]+\.docx$",
        r"Document_(draft|final)_[0-9]+",
    ]
    for pattern in valid_patterns:
        assert validate_regex_pattern(pattern) == pattern


@pytest.mark.parametrize(
    "invalid_syntax",
    [
        r"[a-z",  # unclosed character class
        r"*starting_wildcard",  # invalid quantifier position
        r"(unclosed_group",  # unclosed group
        r"(\d+",
    ],
)
def test_validate_regex_pattern_syntax_errors(invalid_syntax: str):
    """Verify syntactically broken regex patterns raise ValueError."""
    with pytest.raises(ValueError, match="Sintaks regex tidak valid"):
        validate_regex_pattern(invalid_syntax)


@pytest.mark.parametrize(
    "redos_pattern",
    [
        r"(a+)+$",  # classic nested quantifier
        r"(a*)*$",
        r"([a-zA-Z]+)+",
        r"(foo+)*",
        r"(\d+){1,10}",
        r"(a|b+)+",
        r"([0-9]*)*",
        r".*.*",  # adjacent unbounded wildcards
        r".+.*",
    ],
)
def test_validate_regex_pattern_redos_rejected(redos_pattern: str):
    """Verify regex patterns prone to catastrophic backtracking (ReDoS) are rejected."""
    with pytest.raises(ValueError, match="(nested quantifiers|ReDoS|wildcard berturut-turut)"):
        validate_regex_pattern(redos_pattern)


def test_validate_regex_pattern_length_limit():
    """Verify excessively long regex patterns are rejected."""
    long_pattern = "a" * 300
    with pytest.raises(ValueError, match="Pola regex terlalu panjang"):
        validate_regex_pattern(long_pattern, max_length=256)


def test_safe_regex_search_standard_matching():
    """Verify safe_regex_search works properly for valid matches and non-matches."""
    pattern = r"^Invoice_\d+\.pdf$"
    assert safe_regex_search(pattern, "Invoice_2026.pdf") is True
    assert safe_regex_search(pattern, "Receipt_2026.pdf") is False
    assert safe_regex_search(pattern, None) is False


def test_safe_regex_search_blocks_redos():
    """Verify safe_regex_search rejects ReDoS patterns safely without throwing uncaught exceptions."""
    assert safe_regex_search(r"(a+)+$", "aaaaaaaaaaaaaaaaaaaaaaaaaaaa!") is False
    assert safe_regex_search(r".*.*", "any_file.txt") is False


@pytest.mark.asyncio
async def test_rule_creation_rejects_redos_condition(async_client: AsyncClient, tmp_path):
    """Verify creating an organization rule with a ReDoS regex pattern is rejected by API."""
    # 1. Register a managed folder
    folder_dir = tmp_path / "rules_folder"
    folder_dir.mkdir()
    res_f = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rules Test Folder", "root_path": str(folder_dir)},
    )
    assert res_f.status_code in (200, 201)
    folder_id = res_f.json()["id"]

    # 2. Attempt to create rule with nested quantifier ReDoS condition
    malicious_rule_payload = {
        "managed_folder_id": folder_id,
        "name": "Malicious ReDoS Rule",
        "rule_type": "organize",
        "scope": {"subpath": ""},
        "conditions": [
            {
                "field": "name",
                "operator": "matches_regex",
                "value": "(a+)+$",
            }
        ],
        "actions": [
            {
                "action_type": "move",
                "target_directory": "Archived",
            }
        ],
    }

    res = await async_client.post("/api/v1/rules", json=malicious_rule_payload)
    assert res.status_code in (400, 422)
    assert "ReDoS" in str(res.json())


@pytest.mark.asyncio
async def test_rule_creation_accepts_safe_regex_condition(async_client: AsyncClient, tmp_path):
    """Verify creating a rule with legitimate safe regex pattern succeeds."""
    folder_dir = tmp_path / "rules_folder_safe"
    folder_dir.mkdir()
    res_f = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Safe Rules Folder", "root_path": str(folder_dir)},
    )
    assert res_f.status_code in (200, 201)
    folder_id = res_f.json()["id"]

    safe_rule_payload = {
        "managed_folder_id": folder_id,
        "name": "Safe Invoice Rule",
        "rule_type": "organize",
        "scope": {"subpath": ""},
        "conditions": [
            {
                "field": "name",
                "operator": "matches_regex",
                "value": r"^Invoice_\d{4}\.pdf$",
            }
        ],
        "actions": [
            {
                "action_type": "move",
                "target_directory": "Invoices",
            }
        ],
    }

    res = await async_client.post("/api/v1/rules", json=safe_rule_payload)
    assert res.status_code in (200, 201)
    data = res.json()
    assert data["name"] == "Safe Invoice Rule"
    assert data["conditions"][0]["value"] == r"^Invoice_\d{4}\.pdf$"
