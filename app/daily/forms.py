from flask_wtf import FlaskForm
from wtforms import DateField
from wtforms.validators import DataRequired


class DailyDateForm(FlaskForm):
    work_date = DateField("Date", validators=[DataRequired()], format="%Y-%m-%d")
