class GoldenV1Error(RuntimeError):
    """Base error for invalid corpus, candidates, or harness configuration."""


class CorpusError(GoldenV1Error):
    pass


class CaseValidationError(GoldenV1Error):
    pass


class ExpectationValidationError(CaseValidationError):
    """A safely loaded case contains malformed golden expectations."""


class ReplayError(GoldenV1Error):
    pass
