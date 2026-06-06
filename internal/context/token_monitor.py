class TokenMonitor:
    """Lightweight token monitor placeholder.

    This uses whitespace splitting as a cheap estimate until a tokenizer is wired in.
    """

    def __init__(self) -> None:
        self.last_estimate = 0

    def observe(self, text: str) -> int:
        self.last_estimate = len(text.split())
        return self.last_estimate
