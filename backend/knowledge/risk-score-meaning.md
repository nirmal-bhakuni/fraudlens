# What the risk score means

The risk score is a number from 0 to 1 produced by the XGBoost model. A higher score means the transaction looks more like the fraud examples the model saw in training. It is a ranking signal, not a calibrated probability: a score of 0.80 does not mean an 80% chance of fraud. We did not calibrate the scores, and the fraud rate changed between the training and test periods. Compare scores with each other and with the thresholds, and do not read them as percentages. Scores can jump sharply between nearby amounts, because the model is made of decision trees.
