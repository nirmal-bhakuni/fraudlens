# Why the data is not real

The dataset is a public, simulated one, so the patterns the model learned come from the simulator and not from real customers. One example: in the training data, gas_transport payments of $10 to $20 were fraud in 308 of 322 cases (95.7%), which is not realistic. Because of this, an odd score for a normal-looking payment can be a data artifact and not a bug. We checked that the saved model matches the trained model and that single-transaction features match batch features. Results here do not prove real-world accuracy.
