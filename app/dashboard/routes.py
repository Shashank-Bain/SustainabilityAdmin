from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
import csv
import io

from flask import Blueprint, Response, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.orm import joinedload

from app.models import ActivityType, BillingCadence, BillingRate, CostRate, StaffingEntry, Team, User
from app.services.billing import compute_entry_financials, compute_totals_from_financials


dashboard_bp = Blueprint("dashboard_bp", __name__, url_prefix="/dashboard")

TWOPLACES = Decimal("0.01")


def _parse_month(month_value: str | None) -> tuple[str, date, date]:
    if month_value:
        try:
            month_start = datetime.strptime(month_value, "%Y-%m").date().replace(day=1)
        except ValueError:
            today = date.today()
            month_start = today.replace(day=1)
    else:
        today = date.today()
        month_start = today.replace(day=1)

    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)

    return month_start.strftime("%Y-%m"), month_start, month_end


def _decimal_hours(value) -> Decimal:
    return Decimal(str(value or 0))


def _utilization_percent(billable_hours: Decimal, total_hours: Decimal) -> Decimal:
    if total_hours == 0:
        return Decimal("0.00")
    return ((billable_hours / total_hours) * Decimal("100")).quantize(TWOPLACES)


def _get_filtered_entries(month_start: date, month_end: date, manager_id: int | None, team_id: int | None):
    query = StaffingEntry.query.options(
        joinedload(StaffingEntry.project),
        joinedload(StaffingEntry.team),
        joinedload(StaffingEntry.team_member),
        joinedload(StaffingEntry.manager_user),
    ).filter(
        StaffingEntry.work_date >= month_start,
        StaffingEntry.work_date < month_end,
    )

    if manager_id:
        query = query.filter(StaffingEntry.manager_user_id == manager_id)
    if team_id:
        query = query.filter(StaffingEntry.team_id == team_id)

    return query.order_by(StaffingEntry.work_date.asc(), StaffingEntry.id.asc()).all()


