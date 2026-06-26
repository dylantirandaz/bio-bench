.PHONY: test

test:
	python3 -m unittest discover -s tests

brab-smoke:
	python3 scripts/brab_validate.py --tasks data/benchmarks/BioResearchAgentBench-v0/tasks.jsonl --sources data/benchmarks/BioResearchAgentBench-v0/sources.json --taxonomy data/benchmarks/BioResearchAgentBench-v0/failure_taxonomy.json
	python3 scripts/brab_export_prompts.py --tasks data/benchmarks/BioResearchAgentBench-v0/tasks.jsonl --out runs/brab-smoke/prompts.jsonl
	python3 scripts/brab_baseline.py --tasks data/benchmarks/BioResearchAgentBench-v0/tasks.jsonl --out runs/brab-smoke/baseline_outputs.jsonl
	python3 scripts/brab_score.py --tasks data/benchmarks/BioResearchAgentBench-v0/tasks.jsonl --outputs runs/brab-smoke/baseline_outputs.jsonl --out-dir runs/brab-smoke
