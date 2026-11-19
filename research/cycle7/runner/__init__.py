"""research.cycle7.runner -- cycle-7 new-sample runner around the FROZEN cycle-6 engine (FRAMEWORK §1, §4-§6).

  python -m research.cycle7.runner.run_sample --sample research/cycle7/samples/<SPEC>__<SAMPLE>.md \
      --out reports/cycle7_new_samples/runs/<SPEC>__<SAMPLE>/
  python -m research.cycle7.runner.pool --runs-root reports/cycle7_new_samples/runs \
      --out reports/cycle7_new_samples/pooled.json

The engine (research/cycle6/engine) is imported, never edited; its hash is verified before every run.
"""
