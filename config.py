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

# ---- P3: short-dated stock at the C&Fs (Hooghly ships newest first) -------------------------------
RSL_FLOOR = 0.60               # §7.1: no dispatch to a stockist below 60% remaining shelf life (a breach; flagged, not blocked)
RSL_WARN = 0.70                # Kavita Rao (20 Nov): weekly early warning at 70% RSL
BUFFER_MONTHS = 2.0            # Kavita Rao: 2 months of cover stays at the C&F; stock above that is a candidate for return
DAYS_PER_MONTH = 30.44         # shelf life is stated in months; same conversion as the analysis
BLOCK_BELOW_FLOOR = False      # Kavita: flag every dispatch below 60% but do not block; below 60% goes out only if the stockist agrees
CDC = "Bhiwandi"               # return stock goes to the central depot and is reallocated, never destroyed
# Regional Distribution Manager per C&F. Only Hooghly is named in the answers (Subhajit = Kolkata); the rest are unassigned.
RDM = {"CF-E01": "Subhajit Banerjee"}
PICKLIST_TO = {"CF-E01": {"to": "Pradip Ghosh", "cc": "Subhajit Banerjee", "confirm_within_days": 2}}   # Hooghly answer, 20 Nov

# ---- P2: quarter-end schemes -----------------------------------------------------------------------
SCHEME_MOQ_MULT = 1.5          # Annex B p6: minimum order = 1.5 x avg monthly purchase of that SKU over the previous 3 months
                               # Arjun Sethi (20 Nov): paid packs only (free packs out), 3 months before the scheme
SCHEME_LOOKBACK_MONTHS = 3
STOCK_NORM_MONTHS = 2.5        # §4.5 p3: no scheme on an SKU where the stockist's closing stock exceeds 2.5 months of average secondary
FOC_CAP = 0.03                 # §4.4 p2: free goods at PTS <= 3% of the quarter's primary sales (CFO approval above that)
SCHEME_BLOCKS = False          # Arjun: warn the RSM, do not block; the scheme desk decides
SCHEME_CLAIM_TYPES = ("Near expiry", "Expired")
CLAIM_STATUS_COUNTED = ("Credited", "Pending")

# ---- P1: unfilled orders and allocation --------------------------------------------------------------
SCHEME_WINDOW_FROM_DAY = 22    # §4.2 / Annex B: circulars run from the 22nd of the quarter's last month to its last day
SCHEME_MONTHS = (3, 6, 9, 12)
SPARE_BUFFER_MONTHS = 2.0      # Kavita Rao (20 Nov): 2 months of cover stays at the C&F; above that is spare (candidate for return to the CDC)
ALLOC_LOOKBACK_MONTHS = 6      # Kavita / Vaishali (20 Nov): new shares on ordered packs incl. free, repeats once, last six months
ALLOC_SPIKE_CAP = 1.5          # my assumption: smooth scheme spikes by capping a month at 1.5 x the six-month median (to confirm with Vaishali)
ALLOC_REVIEW = "quarterly"     # Kavita (20 Nov): review quarterly, not monthly
BASE_SHARE_FY = "FY25"         # Vaishali (20 Nov): the shares in use are the FY25 ones, unchanged
TRANSFER_DAYS = "10-14"        # Kavita: approval is same-day; the physical move takes 10-14 days; no direct C&F-to-C&F
