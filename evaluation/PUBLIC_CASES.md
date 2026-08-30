# Public-case provenance

The recorded evaluation contains one explicitly marked public-bug-derived case alongside the ten
controlled cases.

## `public-dateutil-empty-input`

- Source project: [python-dateutil](https://github.com/dateutil/dateutil)
- Public report: [dateutil issue #78](https://github.com/dateutil/dateutil/issues/78)
- Upstream fix reference: [dateutil NEWS](https://github.com/dateutil/dateutil/blob/master/NEWS)
- Reported behavior: parsing an empty string returned the supplied default date rather than
  rejecting the empty input. The upstream release notes state that the fix made empty input raise
  `ValueError`.
- Evaluation form: a dependency-free behavioral reproduction with original code written for this
  benchmark. It preserves the reported before/after contract but does not copy upstream source.

This distinction is intentional: the case contributes authentic provenance without adding network
access, unpinned dependencies, or a large third-party checkout to the judge's reproduction path.