def _build_dashboard_data(entries, month_start: date, month_end: date):
    billing_rates_daily = BillingRate.query.filter_by(cadence=BillingCadence.DAILY.value).all()
    cost_rate_by_level = {
        str(getattr(cost_rate.level, "value", cost_rate.level)): cost_rate
        for cost_rate in CostRate.query.all()
    }

    row_financials = {}
    manager_summary = defaultdict(lambda: {
        "label": "Unknown",
        "billed": Decimal("0.00"),
        "cost": Decimal("0.00"),
        "margin": Decimal("0.00"),
        "billable_hours": Decimal("0.00"),
        "total_hours": Decimal("0.00"),
    })
    team_summary = defaultdict(lambda: {
        "label": "Unknown",
        "billed": Decimal("0.00"),
        "cost": Decimal("0.00"),
        "margin": Decimal("0.00"),
        "billable_hours": Decimal("0.00"),
        "total_hours": Decimal("0.00"),
    })
    project_summary = defaultdict(lambda: {
        "case_code": "",
        "project_name": "",
        "case_type": "",
        "region": "",
        "team": "-",
        "project_obj": None,
        "billed": Decimal("0.00"),
        "cost": Decimal("0.00"),
        "margin": Decimal("0.00"),
        "hours": Decimal("0.00"),
    })
    project_entry_bounds = {}

    for entry in entries:
        financial = compute_entry_financials(
            entry,
            billing_rate_rows=billing_rates_daily,
            cost_rate_by_level=cost_rate_by_level,
        )
        row_financials[entry.id] = financial

        hours = _decimal_hours(entry.hours)
        activity = getattr(entry.activity_type, "value", entry.activity_type)
        is_billable = activity == ActivityType.PROJECT.value and entry.project_id is not None
        billable_hours = hours if is_billable else Decimal("0.00")

        manager_bucket = manager_summary[entry.manager_user_id]
        manager_bucket["label"] = entry.manager_user.name if entry.manager_user else f"User {entry.manager_user_id}"
        manager_bucket["billed"] += financial["billed_amount"]
        manager_bucket["cost"] += financial["cost_amount"]
        manager_bucket["margin"] += financial["margin"]
        manager_bucket["billable_hours"] += billable_hours
        manager_bucket["total_hours"] += hours

        team_bucket = team_summary[entry.team_id]
        team_bucket["label"] = entry.team.name if entry.team else f"Team {entry.team_id}"
        team_bucket["billed"] += financial["billed_amount"]
        team_bucket["cost"] += financial["cost_amount"]
        team_bucket["margin"] += financial["margin"]
        team_bucket["billable_hours"] += billable_hours
        team_bucket["total_hours"] += hours

        if entry.project_id is not None and entry.project is not None:
            project_bucket = project_summary[entry.project_id]
            project_bucket["case_code"] = entry.project.case_code
            project_bucket["project_name"] = entry.project.project_name
            project_bucket["case_type"] = entry.project.case_type
            project_bucket["region"] = entry.project.region
            project_bucket["team"] = entry.project.team.name if entry.project.team else "-"
            project_bucket["project_obj"] = entry.project
            project_bucket["billed"] += financial["billed_amount"]
            project_bucket["cost"] += financial["cost_amount"]
            project_bucket["margin"] += financial["margin"]
            project_bucket["hours"] += hours

            if entry.project_id not in project_entry_bounds:
                project_entry_bounds[entry.project_id] = [entry.work_date, entry.work_date]
            else:
                project_entry_bounds[entry.project_id][0] = min(project_entry_bounds[entry.project_id][0], entry.work_date)
                project_entry_bounds[entry.project_id][1] = max(project_entry_bounds[entry.project_id][1], entry.work_date)

    totals = compute_totals_from_financials(row_financials)

    manager_rows = []
    for bucket in manager_summary.values():
        manager_rows.append({
            **bucket,
            "billed": bucket["billed"].quantize(TWOPLACES),
            "cost": bucket["cost"].quantize(TWOPLACES),
            "margin": bucket["margin"].quantize(TWOPLACES),
            "billable_hours": bucket["billable_hours"].quantize(TWOPLACES),
            "total_hours": bucket["total_hours"].quantize(TWOPLACES),
            "utilization": _utilization_percent(bucket["billable_hours"], bucket["total_hours"]),
        })
    manager_rows.sort(key=lambda item: item["label"])

    team_rows = []
    for bucket in team_summary.values():
        team_rows.append({
            **bucket,
            "billed": bucket["billed"].quantize(TWOPLACES),
            "cost": bucket["cost"].quantize(TWOPLACES),
            "margin": bucket["margin"].quantize(TWOPLACES),
            "billable_hours": bucket["billable_hours"].quantize(TWOPLACES),
            "total_hours": bucket["total_hours"].quantize(TWOPLACES),
            "utilization": _utilization_percent(bucket["billable_hours"], bucket["total_hours"]),
        })
    team_rows.sort(key=lambda item: item["label"])

    project_rows = []
    for bucket in project_summary.values():
        project_rows.append({
            **bucket,
            "billed": bucket["billed"].quantize(TWOPLACES),
            "cost": bucket["cost"].quantize(TWOPLACES),
            "margin": bucket["margin"].quantize(TWOPLACES),
            "hours": bucket["hours"].quantize(TWOPLACES),
        })
    project_rows.sort(key=lambda item: (item["case_code"], item["project_name"]))

    manager_chart = {
        "labels": [row["label"] for row in manager_rows],
        "billed": [float(row["billed"]) for row in manager_rows],
        "utilization": [float(row["utilization"]) for row in manager_rows],
    }

    team_chart = {
        "labels": [row["label"] for row in team_rows],
        "billed": [float(row["billed"]) for row in team_rows],
        "utilization": [float(row["utilization"]) for row in team_rows],
    }

    days_in_month = (month_end - month_start).days
    month_last_date = month_end - date.resolution

    timeline_rows = []
    for row in project_rows:
        project_obj = row.get("project_obj")
        project_id = None
        if project_obj is not None:
            project_id = project_obj.id

        inferred_start, inferred_end = (None, None)
        if project_id in project_entry_bounds:
            inferred_start, inferred_end = project_entry_bounds[project_id]

        start_date = getattr(project_obj, "start_date", None) if project_obj is not None else None
        end_date = getattr(project_obj, "end_date", None) if project_obj is not None else None

        if start_date is None:
            start_date = inferred_start
        if end_date is None:
            end_date = inferred_end

        if start_date is None and end_date is None:
            continue
        if start_date is None:
            start_date = end_date
        if end_date is None:
            end_date = start_date

        clamped_start = max(start_date, month_start)
        clamped_end = min(end_date, month_last_date)
        if clamped_end < clamped_start:
            continue

        start_index = (clamped_start - month_start).days
        end_index = (clamped_end - month_start).days
        duration_days = (clamped_end - clamped_start).days + 1

        timeline_rows.append({
            "case_code": row["case_code"],
            "project_name": row["project_name"],
            "team_name": row["team"],
            "start_day": start_index + 1,
            "end_day": end_index + 1,
            "left_pct": (start_index / days_in_month) * 100,
            "width_pct": (duration_days / days_in_month) * 100,
        })

    timeline_rows.sort(key=lambda item: (item["start_day"], item["case_code"]))

    return {
        "totals": totals,
        "manager_rows": manager_rows,
        "team_rows": team_rows,
        "project_rows": project_rows,
        "manager_chart": manager_chart,
        "team_chart": team_chart,
        "timeline_rows": timeline_rows,
    }


