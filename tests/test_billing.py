import sys
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.billing import billed_amount_for_entry, compute_entry_financials


def test_billed_amount_interpolates_between_tiers():
    entry = SimpleNamespace(activity_type="PROJECT", project_id=1, charged_fte=Decimal("3.0"), hours=Decimal("8.0"))
    project = SimpleNamespace(case_type="Client billed", region="AMER")
    rows = [
        SimpleNamespace(case_type="Client billed", region="AMER", cadence="DAILY", fte=Decimal("2.5"), amount=Decimal("2100")),
        SimpleNamespace(case_type="Client billed", region="AMER", cadence="DAILY", fte=Decimal("3.5"), amount=Decimal("2960")),
    ]

    billed = billed_amount_for_entry(entry, project, rows)
    assert billed == Decimal("2530.00")


def test_billed_amount_prorates_from_4_5_when_only_single_tier():
    entry = SimpleNamespace(activity_type="PROJECT", project_id=1, charged_fte=Decimal("2.25"), hours=Decimal("8.0"))
    project = SimpleNamespace(case_type="Client billed", region="AMER")
    rows = [
        SimpleNamespace(case_type="Client billed", region="AMER", cadence="DAILY", fte=Decimal("4.5"), amount=Decimal("3800")),
    ]

    billed = billed_amount_for_entry(entry, project, rows)
    assert billed == Decimal("1900.00")


def test_cd_ip_rule_applies_1080_per_day_scaled_by_hours():
    entry = SimpleNamespace(activity_type="PROJECT", project_id=1, charged_fte=Decimal("4.5"), hours=Decimal("4.0"))
    project = SimpleNamespace(case_type="IP (Z5LB/J2RC)", region="AMER")

    billed = billed_amount_for_entry(entry, project, billing_rate_rows=[])
    assert billed == Decimal("540.00")


def test_non_project_activity_is_not_billed():
    entry = SimpleNamespace(activity_type="VACATION", project_id=1, charged_fte=Decimal("1.0"), hours=Decimal("8.0"))
    project = SimpleNamespace(case_type="Client billed", region="AMER")

    billed = billed_amount_for_entry(entry, project, billing_rate_rows=[])
    assert billed == Decimal("0.00")


def test_compute_financials_warns_when_cost_rate_missing():
    entry = SimpleNamespace(
        activity_type="BENCH",
        project_id=None,
        charged_fte=Decimal("1.0"),
        hours=Decimal("8.0"),
        project=None,
        team_member=None,
    )

    result = compute_entry_financials(entry)
    assert result["cost_amount"] == Decimal("0.00")
    assert "Missing cost rate" in result["warnings"]

