SHELL := /bin/bash

CHART_NAME ?= ai-stack
CHART_DIR ?= .
PROD_VALUES ?= values-prod.yaml

.PHONY: help lint lint-prod template template-prod ct-lint

help:
	@echo "Targets:"
	@echo "  lint        - helm lint with default values"
	@echo "  lint-prod   - helm lint with production overlay"
	@echo "  template    - render chart with default values"
	@echo "  template-prod - render chart with production overlay"
	@echo "  ct-lint     - run chart-testing lint"

lint:
	helm lint $(CHART_DIR)

lint-prod:
	helm lint $(CHART_DIR) -f values.yaml -f $(PROD_VALUES)

template:
	helm template $(CHART_NAME) $(CHART_DIR) --debug

template-prod:
	helm template $(CHART_NAME) $(CHART_DIR) -f values.yaml -f $(PROD_VALUES) --debug

ct-lint:
	ct lint --config ct.yaml --charts $(CHART_DIR)
