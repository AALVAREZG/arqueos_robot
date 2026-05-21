"""
Contable-document capture (inverted architecture, spec v2).

The consumer no longer fetches/merges/prints/stages. It only captures the
SICAL contable document to a PDF and returns it to sical-robot in the
result message. Public entry point: ``capture_and_return.capture_and_return``.

``sical_capture`` drives the live SICAL UI and stays UNVERIFIED until a
dry-run on the real SICAL build (rollout flag stays OFF until then).
"""
