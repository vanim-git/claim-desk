"""Every policy number, with its page reference (CO-POL-014 v4.2, data-pack doc 02)."""

NE_WINDOW_DAYS = 90            # §5.2 p3: near-expiry claims accepted from 90 days before expiry
EXPIRED_WINDOW_DAYS = 90       # §5.2 p3: expired claims accepted up to 90 days after expiry
TRANSIT_WINDOW_DAYS = 7        # §5.2 p3: breakage and short supply within 7 days of invoice
VALUE_TOLERANCE_INR = 1        # §5.7 p4: claim value = qty x PTS
STATED_EXPIRY_TOLERANCE_DAYS = 31   # §5.3 p3: the expiry in an email must match the batch master

# Neha Bansal (FDE Academy, 20 Nov): a person decides and may reject; the tool still RECOMMENDS reject and cites the clause.
# "reject" = recommend Reject (default now). "person" = recommend Needs a person (the earlier Q&A #58 reading).
EARLY_NE_ACTION = "reject"
QTY_OVER_ACTION = "reject"

MAX_MODEL_CALLS = 3            # one parse, one retry, one explain

CLAUSES = {
    "D0": "§5.6 p4 (same line twice in one email)",
    "R1": "§5.5 p3, §8.3 p4",
    "R2": "§5.3 p3, §5.4 p3",
    "R3": "§5.2 p3",
    "R4": "§5.5 p3",
    "R5": "§5.6 p4",
    "R6": "§5.1 p3",
    "R7": "§5.7 p4",
    "R8": "§5.3 p3",
}
POLICY = "CO-POL-014 v4.2"
