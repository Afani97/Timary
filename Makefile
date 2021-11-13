migrate:
	python manage.py makemigrations
	python manage.py migrate
.PHONY: migrate

ks:
	pkill -f runserver qcluster
.PHONY: ks

run:
	make migrate
	python manage.py runserver & python manage.py qcluster
.PHONY: run


test:
	python manage.py test --failfast
.PHONY: test