def _csv_response(filename: str, headers: list[str], rows: list[list]):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@dashboard_bp.route("", methods=["GET"])
@dashboard_bp.route("/", methods=["GET"])
@login_required
def index():
    month_value, month_start, month_end = _parse_month(request.args.get("month"))
    selected_year = int(month_value.split("-")[0]) if month_value else date.today().year

    manager_id = request.args.get("manager_id", type=int)
    team_id = request.args.get("team_id", type=int)

    entries = _get_filtered_entries(month_start, month_end, manager_id, team_id)
    dashboard_data = _build_dashboard_data(entries, month_start, month_end)

    managers = User.query.filter_by(active=True).order_by(User.name.asc()).all()
    teams = Team.query.filter_by(active=True).order_by(Team.name.asc()).all()

    export_manager_url = url_for("dashboard_bp.export_manager_csv", month=month_value, manager_id=manager_id, team_id=team_id)
    export_team_url = url_for("dashboard_bp.export_team_csv", month=month_value, manager_id=manager_id, team_id=team_id)
    export_projects_url = url_for("dashboard_bp.export_projects_csv", month=month_value, manager_id=manager_id, team_id=team_id)

    return render_template(
        "dashboard/index.html",
        month=month_value,
        selected_year=selected_year,
        manager_id=manager_id,
        team_id=team_id,
        managers=managers,
        teams=teams,
        totals=dashboard_data["totals"],
        manager_rows=dashboard_data["manager_rows"],
        team_rows=dashboard_data["team_rows"],
        project_rows=dashboard_data["project_rows"],
        manager_chart=dashboard_data["manager_chart"],
        team_chart=dashboard_data["team_chart"],
        timeline_rows=dashboard_data["timeline_rows"],
        export_manager_url=export_manager_url,
        export_team_url=export_team_url,
        export_projects_url=export_projects_url,
    )


