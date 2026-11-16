# Day 8 Block 4: GitHub Actions CI

## Objective

Provide reproducible remote CI evidence for the current Block 3 implementation.

## Acceptance criteria

- CI runs on Python 3.11 and 3.13.
- The existing `unittest` suite runs in CI.
- The project is also exercised through `pytest`.
- CLI smoke checks execute successfully.
- No application credentials or external runtime services are required.
- The workflow is triggered for pushes and pull requests.

## Evidence

The final checkpoint should record the GitHub Actions workflow URL/run and its actual result after the commit is pushed.

## Important scope note

This Block 4 update is intentionally limited to CI. It does not apply the older `block4-update/block4.patch`, because that prepared patch targets a different historical base commit and represents an automated-testing checkpoint rather than the current assessment's GitHub Actions CI block.
