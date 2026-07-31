"""The browser inspector must use the retained generated contract objects."""

from pathlib import Path

from scripts.build_network_demo_data import OUTPUT, build_data, render


ROOT = Path(__file__).resolve().parents[1]


def test_browser_data_bundle_is_generated_without_drift() -> None:
    assert OUTPUT.read_text(encoding="utf-8") == render()


def test_browser_bundle_is_synthetic_and_retains_authority_boundaries() -> None:
    data = build_data()
    operations = data["provider_operations"]
    document = data["care_document"]
    extraction = data["document_extraction"]
    grant = data["document_share_grant"]
    decision = data["document_share"]["decision"]
    post_revoke = data["document_post_revocation"]["decision"]

    assert document["privacy"]["contains_real_phi"] is False
    assert document["clinically_authoritative"] is False
    assert extraction["clinically_verified"] is False
    assert extraction["shareable"] is False
    assert grant["raw_document_sharing_allowed"] is False
    assert grant["unapproved_items_allowed"] is False
    assert decision["outcome"] == "permit"
    assert post_revoke["outcome"] == "deny"
    assert "grant_revoked" in post_revoke["reason_codes"]
    assert operations["care_context_count"] == 3
    assert operations["application_count"] == 3
    assert operations["decision_count"] == 10
    assert operations["permit_count"] == 3
    assert operations["deny_count"] == 7
    assert operations["field_outcomes_measured"] is False
    assert any("No time saved" in item for item in operations["non_claims"])


def test_browser_page_loads_generated_bundle_before_behavior() -> None:
    html = (ROOT / "demo" / "network.html").read_text(encoding="utf-8")
    assert '<script src="network-data.js?v=0.4.1"></script>' in html
    assert '<script src="network.js?v=0.4.1"></script>' in html
    assert html.index('src="network-data.js') < html.index('src="network.js')