@dashboard_bp.route("/export/manager.csv", methods=["GET"])
@login_required
def export_manager_csv():
    month_value, month_start, month_end = _parse_month(request.args.get("month"))
    manager_id = request.args.get("manager_id", type=int)
    team_id = request.args.get("team_id", type=int)

    entries = _get_filtered_entries(month_start, month_end, manager_id, team_id)
    data = _build_dashboard_data(entries, month_start, month_end)

    rows = [
        [
            row["label"],
            f"{row['billed']:.2f}",
            f"{row['cost']:.2f}",
            f"{row['margin']:.2f}",
            f"{row['billable_hours']:.2f}",
            f"{row['total_hours']:.2f}",
            f"{row['utilization']:.2f}",
        ]
        for row in data["manager_rows"]
    ]

    return _csv_response(
        f"manager_summary_{month_value}.csv",
        ["Manager", "Billed", "Cost", "Margin", "BillableHours", "TotalHours", "UtilizationPct"],
        rows,
    )


@dashboard_bp.route("/export/team.csv", methods=["GET"])
@login_required
def export_team_csv():
    month_value, month_start, month_end = _parse_month(request.args.get("month"))
    manager_id = request.args.get("manager_id", type=int)
    team_id = request.args.get("team_id", type=int)

    entries = _get_filtered_entries(month_start, month_end, manager_id, team_id)
    data = _build_dashboard_data(entries, month_start, month_end)

    rows = [
        [
            row["label"],
            f"{row['billed']:.2f}",
            f"{row['cost']:.2f}",
            f"{row['margin']:.2f}",
            f"{row['billable_hours']:.2f}",
            f"{row['total_hours']:.2f}",
            f"{row['utilization']:.2f}",
        ]
        for row in data["team_rows"]
    ]

    return _csv_response(
        f"team_summary_{month_value}.csv",
        ["Team", "Billed", "Cost", "Margin", "BillableHours", "TotalHours", "UtilizationPct"],
        rows,
    )


@dashboard_bp.route("/export/projects.csv", methods=["GET"])
@login_required
def export_projects_csv():
    month_value, month_start, month_end = _parse_month(request.args.get("month"))
    manager_id = request.args.get("manager_id", type=int)
    team_id = request.args.get("team_id", type=int)

    entries = _get_filtered_entries(month_start, month_end, manager_id, team_id)
    data = _build_dashboard_data(entries, month_start, month_end)

    rows = [
        [
            row["case_code"],
            row["project_name"],
            row["case_type"],
            row["region"],
            row["team"],
            f"{row['billed']:.2f}",
            f"{row['cost']:.2f}",
            f"{row['margin']:.2f}",
            f"{row['hours']:.2f}",
        ]
        for row in data["project_rows"]
    ]

    return _csv_response(
        f"projects_summary_{month_value}.csv",
        ["CaseCode", "ProjectName", "CaseType", "Region", "Team", "Billed", "Cost", "Margin", "Hours"],
        rows,
    )


