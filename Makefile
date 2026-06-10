# ai-stack Makefile — common chart operations
.PHONY: help lint lint-prod template template-prod check-links unittest pydanticai-lock ingestion-worker-lock test clean

help:
	@echo "ai-stack Helm chart targets:"
	@echo "  make lint           Run helm lint (lab profile)"
	@echo "  make lint-prod      Run helm lint (prod profile)"
	@echo "  make template       Render templates (lab profile)"
	@echo "  make template-prod  Render templates (prod profile)"
	@echo "  make check-links    Validate markdown links and anchors"
	@echo "  make unittest       Run helm-unittest suites (needs the helm unittest plugin)"
	@echo "  make pydanticai-lock  Recompile the hashed Pydantic AI requirements lock (needs uv)"
	@echo "  make ingestion-worker-lock  Recompile the hashed ingestion-worker requirements lock (needs uv)"
	@echo "  make test           Run helm lint + template smoke test + unit tests"
	@echo "  make clean          Remove rendered output and packaging artifacts"

lint:
	helm lint .

lint-prod:
	helm lint . -f values.yaml -f values-prod.yaml

template:
	helm template ai-stack . --debug > /dev/null && echo "lab template OK"

template-prod:
	helm template ai-stack . -f values.yaml -f values-prod.yaml --debug > /dev/null && echo "prod template OK"

check-links:
	python3 .github/scripts/check_md_links.py

unittest:
	helm unittest .

pydanticai-lock:
	uv pip compile files/pydanticai/requirements.in --universal --generate-hashes \
		--python-version 3.13 --output-file files/pydanticai/requirements.txt

ingestion-worker-lock:
	uv pip compile files/ingestion-worker/requirements.in --universal --generate-hashes \
		--python-version 3.14 --output-file files/ingestion-worker/requirements.txt

test:
	helm lint . && helm template ai-stack . --debug > /dev/null && helm unittest . && echo "smoke test + unit tests passed"

clean:
	rm -rf output rendered *.tgz zarf-package-*.tar.zst
