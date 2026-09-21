CORPUS: list[dict] = [
    {
        "title": "Shipping Policy",
        "content": (
            "We process and ship orders within 2 business days of purchase.\n\n"
            "Standard shipping takes 5–7 business days. Express shipping (2 business days) "
            "is available at checkout for an additional fee.\n\n"
            "Orders over $50 qualify for free standard shipping automatically."
        ),
    },
    {
        "title": "Return and Refund Policy",
        "content": (
            "We accept returns within 30 days of delivery. Items must be unused and in "
            "original packaging.\n\n"
            "To start a return, contact support with your order ID. We will email a prepaid "
            "return label within 1 business day.\n\n"
            "Refunds are issued to the original payment method within 5–10 business days of "
            "receiving the returned item."
        ),
    },
    {
        "title": "Account and Login Issues",
        "content": (
            "If you cannot log in, first try resetting your password via the 'Forgot password' "
            "link on the login page.\n\n"
            "If your account has been locked after multiple failed login attempts, it will "
            "unlock automatically after 30 minutes. Contact support if you need immediate access.\n\n"
            "Two-factor authentication (2FA) codes expire after 60 seconds. If your code is "
            "rejected, check that your device clock is synced."
        ),
    },
    {
        "title": "Payment Failures",
        "content": (
            "A declined payment usually means the card details entered do not match your "
            "bank's records. Double-check the card number, expiry date, and billing address.\n\n"
            "Some banks block first-time transactions with new merchants. Contact your bank to "
            "authorize the charge, then retry.\n\n"
            "If a charge appears on your statement but your order shows as failed, the hold "
            "will be released automatically within 3–5 business days."
        ),
    },
    {
        "title": "Order Tracking",
        "content": (
            "Once your order ships you will receive a confirmation email with a tracking number.\n\n"
            "Tracking updates can take up to 24 hours to appear after the carrier scans the package.\n\n"
            "If your tracking number shows no movement for more than 5 business days, contact "
            "support with your order ID and we will open an investigation."
        ),
    },
]


def chunk_document(document: dict) -> list[dict]:
    """Split a document into paragraph-level chunks.

    Paragraph boundaries (double newlines) are used rather than fixed token
    counts so each chunk preserves semantic coherence — a sentence split
    mid-chunk loses the context needed for accurate retrieval.
    """
    paragraphs = document["content"].split("\n\n")
    return [
        {"text": paragraph.strip(), "source": document["title"]}
        for paragraph in paragraphs
        if paragraph.strip()
    ]
