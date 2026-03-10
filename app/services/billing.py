from decimal import Decimal, ROUND_HALF_UP

from app.models import ActivityType, BillingCadence, BillingRate, CostRate


TWOPLACES = Decimal("0.01")
EIGHT = Decimal("8")
CD_BASE_FTE = Decimal("4.5")


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _activity_value(activity_type) -> str:
    return getattr(activity_type, "value", activity_type)


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def day_fraction(hours) -> Decimal:
    return _to_decimal(hours) / EIGHT


def billed_amount_for_entry(entry, project, billing_rate_rows, default_cd_rate=1080, cd_base_fte=4.5) -> Decimal:
    activity = _activity_value(getattr(entry, "activity_type", None))
    if activity != "PROJECT" or getattr(entry, "project_id", None) is None:
        return Decimal("0.00")

    charged_fte = _to_decimal(getattr(entry, "charged_fte", 0))
    hours_fraction = day_fraction(getattr(entry, "hours", 0))

    case_type = getattr(project, "case_type", None) if project is not None else None
    region = getattr(project, "region", None) if project is not None else None

    daily_rows = [
        row
        for row in billing_rate_rows
        if _activity_value(getattr(row, "cadence", None)) == BillingCadence.DAILY.value
        and getattr(row, "case_type", case_type) == case_type
        and getattr(row, "region", region) == region
    ]

    billed_per_day = Decimal("0")
    if daily_rows:
        tiers = {_to_decimal(row.fte): _to_decimal(row.amount) for row in daily_rows}

        if charged_fte in tiers:
            billed_per_day = tiers[charged_fte]
        else:
            sorted_ftes = sorted(tiers.keys())
            lower_candidates = [fte for fte in sorted_ftes if fte < charged_fte]
            upper_candidates = [fte for fte in sorted_ftes if fte > charged_fte]

            lower = max(lower_candidates) if lower_candidates else None
            upper = min(upper_candidates) if upper_candidates else None

            if lower is not None and upper is not None:
                lower_amount = tiers[lower]
                upper_amount = tiers[upper]
                billed_per_day = lower_amount + ((charged_fte - lower) / (upper - lower)) * (upper_amount - lower_amount)
            elif len(tiers) == 1 and _to_decimal(cd_base_fte) in tiers:
                billed_per_day = tiers[_to_decimal(cd_base_fte)] * (charged_fte / _to_decimal(cd_base_fte))
    elif case_type in {"IP (Z5LB/J2RC)", "Other CD/IP Codes", "Investment"}:
        billed_per_day = _to_decimal(default_cd_rate) * (charged_fte / _to_decimal(cd_base_fte))

    billed_amount = billed_per_day * hours_fraction
    return _quantize_money(billed_amount)


def cost_amount_for_entry(entry, team_member, cost_rate) -> Decimal:
    if team_member is None or cost_rate is None:
        return Decimal("0.00")

    cost_per_day = _to_decimal(cost_rate.cost_per_day)
    cost_amount = cost_per_day * day_fraction(getattr(entry, "hours", 0))
    return _quantize_money(cost_amount)


def compute_entry_financials(entry, billing_rate_rows=None, cost_rate_by_level=None) -> dict:
    warnings = []

    project = getattr(entry, "project", None)
    if billing_rate_rows is None:
        if getattr(entry, "project_id", None) is not None and project is not None:
            billing_rows = BillingRate.query.filter_by(
                case_type=project.case_type,
                region=project.region,
                cadence=BillingCadence.DAILY.value,
            ).all()
        else:
            billing_rows = []
    else:
        billing_rows = billing_rate_rows

    billed_amount = billed_amount_for_entry(entry, project, billing_rows)

    activity = _activity_value(getattr(entry, "activity_type", None))
    if activity == "PROJECT" and getattr(entry, "project_id", None) is not None:
        case_type = getattr(project, "case_type", None) if project is not None else None
        if billed_amount == Decimal("0.00") and case_type not in {"IP (Z5LB/J2RC)", "Other CD/IP Codes", "Investment"}:
            warnings.append("Missing billing rate")

    team_member = getattr(entry, "team_member", None)
    cost_rate = None
    if team_member is not None:
        level_value = getattr(team_member.level, "value", team_member.level)
        if cost_rate_by_level is not None:
            cost_rate = cost_rate_by_level.get(str(level_value))
        else:
            cost_rate = CostRate.query.filter_by(level=level_value).first()

    cost_amount = cost_amount_for_entry(entry, team_member, cost_rate)
    if team_member is None or cost_rate is None:
        warnings.append("Missing cost rate")

    margin = _quantize_money(billed_amount - cost_amount)

    return {
        "billed_amount": billed_amount,
        "cost_amount": cost_amount,
        "margin": margin,
        "warnings": warnings,
    }


def compute_totals_from_financials(row_financials: dict) -> dict:
    total_billed = Decimal("0.00")
    total_cost = Decimal("0.00")
    total_margin = Decimal("0.00")

    for row in row_financials.values():
        total_billed += row["billed_amount"]
        total_cost += row["cost_amount"]
        total_margin += row["margin"]

    return {
        "billed_amount": _quantize_money(total_billed),
        "cost_amount": _quantize_money(total_cost),
        "margin": _quantize_money(total_margin),
    }


def compute_totals_for_entries(entries) -> dict:
    total_billed = Decimal("0.00")
    total_cost = Decimal("0.00")
    total_margin = Decimal("0.00")

    for entry in entries:
        row = compute_entry_financials(entry)
        total_billed += row["billed_amount"]
        total_cost += row["cost_amount"]
        total_margin += row["margin"]

    return {
        "billed_amount": _quantize_money(total_billed),
        "cost_amount": _quantize_money(total_cost),
        "margin": _quantize_money(total_margin),
    }
