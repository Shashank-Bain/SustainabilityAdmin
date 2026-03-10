from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import ActivityType, BillingCadence, BillingRate, CostRate, Project, StaffingEntry, Team, TeamMember, User
from app.services.billing import compute_entry_financials, compute_totals_from_financials


daily_bp = Blueprint("daily_bp", __name__, url_prefix="/daily")


def _parse_date(value: str | None) -> date:
    if value:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def _to_decimal(value, default: str) -> Decimal:
    if value is None or str(value).strip() == "":
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _load_master_data():
    members = TeamMember.query.filter_by(active=True).order_by(TeamMember.name.asc()).all()
    teams = Team.query.filter_by(active=True).order_by(Team.name.asc()).all()
    projects = Project.query.order_by(Project.case_code.asc()).all()
    users = User.query.filter_by(active=True).order_by(User.name.asc()).all()
    billing_rates = BillingRate.query.filter_by(cadence=BillingCadence.DAILY.value).all()
    cost_rates = CostRate.query.all()
    return members, teams, projects, users, billing_rates, cost_rates


def _serialize_entry(entry: StaffingEntry):
    return {
        "key": f"id_{entry.id}",
        "id": entry.id,
        "team_member_id": entry.team_member_id,
        "team_id": entry.team_id,
        "activity_type": getattr(entry.activity_type, "value", entry.activity_type),
        "project_id": entry.project_id,
        "hours": float(entry.hours or 8),
        "charged_fte": float(entry.charged_fte or 1),
        "billing_manager_user_id": entry.billing_manager_user_id,
        "notes": entry.notes or "",
    }


@daily_bp.route("", methods=["GET"])
@daily_bp.route("/", methods=["GET"])
@login_required
def index():
    selected_date = _parse_date(request.args.get("date"))

    entries = StaffingEntry.query.options(
        joinedload(StaffingEntry.project),
        joinedload(StaffingEntry.team_member),
    ).filter_by(
        work_date=selected_date,
        manager_user_id=current_user.id,
    ).order_by(StaffingEntry.id.asc()).all()

    if not entries:
        previous_date = db.session.query(db.func.max(StaffingEntry.work_date)).filter(
            StaffingEntry.manager_user_id == current_user.id,
            StaffingEntry.work_date < selected_date,
        ).scalar()

        if previous_date is not None:
            previous_entries = StaffingEntry.query.filter_by(
                work_date=previous_date,
                manager_user_id=current_user.id,
            ).order_by(StaffingEntry.id.asc()).all()

            for prev in previous_entries:
                cloned = StaffingEntry(
                    work_date=selected_date,
                    manager_user_id=current_user.id,
                    team_member_id=prev.team_member_id,
                    team_id=prev.team_id,
                    project_id=prev.project_id,
                    activity_type=getattr(prev.activity_type, "value", prev.activity_type),
                    hours=prev.hours,
                    charged_fte=prev.charged_fte,
                    billing_manager_user_id=prev.billing_manager_user_id,
                    notes=prev.notes,
                )
                db.session.add(cloned)

            db.session.commit()
            flash(f"Prefilled from {previous_date.isoformat()}", "info")

            entries = StaffingEntry.query.options(
                joinedload(StaffingEntry.project),
                joinedload(StaffingEntry.team_member),
            ).filter_by(
                work_date=selected_date,
                manager_user_id=current_user.id,
            ).order_by(StaffingEntry.id.asc()).all()

    members, teams, projects, users, billing_rates, cost_rates = _load_master_data()

    cost_rate_by_level = {
        str(getattr(cost_rate.level, "value", cost_rate.level)): cost_rate
        for cost_rate in cost_rates
    }

    row_financials = {}
    for entry in entries:
        result = compute_entry_financials(
            entry,
            billing_rate_rows=billing_rates,
            cost_rate_by_level=cost_rate_by_level,
        )
        row_financials[entry.id] = result

    totals = compute_totals_from_financials(row_financials)
    rows = [_serialize_entry(entry) for entry in entries]

    return render_template(
        "daily/index.html",
        selected_date=selected_date,
        rows=rows,
        members=members,
        teams=teams,
        projects=projects,
        users=users,
        activity_types=[item.value for item in ActivityType],
        row_financials=row_financials,
        totals=totals,
        billing_rates=billing_rates,
        cost_rates=cost_rates,
    )


