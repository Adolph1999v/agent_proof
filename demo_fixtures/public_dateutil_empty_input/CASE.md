# Public dateutil empty-input reproduction

This dependency-free behavioral reproduction is derived from python-dateutil issue #78. The parser
handles ISO dates, outer whitespace, invalid formats, and date formatting. The requested change is
only for blank input to raise `ValueError`; every valid non-empty behavior must stay unchanged.
