# What Approve, Review and Decline mean

Approve means the system found nothing worrying: the risk score is below the review threshold and no safety rule triggered. Review means the transaction is flagged for a closer look, either because the model score is in the middle band or because a safety rule moved an Approve up to Review. Decline means the model score reached the decline threshold. Only the model can produce a Decline, and rules never do. Review and Decline are both counted as flagged, and they show up when you filter the dashboard by flagged.
