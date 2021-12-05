migrate:
	python manage.py makemigrations
	python manage.py migrate
.PHONY: migrate

ks:
	pkill -f runserver qcluster
.PHONY: ks

run-async:
	python manage.py runserver & python manage.py qcluster
.PHONY: run-async

run:
	python manage.py runserver
.PHONY: run

runp:
	python manage.py runserver 0.0.0.0:8000

static:
	python manage.py collectstatic --no-input
.PHONY: static

test:
	python manage.py test --failfast
.PHONY: test
