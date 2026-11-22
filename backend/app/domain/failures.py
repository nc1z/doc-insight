class StepFailure(Exception):
    """A pipeline step failed. Permanent failures are not retried."""

    def __init__(self, code: str, *, permanent: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.permanent = permanent
