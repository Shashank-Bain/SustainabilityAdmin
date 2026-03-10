from enum import Enum

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"


class TeamMemberLevel(str, Enum):
    ANALYST1 = "Analyst1"
    ANALYST2 = "Analyst2"
    ASSOCIATE1 = "Associate1"
    ASSOCIATE2 = "Associate2"
    ASSOCIATE3 = "Associate3"
    PROJECT_LEADER1 = "ProjectLeader1"
    PROJECT_LEADER2 = "ProjectLeader2"
    PROJECT_LEADER3 = "ProjectLeader3"
    MANAGER1 = "Manager1"
    MANAGER2 = "Manager2"
    MANAGER3 = "Manager3"
    SENIOR_MANAGER1 = "SeniorManager1"
    SENIOR_MANAGER2 = "SeniorManager2"
    SENIOR_MANAGER3 = "SeniorManager3"
    DIRECTOR = "Director"
    SENIOR_DIRECTOR = "SeniorDirector"
    VP = "VP"


class BillingCadence(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class ActivityType(str, Enum):
    PROJECT = "PROJECT"
    SICK_LEAVE = "SICK_LEAVE"
    VACATION = "VACATION"
    HOLIDAY = "HOLIDAY"
    BENCH = "BENCH"
    TRAINING = "TRAINING"
    OTHER = "OTHER"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum(UserRole, native_enum=False, values_callable=lambda enum_cls: [item.value for item in enum_cls]),
        nullable=False,
        default=UserRole.MANAGER.value,
    )
    active = db.Column(db.Boolean, nullable=False, default=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"


class TeamMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    employee_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    gender = db.Column(db.String(50), nullable=True)
    level = db.Column(
        db.Enum(
            TeamMemberLevel,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    active = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<TeamMember id={self.id} employee_id={self.employee_id} level={self.level}>"


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    classification_1 = db.Column(db.String(255), nullable=True)
    classification_2 = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    projects = db.relationship("Project", back_populates="team", lazy=True)

    def __repr__(self) -> str:
        return f"<Team id={self.id} name={self.name}>"


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_code = db.Column(db.String(255), nullable=False, unique=True, index=True)
    project_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    case_type = db.Column(db.String(255), nullable=False)
    stakeholder = db.Column(db.String(255), nullable=True)
    region = db.Column(db.String(255), nullable=False)
    nps_contact = db.Column(db.String(255), nullable=True)
    sku = db.Column(db.String(255), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), nullable=False, default="Active")
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)

    team = db.relationship("Team", back_populates="projects")

    def __repr__(self) -> str:
        return f"<Project id={self.id} case_code={self.case_code} status={self.status}>"


class CostRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(
        db.Enum(
            TeamMemberLevel,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        unique=True,
    )
    cost_per_day = db.Column(db.Numeric(10, 2), nullable=False)

    def __repr__(self) -> str:
        return f"<CostRate id={self.id} level={self.level} cost_per_day={self.cost_per_day}>"


class BillingRate(db.Model):
    __table_args__ = (
        db.UniqueConstraint("case_type", "region", "cadence", "fte", name="uq_billing_rate_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    case_type = db.Column(db.String(255), nullable=False)
    region = db.Column(db.String(255), nullable=False)
    cadence = db.Column(
        db.Enum(
            BillingCadence,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    fte = db.Column(db.Numeric(4, 1), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<BillingRate id={self.id} case_type={self.case_type} region={self.region} "
            f"cadence={self.cadence} fte={self.fte} amount={self.amount}>"
        )


class StaffingEntry(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "work_date",
            "manager_user_id",
            "team_member_id",
            "project_id",
            "activity_type",
            name="uq_staffing_row",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    manager_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    team_member_id = db.Column(db.Integer, db.ForeignKey("team_member.id"), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True)
    activity_type = db.Column(
        db.Enum(
            ActivityType,
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ActivityType.PROJECT.value,
    )
    hours = db.Column(db.Numeric(4, 1), nullable=False, default=8.0)
    billing_manager_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    charged_fte = db.Column(db.Numeric(4, 2), nullable=False, default=1.0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    manager_user = db.relationship("User", foreign_keys=[manager_user_id], lazy=True)
    billing_manager_user = db.relationship("User", foreign_keys=[billing_manager_user_id], lazy=True)
    team_member = db.relationship("TeamMember", foreign_keys=[team_member_id], lazy=True)
    team = db.relationship("Team", foreign_keys=[team_id], lazy=True)
    project = db.relationship("Project", foreign_keys=[project_id], lazy=True)

    def __repr__(self) -> str:
        return (
            f"<StaffingEntry id={self.id} work_date={self.work_date} "
            f"activity_type={self.activity_type} charged_fte={self.charged_fte}>"
        )
