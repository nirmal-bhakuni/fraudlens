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

## Known model behavior (read before trusting scores)
- The model learned patterns of the simulator that made the data. For example, small
  gas_transport payments ($10-20) are fraud 95.7% of the time in the training file
  (308 of 322 rows). Real life is not like that.
- Scores jump sharply between nearby amounts (tree model).
- Fraud rate dropped from 0.58% (train) to 0.39% (test), so precision on test is lower than on validation.
- About 22% of fraud in the test set is still approved (479 of 2,145).
- Results do NOT prove real-world accuracy.   
## Ask why (RAG)
- `POST /transactions/{id}/explain` searches the knowledge documents (pgvector), then asks an LLM to explain.
- The ML model and rules decide. The LLM only explains. A test checks the transaction is unchanged.
- If no passage is relevant (similarity below 0.30), the API answers "I don't have enough information"
  and does not call the LLM. The 0.30 cutoff is a first guess, tuned later with the evaluation set.
- `sources` are the passages given to the model. The answer may use only some of them.
- Provider: Gemini REST `generateContent` (Google's docs call it "legacy"), model `gemini-3-flash-preview`.
  Preview models can be retired, so the model name is a setting.
- Safety around the LLM: retry on 503, a fallback model, thinking limited, and a cut-off answer is an
  error, never shown as complete. The merchant name is never sent to the LLM.
- Not done yet: explanations are not cached, and free-tier limits apply.
- Dataset license: see the Kaggle page (write the exact text here).
