lint:
	isort .
	black .
clean:
	rm duplicates-*
	rm settings.py
