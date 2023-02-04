import datetime

from django import template
from django.template.defaultfilters import date as template_date
from django.utils import timezone
from django.utils.dateparse import parse_datetime

register = template.Library()


@register.filter(name="addclass")
def addclass(field, class_attr):
    return field.as_widget(attrs={"class": class_attr})


@register.filter(name="nextmonday")
def nextmonday(field, today_str):
    weekday = 0
    today = parse_datetime(today_str)
    day_shift = (weekday - today.weekday()) % 7
    next_date = (today + timezone.timedelta(days=day_shift)).date()
    return template_date(next_date, "M. j, Y") if next_date != today.date() else "today"


@register.filter(name="addf")
def addfloats(val, arg):
    return float(val) + float(arg)


@register.filter(name="adddays")
def adddays(value, days):
    return datetime.date.fromisoformat(value) + datetime.timedelta(days=int(days))


@register.filter(name="python_any")
def python_any(values):
    return any(values)
