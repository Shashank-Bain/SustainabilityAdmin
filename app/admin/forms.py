from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DecimalField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Optional

from app.models import BillingCadence, TeamMemberLevel, UserRole


class TeamForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    classification_1 = StringField("Classification 1")
    classification_2 = StringField("Classification 2")
    active = BooleanField("Active", default=True)
    submit = SubmitField("Save")


class TeamMemberForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    employee_id = StringField("Employee ID", validators=[DataRequired()])
    gender = StringField("Gender")
    level = SelectField(
        "Level",
        validators=[DataRequired()],
        choices=[(level.value, level.value) for level in TeamMemberLevel],
    )
    active = BooleanField("Active", default=True)
    submit = SubmitField("Save")


class ProjectForm(FlaskForm):
    case_code = StringField("Case Code", validators=[DataRequired()])
    project_name = StringField("Project Name", validators=[DataRequired()])
    description = TextAreaField("Description")
    case_type = StringField("Case Type", validators=[DataRequired()])
    stakeholder = StringField("Stakeholder")
    region = StringField("Region", validators=[DataRequired()])
    nps_contact = StringField("NPS Contact")
    sku = StringField("SKU")
    start_date = DateField("Start Date", format="%Y-%m-%d", validators=[], render_kw={"type": "date"})
    end_date = DateField("End Date", format="%Y-%m-%d", validators=[], render_kw={"type": "date"})
    status = StringField("Status", validators=[DataRequired()], default="Active")
    team_id = SelectField("Team", coerce=int, choices=[(0, "-- No Team --")], default=0)
    submit = SubmitField("Save")


class UserForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[Optional()])
    role = SelectField(
        "Role",
        validators=[DataRequired()],
        choices=[(role.value, role.value) for role in UserRole],
    )
    active = BooleanField("Active", default=True)
    submit = SubmitField("Save")


class CostRateForm(FlaskForm):
    level = SelectField(
        "Level",
        validators=[DataRequired()],
        choices=[(level.value, level.value) for level in TeamMemberLevel],
    )
    cost_per_day = DecimalField("Cost Per Day", validators=[DataRequired()], places=2)
    submit = SubmitField("Save")


class BillingRateForm(FlaskForm):
    case_type = StringField("Case Type", validators=[DataRequired()])
    region = StringField("Region", validators=[DataRequired()])
    cadence = SelectField(
        "Cadence",
        validators=[DataRequired()],
        choices=[(cadence.value, cadence.value) for cadence in BillingCadence],
    )
    fte = DecimalField("FTE", validators=[DataRequired()], places=1)
    amount = DecimalField("Amount", validators=[DataRequired()], places=2)
    submit = SubmitField("Save")

