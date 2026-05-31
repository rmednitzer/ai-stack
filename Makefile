# ai-stack Makefile — common chart operations
.PHONY: help lint lint-prod template template-prod check-links pydanticai-lock test clean

help:
	@echo "ai-stack Helm chart targets:"
	@echo "  make lint           Run helm lint (lab profile)"
	@echo "  make lint-prod      Run helm lint (prod profile)"
	@echo "  make template       Render templates (lab profile)"
	@echo "  make template-prod  Render templates (prod profile)"
	@echo "  make check-links    Validate markdown links and anchors"
	@echo "  make pydanticai-lock  Recompile the hashed Pydantic AI requirements lock (needs uv)"
	@echo "  make test           Run helm lint + template smoke test"
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

pydanticai-lock:
	uv pip compile files/pydanticai/requirements.in --universal --generate-hashes \
		--python-version 3.13 -o files/pydanticai/requirements.txt

test:
	helm lint . && helm template ai-stack . --debug > /dev/null && echo "smoke test passed"

clean:
	rm -rf output rendered *.tgz zarf-package-*.tar.zst