@dashboard_bp.route("/martha", methods=["GET"])
@login_required
def martha():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    if year < 1900 or year > 3000:
        year = today.year

    manager_id = request.args.get("manager_id", type=int)
    team_id = request.args.get("team_id", type=int)

    billing_rates_daily = BillingRate.query.filter_by(cadence=BillingCadence.DAILY.value).all()
    cost_rate_by_level = {
        str(getattr(cost_rate.level, "value", cost_rate.level)): cost_rate
        for cost_rate in CostRate.query.all()
    }

    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    monthly_rows = []

    for month_number in range(1, 13):
        month_start = date(year, month_number, 1)
        if month_number == 12:
            month_end = date(year + 1, 1, 1)
        else:
            month_end = date(year, month_number + 1, 1)

        entries = _get_filtered_entries(month_start, month_end, manager_id, team_id)

        gross_cost = Decimal("0.00")
        recovery_total = Decimal("0.00")
        client_recovery = Decimal("0.00")
        other_practice_recovery = Decimal("0.00")
        fte_days = Decimal("0.00")
        distinct_days = set()

        for entry in entries:
            distinct_days.add(entry.work_date)
            fin = compute_entry_financials(
                entry,
                billing_rate_rows=billing_rates_daily,
                cost_rate_by_level=cost_rate_by_level,
            )
            cost_amount = fin["cost_amount"]
            billed_amount = fin["billed_amount"]

            gross_cost += cost_amount

            hours_fraction = _decimal_hours(entry.hours) / Decimal("8")
            charged_fte = Decimal(str(entry.charged_fte or 0))
            fte_days += charged_fte * hours_fraction

            activity = getattr(entry.activity_type, "value", entry.activity_type)
            is_billable = activity == ActivityType.PROJECT.value and entry.project_id is not None
            if is_billable:
                recovery_total += billed_amount
                case_type = entry.project.case_type if entry.project is not None else None
                if case_type == "Client billed":
                    client_recovery += billed_amount
                else:
                    other_practice_recovery += billed_amount

        working_days = len(distinct_days)
        ftes = (fte_days / Decimal(str(working_days))) if working_days else Decimal("0.00")

        net_cost = gross_cost - recovery_total
        total_recovery_pct = (recovery_total / gross_cost * Decimal("100")) if gross_cost > 0 else Decimal("0.00")
        pct_recovery_client = (client_recovery / recovery_total * Decimal("100")) if recovery_total > 0 else Decimal("0.00")
        pct_recovery_other = (other_practice_recovery / recovery_total * Decimal("100")) if recovery_total > 0 else Decimal("0.00")

        monthly_rows.append({
            "month": month_names[month_number - 1],
            "month_number": month_number,
            "ftes": float(ftes.quantize(TWOPLACES)),
            "gross_cost": float(gross_cost.quantize(TWOPLACES)),
            "recovery_total": float(recovery_total.quantize(TWOPLACES)),
            "net_cost": float(net_cost.quantize(TWOPLACES)),
            "total_recovery_pct": float(total_recovery_pct.quantize(TWOPLACES)),
            "pct_recovery_client": float(pct_recovery_client.quantize(TWOPLACES)),
            "pct_recovery_other": float(pct_recovery_other.quantize(TWOPLACES)),
        })

    ytd_last_month = today.month if year == today.year else 12
    ytd_rows = [row for row in monthly_rows if row["month_number"] <= ytd_last_month]

    ytd_gross_cost = sum((row["gross_cost"] for row in ytd_rows), Decimal("0.00"))
    ytd_recovery = sum((row["recovery_total"] for row in ytd_rows), Decimal("0.00"))
    ytd_net = sum((row["net_cost"] for row in ytd_rows), Decimal("0.00"))
    ytd_total_recovery_pct = (ytd_recovery / ytd_gross_cost * Decimal("100")) if ytd_gross_cost > 0 else Decimal("0.00")

    total_budget_year = Decimal("1200000")
    budget_allocated_ytd = Decimal("200000")
    budget_utilized_pct = (ytd_net / total_budget_year * Decimal("100")) if total_budget_year > 0 else Decimal("0.00")
    unspent_budget_ytd = total_budget_year - ytd_net

    ytd_budget = {
        "ytd_gross_cost": float(ytd_gross_cost.quantize(TWOPLACES)),
        "ytd_recovery": float(ytd_recovery.quantize(TWOPLACES)),
        "ytd_net": float(ytd_net.quantize(TWOPLACES)),
        "ytd_total_recovery_pct": float(ytd_total_recovery_pct.quantize(TWOPLACES)),
        "total_budget_year": float(total_budget_year.quantize(TWOPLACES)),
        "budget_allocated_ytd": float(budget_allocated_ytd.quantize(TWOPLACES)),
        "budget_utilized_pct": float(budget_utilized_pct.quantize(TWOPLACES)),
        "unspent_budget_ytd": float(unspent_budget_ytd.quantize(TWOPLACES)),
    }

    managers = User.query.filter_by(active=True).order_by(User.name.asc()).all()
    teams = Team.query.filter_by(active=True).order_by(Team.name.asc()).all()

    month_for_back = request.args.get("month")
    if not month_for_back:
        month_for_back = f"{year}-{(today.month if year == today.year else 12):02d}"

    return render_template(
        "dashboard/martha.html",
        year=year,
        month_for_back=month_for_back,
        manager_id=manager_id,
        team_id=team_id,
        managers=managers,
        teams=teams,
        monthly_rows=monthly_rows,
        ytd_budget=ytd_budget,
    )


