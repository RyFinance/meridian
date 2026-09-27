"""Alternate-futures lab v2 (Workstream C4): explicit forward-world simulation for the two live
forward-observation candidates, tsy_month_end_v1 and momentum_gold_v1.

research/future_lab/ only resamples observed history, so it cannot create a regime, a decay path,
or a cost shock the sample does not contain. This package builds SIX explicit generative worlds
(W0 null ... W5 cost shock) for each candidate, on top of the same block-bootstrap machinery
(research.future_lab.engines) already used and tested there, and asks a narrower question than
research/future_lab/ does: under each world, how long until forward data can confirm or kill the
candidate, and with what error rates, under a SIMPLE, pre-declared sequential rule?

Every number here is a property of a SIMULATED world, not a forecast. The worlds are built from
the same finite historical sample (2003-2026 for TLT, 2017-2026 for SPMO/GLD); they cannot contain
a regime, shock or structural break absent from that sample, only explicit, hand-specified
alternatives to it (mean shift, decay, volatility scaling, extra cost).
"""
