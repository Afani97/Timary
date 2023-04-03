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
	make build
	rm -rf staticfiles
	python manage.py collectstatic --no-input
	git restore staticfiles/admin
	git add staticfiles/css staticfiles/staticfiles.json timarytailwind/static/css staticfiles/timary
.PHONY: static

build:
	python manage.py tailwind build
.PHONY: build

test:
	python manage.py test --failfast --exclude-tag=ui
.PHONY: test

test-ui:
	python manage.py test timary.tests.test_e2e --failfast
.PHONY: test-ui

upgrade:
	pip-compile --upgrade
	pip-sync
	playwright install
.PHONY: upgrade

# TO RUN NGROK FOR TESTING: JUST TYPE 'n' in terminal
