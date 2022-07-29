lint:
	python -m isort .
	python -m black .
	python -m pylama .
	python -m pydocstyle .
	#python -m mypy --strict --no-warn-return-any pan_deduper/
clean:
	rm duplicates-*
	rm settings.py
	rm deduper.log
