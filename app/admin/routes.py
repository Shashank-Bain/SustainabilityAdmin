from sqlalchemy.exc import IntegrityError

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import BillingRate, CostRate, Project, Team, TeamMember, User

from .forms import BillingRateForm, CostRateForm, ProjectForm, TeamForm, TeamMemberForm, UserForm


admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")


def _admin_only() -> None:
    if not current_user.is_authenticated or getattr(current_user, "role", None) != "admin":
        abort(403)


@admin_bp.route("")
@admin_bp.route("/")
@login_required
def index():
    return render_template("admin/index.html")


@admin_bp.route("/teams")
@login_required
def teams_list():
    teams = Team.query.order_by(Team.name.asc()).all()
    return render_template("admin/teams_list.html", teams=teams)


@admin_bp.route("/teams/new", methods=["GET", "POST"])
@login_required
def teams_new():
    form = TeamForm()
    if form.validate_on_submit():
        team = Team(
            name=form.name.data.strip(),
            classification_1=form.classification_1.data.strip() if form.classification_1.data else None,
            classification_2=form.classification_2.data.strip() if form.classification_2.data else None,
            active=form.active.data,
        )
        db.session.add(team)
        try:
            db.session.commit()
            flash("Team created successfully.", "success")
            return redirect(url_for("admin_bp.teams_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A team with this name already exists.", "danger")

    return render_template("admin/team_form.html", form=form, title="New Team", cancel_url=url_for("admin_bp.teams_list"))


@admin_bp.route("/teams/<int:team_id>/edit", methods=["GET", "POST"])
@login_required
def teams_edit(team_id: int):
    team = Team.query.get_or_404(team_id)
    form = TeamForm(obj=team)

    if form.validate_on_submit():
        team.name = form.name.data.strip()
        team.classification_1 = form.classification_1.data.strip() if form.classification_1.data else None
        team.classification_2 = form.classification_2.data.strip() if form.classification_2.data else None
        team.active = form.active.data
        try:
            db.session.commit()
            flash("Team updated successfully.", "success")
            return redirect(url_for("admin_bp.teams_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A team with this name already exists.", "danger")

    return render_template(
        "admin/team_form.html",
        form=form,
        title="Edit Team",
        cancel_url=url_for("admin_bp.teams_list"),
    )


@admin_bp.route("/teams/<int:team_id>/delete/confirm")
@login_required
def teams_delete_confirm(team_id: int):
    team = Team.query.get_or_404(team_id)
    return render_template(
        "admin/confirm_delete.html",
        title="Delete Team",
        message=f"Are you sure you want to delete team '{team.name}'?",
        confirm_url=url_for("admin_bp.teams_delete", team_id=team.id),
        cancel_url=url_for("admin_bp.teams_list"),
    )


@admin_bp.route("/teams/<int:team_id>/delete", methods=["POST"])
@login_required
def teams_delete(team_id: int):
    team = Team.query.get_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    flash("Team deleted successfully.", "success")
    return redirect(url_for("admin_bp.teams_list"))


@admin_bp.route("/members")
@login_required
def members_list():
    members = TeamMember.query.order_by(TeamMember.name.asc()).all()
    return render_template("admin/members_list.html", members=members)


@admin_bp.route("/members/new", methods=["GET", "POST"])
@login_required
def members_new():
    form = TeamMemberForm()
    if form.validate_on_submit():
        member = TeamMember(
            name=form.name.data.strip(),
            employee_id=form.employee_id.data.strip(),
            gender=form.gender.data.strip() if form.gender.data else None,
            level=form.level.data,
            active=form.active.data,
        )
        db.session.add(member)
        try:
            db.session.commit()
            flash("Team member created successfully.", "success")
            return redirect(url_for("admin_bp.members_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A team member with this employee ID already exists.", "danger")

    return render_template(
        "admin/member_form.html",
        form=form,
        title="New Team Member",
        cancel_url=url_for("admin_bp.members_list"),
    )


@admin_bp.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
@login_required
def members_edit(member_id: int):
    member = TeamMember.query.get_or_404(member_id)
    form = TeamMemberForm(obj=member)

    if form.validate_on_submit():
        member.name = form.name.data.strip()
        member.employee_id = form.employee_id.data.strip()
        member.gender = form.gender.data.strip() if form.gender.data else None
        member.level = form.level.data
        member.active = form.active.data
        try:
            db.session.commit()
            flash("Team member updated successfully.", "success")
            return redirect(url_for("admin_bp.members_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A team member with this employee ID already exists.", "danger")

    return render_template(
        "admin/member_form.html",
        form=form,
        title="Edit Team Member",
        cancel_url=url_for("admin_bp.members_list"),
    )


@admin_bp.route("/members/<int:member_id>/delete/confirm")
@login_required
def members_delete_confirm(member_id: int):
    member = TeamMember.query.get_or_404(member_id)
    return render_template(
        "admin/confirm_delete.html",
        title="Delete Team Member",
        message=f"Are you sure you want to delete team member '{member.name}'?",
        confirm_url=url_for("admin_bp.members_delete", member_id=member.id),
        cancel_url=url_for("admin_bp.members_list"),
    )


@admin_bp.route("/members/<int:member_id>/delete", methods=["POST"])
@login_required
def members_delete(member_id: int):
    member = TeamMember.query.get_or_404(member_id)
    db.session.delete(member)
    db.session.commit()
    flash("Team member deleted successfully.", "success")
    return redirect(url_for("admin_bp.members_list"))


@admin_bp.route("/projects")
@login_required
def projects_list():
    projects = Project.query.order_by(Project.project_name.asc()).all()
    return render_template("admin/projects_list.html", projects=projects)


@admin_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def projects_new():
    form = ProjectForm()
    teams = Team.query.order_by(Team.name.asc()).all()
    form.team_id.choices = [(0, "-- No Team --")] + [
        (team.id, team.name) for team in teams
    ]

    if form.validate_on_submit():
        project = Project(
            case_code=form.case_code.data.strip(),
            project_name=form.project_name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            case_type=form.case_type.data.strip(),
            stakeholder=form.stakeholder.data.strip() if form.stakeholder.data else None,
            region=form.region.data.strip(),
            nps_contact=form.nps_contact.data.strip() if form.nps_contact.data else None,
            sku=form.sku.data.strip() if form.sku.data else None,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status=form.status.data.strip(),
            team_id=form.team_id.data if form.team_id.data != 0 else None,
        )
        db.session.add(project)
        try:
            db.session.commit()
            flash("Project created successfully.", "success")
            return redirect(url_for("admin_bp.projects_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A project with this case code already exists.", "danger")

    return render_template(
        "admin/project_form.html",
        form=form,
        title="New Project",
        cancel_url=url_for("admin_bp.projects_list"),
    )


@admin_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def projects_edit(project_id: int):
    project = Project.query.get_or_404(project_id)
    form = ProjectForm(obj=project)
    teams = Team.query.order_by(Team.name.asc()).all()
    form.team_id.choices = [(0, "-- No Team --")] + [
        (team.id, team.name) for team in teams
    ]

    if project.team_id is None:
        form.team_id.data = 0

    if form.validate_on_submit():
        project.case_code = form.case_code.data.strip()
        project.project_name = form.project_name.data.strip()
        project.description = form.description.data.strip() if form.description.data else None
        project.case_type = form.case_type.data.strip()
        project.stakeholder = form.stakeholder.data.strip() if form.stakeholder.data else None
        project.region = form.region.data.strip()
        project.nps_contact = form.nps_contact.data.strip() if form.nps_contact.data else None
        project.sku = form.sku.data.strip() if form.sku.data else None
        project.start_date = form.start_date.data
        project.end_date = form.end_date.data
        project.status = form.status.data.strip()
        project.team_id = form.team_id.data if form.team_id.data != 0 else None
        try:
            db.session.commit()
            flash("Project updated successfully.", "success")
            return redirect(url_for("admin_bp.projects_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A project with this case code already exists.", "danger")

    return render_template(
        "admin/project_form.html",
        form=form,
        title="Edit Project",
        cancel_url=url_for("admin_bp.projects_list"),
    )


@admin_bp.route("/projects/<int:project_id>/delete/confirm")
@login_required
def projects_delete_confirm(project_id: int):
    project = Project.query.get_or_404(project_id)
    return render_template(
        "admin/confirm_delete.html",
        title="Delete Project",
        message=f"Are you sure you want to delete project '{project.project_name}'?",
        confirm_url=url_for("admin_bp.projects_delete", project_id=project.id),
        cancel_url=url_for("admin_bp.projects_list"),
    )


@admin_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def projects_delete(project_id: int):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted successfully.", "success")
    return redirect(url_for("admin_bp.projects_list"))


@admin_bp.route("/users")
@login_required
def users_list():
    _admin_only()
    users = User.query.order_by(User.name.asc()).all()
    return render_template("admin/users_list.html", users=users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
def users_new():
    _admin_only()
    form = UserForm()
    if form.validate_on_submit():
        password = (form.password.data or "").strip()
        if not password:
            flash("Password is required when creating a user.", "danger")
            return render_template(
                "admin/user_form.html",
                form=form,
                title="New User",
                cancel_url=url_for("admin_bp.users_list"),
            )

        user = User(
            name=form.name.data.strip(),
            email=form.email.data.strip().lower(),
            role=form.role.data,
            active=form.active.data,
        )
        user.set_password(password)

        db.session.add(user)
        try:
            db.session.commit()
            flash("User created successfully.", "success")
            return redirect(url_for("admin_bp.users_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A user with this email already exists.", "danger")

    return render_template(
        "admin/user_form.html",
        form=form,
        title="New User",
        cancel_url=url_for("admin_bp.users_list"),
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def users_edit(user_id: int):
    _admin_only()
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)

    if form.validate_on_submit():
        user.name = form.name.data.strip()
        user.email = form.email.data.strip().lower()
        user.role = form.role.data
        user.active = form.active.data

        password = (form.password.data or "").strip()
        if password:
            user.set_password(password)

        try:
            db.session.commit()
            flash("User updated successfully.", "success")
            return redirect(url_for("admin_bp.users_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A user with this email already exists.", "danger")

    return render_template(
        "admin/user_form.html",
        form=form,
        title="Edit User",
        cancel_url=url_for("admin_bp.users_list"),
    )


@admin_bp.route("/users/<int:user_id>/delete/confirm")
@login_required
def users_delete_confirm(user_id: int):
    _admin_only()
    user = User.query.get_or_404(user_id)
    return render_template(
        "admin/confirm_delete.html",
        title="Delete User",
        message=f"Are you sure you want to delete user '{user.email}'?",
        confirm_url=url_for("admin_bp.users_delete", user_id=user.id),
        cancel_url=url_for("admin_bp.users_list"),
    )


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def users_delete(user_id: int):
    _admin_only()
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully.", "success")
    return redirect(url_for("admin_bp.users_list"))


@admin_bp.route("/costrates")
@login_required
def costrates_list():
    cost_rates = CostRate.query.order_by(CostRate.level.asc()).all()
    return render_template("admin/costrates_list.html", cost_rates=cost_rates)


@admin_bp.route("/costrates/new", methods=["GET", "POST"])
@login_required
def costrates_new():
    form = CostRateForm()
    if form.validate_on_submit():
        cost_rate = CostRate(
            level=form.level.data,
            cost_per_day=form.cost_per_day.data,
        )
        db.session.add(cost_rate)
        try:
            db.session.commit()
            flash("Cost rate created successfully.", "success")
            return redirect(url_for("admin_bp.costrates_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A cost rate for this level already exists.", "danger")

    return render_template(
        "admin/costrate_form.html",
        form=form,
        title="New Cost Rate",
        cancel_url=url_for("admin_bp.costrates_list"),
    )


@admin_bp.route("/costrates/<int:cost_rate_id>/edit", methods=["GET", "POST"])
@login_required
def costrates_edit(cost_rate_id: int):
    cost_rate = CostRate.query.get_or_404(cost_rate_id)
    form = CostRateForm(obj=cost_rate)

    if form.validate_on_submit():
        cost_rate.level = form.level.data
        cost_rate.cost_per_day = form.cost_per_day.data
        try:
            db.session.commit()
            flash("Cost rate updated successfully.", "success")
            return redirect(url_for("admin_bp.costrates_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A cost rate for this level already exists.", "danger")

    return render_template(
        "admin/costrate_form.html",
        form=form,
        title="Edit Cost Rate",
        cancel_url=url_for("admin_bp.costrates_list"),
    )


@admin_bp.route("/costrates/<int:cost_rate_id>/delete/confirm")
@login_required
def costrates_delete_confirm(cost_rate_id: int):
    cost_rate = CostRate.query.get_or_404(cost_rate_id)
    return render_template(
        "admin/confirm_delete.html",
        title="Delete Cost Rate",
        message=f"Are you sure you want to delete cost rate for level '{cost_rate.level}'?",
        confirm_url=url_for("admin_bp.costrates_delete", cost_rate_id=cost_rate.id),
        cancel_url=url_for("admin_bp.costrates_list"),
    )


@admin_bp.route("/costrates/<int:cost_rate_id>/delete", methods=["POST"])
@login_required
def costrates_delete(cost_rate_id: int):
    cost_rate = CostRate.query.get_or_404(cost_rate_id)
    db.session.delete(cost_rate)
    db.session.commit()
    flash("Cost rate deleted successfully.", "success")
    return redirect(url_for("admin_bp.costrates_list"))


@admin_bp.route("/billingrates")
@login_required
def billingrates_list():
    billing_rates = BillingRate.query.order_by(BillingRate.case_type.asc(), BillingRate.region.asc()).all()
    return render_template("admin/billingrates_list.html", billing_rates=billing_rates)


@admin_bp.route("/billingrates/new", methods=["GET", "POST"])
@login_required
def billingrates_new():
    form = BillingRateForm()
    if form.validate_on_submit():
        billing_rate = BillingRate(
            case_type=form.case_type.data.strip(),
            region=form.region.data.strip(),
            cadence=form.cadence.data,
            fte=form.fte.data,
            amount=form.amount.data,
        )
        db.session.add(billing_rate)
        try:
            db.session.commit()
            flash("Billing rate created successfully.", "success")
            return redirect(url_for("admin_bp.billingrates_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A billing rate with this case type, region, cadence, and FTE already exists.", "danger")

    return render_template(
        "admin/billingrate_form.html",
        form=form,
        title="New Billing Rate",
        cancel_url=url_for("admin_bp.billingrates_list"),
    )


@admin_bp.route("/billingrates/<int:billing_rate_id>/edit", methods=["GET", "POST"])
@login_required
def billingrates_edit(billing_rate_id: int):
    billing_rate = BillingRate.query.get_or_404(billing_rate_id)
    form = BillingRateForm(obj=billing_rate)

    if form.validate_on_submit():
        billing_rate.case_type = form.case_type.data.strip()
        billing_rate.region = form.region.data.strip()
        billing_rate.cadence = form.cadence.data
        billing_rate.fte = form.fte.data
        billing_rate.amount = form.amount.data
        try:
            db.session.commit()
            flash("Billing rate updated successfully.", "success")
            return redirect(url_for("admin_bp.billingrates_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A billing rate with this case type, region, cadence, and FTE already exists.", "danger")

    return render_template(
        "admin/billingrate_form.html",
        form=form,
        title="Edit Billing Rate",
        cancel_url=url_for("admin_bp.billingrates_list"),
    )


@admin_bp.route("/billingrates/<int:billing_rate_id>/delete/confirm")
@login_required
def billingrates_delete_confirm(billing_rate_id: int):
    billing_rate = BillingRate.query.get_or_404(billing_rate_id)
    return render_template(
        "admin/confirm_delete.html",
        title="Delete Billing Rate",
        message=(
            "Are you sure you want to delete billing rate "
            f"'{billing_rate.case_type} / {billing_rate.region} / {billing_rate.cadence} / {billing_rate.fte}'?"
        ),
        confirm_url=url_for("admin_bp.billingrates_delete", billing_rate_id=billing_rate.id),
        cancel_url=url_for("admin_bp.billingrates_list"),
    )


@admin_bp.route("/billingrates/<int:billing_rate_id>/delete", methods=["POST"])
@login_required
def billingrates_delete(billing_rate_id: int):
    billing_rate = BillingRate.query.get_or_404(billing_rate_id)
    db.session.delete(billing_rate)
    db.session.commit()
    flash("Billing rate deleted successfully.", "success")
    return redirect(url_for("admin_bp.billingrates_list"))

