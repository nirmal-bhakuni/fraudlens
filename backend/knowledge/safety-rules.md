# Safety rules

Two simple rules add checks after the model. The rule high_amount triggers when the amount is $5,000 or more. The rule high_amount_at_night triggers when the amount is $1,000 or more between 22:00 and 03:59. A rule can only move an Approve to a Review. It never lowers a decision and never creates a Decline. These limits are our own assumptions, not facts from the data.