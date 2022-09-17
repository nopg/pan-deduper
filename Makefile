lint:
	python -m isort .
	python -m black .
	python -m pylama .
	python -m pydocstyle .
	#python -m mypy --strict --no-warn-return-any pan_deduper/

clean:
	rm -f duplicates-*.json
	rm -f settings.py
	rm -f deduper.log
	rm -f deep-dupes-*.json
	rm -f set-commands-*.txt

test:
	python -m pytest .