@dashboard_bp.route("/billing-summary", methods=["GET"])
@login_required
def billing_summary():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    if year < 1900 or year > 3000:
        year = today.year

    manager_id = request.args.get("manager_id", type=int)
    team_id = request.args.get("team_id", type=int)

    billing_rates_daily = BillingRate.query.filter_by(cadence=BillingCadence.DAILY.value).all()
    cost_rate_by_level = {
        str(getattr(cost_rate.level, "value", cost_rate.level)): cost_rate
        for cost_rate in CostRate.query.all()
    }

    ip_cd_investment_case_types = {"IP (Z5LB/J2RC)", "Other CD/IP Codes", "Investment"}
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    monthly_rows = []
    for month_number in range(1, 13):
        month_start = date(year, month_number, 1)
        if month_number == 12:
            month_end = date(year + 1, 1, 1)
        else:
            month_end = date(year, month_number + 1, 1)

        entries = _get_filtered_entries(month_start, month_end, manager_id, team_id)

        recovery_total = Decimal("0.00")
        client_billed_recovery = Decimal("0.00")
        ip_cd_investment_recovery = Decimal("0.00")
        other_recovery = Decimal("0.00")
        total_billable_hours = Decimal("0.00")
        total_hours = Decimal("0.00")

        for entry in entries:
            entry_hours = _decimal_hours(entry.hours)
            total_hours += entry_hours

            activity = getattr(entry.activity_type, "value", entry.activity_type)
            is_project_billable = activity == ActivityType.PROJECT.value and entry.project_id is not None
            if not is_project_billable:
                continue

            total_billable_hours += entry_hours

            fin = compute_entry_financials(
                entry,
                billing_rate_rows=billing_rates_daily,
                cost_rate_by_level=cost_rate_by_level,
            )
            billed_amount = fin["billed_amount"]
            recovery_total += billed_amount

            case_type = entry.project.case_type if entry.project is not None else None
            if case_type == "Client billed":
                client_billed_recovery += billed_amount
            elif case_type in ip_cd_investment_case_types:
                ip_cd_investment_recovery += billed_amount
            else:
                other_recovery += billed_amount

        utilization_pct = (total_billable_hours / total_hours * Decimal("100")) if total_hours > 0 else Decimal("0.00")

        monthly_rows.append({
            "month": month_names[month_number - 1],
            "recovery_total": float(recovery_total.quantize(TWOPLACES)),
            "client_billed_recovery": float(client_billed_recovery.quantize(TWOPLACES)),
            "ip_cd_investment_recovery": float(ip_cd_investment_recovery.quantize(TWOPLACES)),
            "other_recovery": float(other_recovery.quantize(TWOPLACES)),
            "total_billable_hours": float(total_billable_hours.quantize(TWOPLACES)),
            "total_hours": float(total_hours.quantize(TWOPLACES)),
            "utilization_pct": float(utilization_pct.quantize(TWOPLACES)),
        })

    managers = User.query.filter_by(active=True).order_by(User.name.asc()).all()
    teams = Team.query.filter_by(active=True).order_by(Team.name.asc()).all()

    month_for_back = request.args.get("month")
    if not month_for_back:
        month_for_back = f"{year}-{(today.month if year == today.year else 12):02d}"

    return render_template(
        "dashboard/billing_summary.html",
        year=year,
        month_for_back=month_for_back,
        manager_id=manager_id,
        team_id=team_id,
        managers=managers,
        teams=teams,
        monthly_rows=monthly_rows,
    )
