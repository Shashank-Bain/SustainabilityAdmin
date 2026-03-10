import sys
from decimal import Decimal
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.extensions import db
from app.models import BillingCadence, BillingRate, CostRate, TeamMemberLevel, User, UserRole


def seed_admin_user() -> int:
    admin_email = "admin@example.com"
    admin_user = User.query.filter_by(email=admin_email).first()
    if admin_user is None:
        admin_user = User(
            name="Admin User",
            email=admin_email,
            role=UserRole.ADMIN.value,
            active=True,
        )
        admin_user.set_password("change-me")
        db.session.add(admin_user)
        return 1

    return 0


def seed_cost_rates() -> int:
    cost_rate_mapping = {
        TeamMemberLevel.ANALYST1.value: 220,
        TeamMemberLevel.ANALYST2.value: 250,
        TeamMemberLevel.ASSOCIATE1.value: 350,
        TeamMemberLevel.ASSOCIATE2.value: 400,
        TeamMemberLevel.ASSOCIATE3.value: 400,
        TeamMemberLevel.PROJECT_LEADER1.value: 550,
        TeamMemberLevel.PROJECT_LEADER2.value: 550,
        TeamMemberLevel.PROJECT_LEADER3.value: 550,
        TeamMemberLevel.MANAGER1.value: 800,
        TeamMemberLevel.MANAGER2.value: 800,
        TeamMemberLevel.MANAGER3.value: 800,
        TeamMemberLevel.SENIOR_MANAGER1.value: 1000,
        TeamMemberLevel.SENIOR_MANAGER2.value: 1000,
        TeamMemberLevel.SENIOR_MANAGER3.value: 1000,
        TeamMemberLevel.DIRECTOR.value: 1600,
        TeamMemberLevel.SENIOR_DIRECTOR.value: 2300,
        TeamMemberLevel.VP.value: 2600,
    }

    inserted = 0

    for level, amount in cost_rate_mapping.items():
        existing = CostRate.query.filter_by(level=level).first()
        if existing is None:
            db.session.add(CostRate(level=level, cost_per_day=Decimal(str(amount))))
            inserted += 1

    return inserted


def seed_billing_rates() -> int:
    case_type = "Client billed"
    billing_rates = {
        "AMER": {
            BillingCadence.WEEKLY.value: {"4.5": 19000, "3.5": 14800, "2.5": 10500, "1": 4200},
            BillingCadence.DAILY.value: {"4.5": 3800, "3.5": 2960, "2.5": 2100, "1": 840},
        },
        "EMEA": {
            BillingCadence.WEEKLY.value: {"4.5": 17500, "3.5": 13600, "2.5": 9700, "1": 3900},
            BillingCadence.DAILY.value: {"4.5": 3500, "3.5": 2720, "2.5": 1940, "1": 780},
        },
        "APAC": {
            BillingCadence.WEEKLY.value: {"4.5": 16500, "3.5": 12800, "2.5": 9200, "1": 3700},
            BillingCadence.DAILY.value: {"4.5": 3300, "3.5": 2560, "2.5": 1840, "1": 740},
        },
    }

    inserted = 0

    for region, cadence_values in billing_rates.items():
        for cadence, fte_values in cadence_values.items():
            for fte, amount in fte_values.items():
                fte_decimal = Decimal(fte)
                existing = BillingRate.query.filter_by(
                    case_type=case_type,
                    region=region,
                    cadence=cadence,
                    fte=fte_decimal,
                ).first()
                if existing is None:
                    db.session.add(
                        BillingRate(
                            case_type=case_type,
                            region=region,
                            cadence=cadence,
                            fte=fte_decimal,
                            amount=Decimal(str(amount)),
                        )
                    )
                    inserted += 1

    return inserted


def main() -> None:
    app = create_app()
    with app.app_context():
        users_inserted = seed_admin_user()
        cost_rates_inserted = seed_cost_rates()
        billing_rates_inserted = seed_billing_rates()
        db.session.commit()
        print(
            "Seed completed. "
            f"Inserted: users={users_inserted}, "
            f"cost_rates={cost_rates_inserted}, "
            f"billing_rates={billing_rates_inserted}"
        )


if __name__ == "__main__":
    main()