@daily_bp.route("/save", methods=["POST"])
@login_required
def save():
    selected_date = _parse_date(request.form.get("work_date"))
    existing_rows = StaffingEntry.query.filter_by(
        work_date=selected_date,
        manager_user_id=current_user.id,
    ).all()
    existing_by_id = {row.id: row for row in existing_rows}

    row_keys = request.form.getlist("row_key")
    for row_key in row_keys:
        row_id_raw = request.form.get(f"{row_key}_id")
        is_delete = request.form.get(f"{row_key}_delete") == "1"

        entry = None
        if row_id_raw:
            row_id = int(row_id_raw)
            entry = existing_by_id.get(row_id)
            if entry is None:
                continue
            if is_delete:
                db.session.delete(entry)
                continue
        else:
            if is_delete:
                continue
            team_id_val = request.form.get(f"{row_key}_team_id")
            if not team_id_val:
                continue
            entry = StaffingEntry(
                work_date=selected_date,
                manager_user_id=current_user.id,
                team_id=int(team_id_val),
            )
            db.session.add(entry)

        team_id_raw = request.form.get(f"{row_key}_team_id")
        if not team_id_raw:
            flash("Team is required for each row.", "danger")
            continue

        activity_type = request.form.get(f"{row_key}_activity_type", ActivityType.PROJECT.value)
        project_id_raw = request.form.get(f"{row_key}_project_id")

        entry.team_member_id = int(request.form.get(f"{row_key}_team_member_id")) if request.form.get(f"{row_key}_team_member_id") else None
        entry.team_id = int(team_id_raw)
        entry.activity_type = activity_type
        entry.project_id = int(project_id_raw) if (activity_type == ActivityType.PROJECT.value and project_id_raw) else None
        entry.hours = _to_decimal(request.form.get(f"{row_key}_hours"), "8.0")
        entry.charged_fte = _to_decimal(request.form.get(f"{row_key}_charged_fte"), "1.0")
        entry.billing_manager_user_id = int(request.form.get(f"{row_key}_billing_manager_user_id")) if request.form.get(f"{row_key}_billing_manager_user_id") else None
        entry.notes = request.form.get(f"{row_key}_notes") or None

    db.session.commit()
    flash("Daily staffing saved.", "success")
    return redirect(url_for("daily_bp.index", date=selected_date.isoformat()))


@daily_bp.route("/clear", methods=["POST"])
@login_required
def clear_day():
    selected_date = _parse_date(request.form.get("work_date"))
    StaffingEntry.query.filter_by(
        work_date=selected_date,
        manager_user_id=current_user.id,
    ).delete(synchronize_session=False)
    db.session.commit()
    flash("Daily entries cleared.", "warning")
    return redirect(url_for("daily_bp.index", date=selected_date.isoformat()))


@daily_bp.route("/add_row", methods=["POST"])
@login_required
def add_row():
    selected_date = _parse_date(request.form.get("work_date"))
    first_team = Team.query.filter_by(active=True).order_by(Team.name.asc()).first()
    if first_team is None:
        flash("At least one active team is required before adding staffing rows.", "danger")
        return redirect(url_for("daily_bp.index", date=selected_date.isoformat()))

    entry = StaffingEntry(
        work_date=selected_date,
        manager_user_id=current_user.id,
        team_id=first_team.id,
        activity_type=ActivityType.PROJECT.value,
        hours=Decimal("8.0"),
        charged_fte=Decimal("1.0"),
        billing_manager_user_id=current_user.id,
    )
    db.session.add(entry)
    db.session.commit()
    return redirect(url_for("daily_bp.index", date=selected_date.isoformat()))
