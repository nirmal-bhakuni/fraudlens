# FraudLens

Explainable payment fraud checks: an ML model scores each transaction,
simple rules add safety checks, SHAP gives the top reasons, and a RAG
feature explains the reasons in plain English with sources.

Design rule: the ML model decides. The LLM only explains.

## Status
Day 1: project setup and data inspection.

## Data (important)
- Dataset: "Credit Card Transactions Fraud Detection Dataset" (Sparkov) by kartik2112 on Kaggle.
- License: <WRITE WHAT THE KAGGLE PAGE SAYS>
- The data is public and simulated. Results here do NOT prove real-world accuracy.
- The data files are NOT in this repo.

### Download steps
1. Make a free Kaggle account and open the dataset page.
2. Click Download. You get a zip file.
3. Unzip it so these files are in `data/raw/`:
   - `fraudTrain.csv`
   - `fraudTest.csv`