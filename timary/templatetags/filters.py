import datetime

from django import template

register = template.Library()


@register.filter(name="addclass")
def addclass(field, class_attr):
    return field.as_widget(attrs={"class": class_attr})


@register.filter(name="nextmonday")
def nextmonday(field):
    weekday = 0
    today = datetime.datetime.today()
    day_shift = (weekday - today.weekday()) % 7
    next_date = (today + datetime.timedelta(days=day_shift)).date()
    return next_date if next_date != today.date() else "today"
