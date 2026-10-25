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
## Dashboard (React + Vite)
- Run: `cd frontend; npm install; npm run dev`, then open http://localhost:5173 (API must be running).
- Demo data: `python scripts\seed_demo.py` loads 50 rows from the TEST file (20 fraud, 30 normal).
  This sample over-represents fraud, so its numbers are not accuracy numbers.
- The dev server proxies /api to the backend, so no CORS setup is needed.
- Security note: the API key is kept in sessionStorage (readable by any script on the page).
  A production app would use cookie sessions. The AI's text is shown as plain text, never as HTML.
- Not done yet: charts, frontend tests, URL routing.
## Run everything with Docker
- `docker compose up -d --build` starts the database, the API (http://localhost:8000) and the dashboard (http://localhost:8080).
- Put `GEMINI_API_KEY` in `backend/.env` first. The key is never baked into an image.
- Demo data: `python scripts\seed_demo.py`.
- The embedding model is downloaded while building the image. The API container runs as a non-root user.
- Known limits: the knowledge documents are re-loaded on every API start; the dev database password is in docker-compose.yml.

## Evaluation (retrieval)
- `python -m app.rag.evaluate` scores retrieval on 45 questions (37 answerable, 8 that should be refused).
  No LLM is called. The knowledge base has 19 documents, each stored as one chunk.
- Split: "dev" questions choose the similarity cutoff, "test" questions check it afterwards.
- Settings: cutoff 0.30, top-k 4. The cutoff is a plateau, not a clear peak: dev scores the same from 0.30 to 0.35
  and falls to 69.6% at 0.40.
- Results at cutoff 0.30: overall 88.9% (40/45). Answerable 91.9% (34/37). Off-topic questions refused
  correctly 75% (6/8). Right document first 81.1%, MRR 0.88. Dev 87.0% (20/23), test 90.9% (20/22).
- Known failures: a document that mixes several topics is retrieved poorly (q33), one correct match scored
  just below the cutoff (q36), and off-topic questions that share words with our documents can pass the cutoff
  (u03, u08). The prompt tells the model to say "I don't have enough information" in that case.
- Limits: the questions and documents were written by the same person from the same facts, so the score is
  optimistic. About 22 questions per split, so one question moves a score by ~4.5 points. It does not check
  whether the AI's wording is correct, and it does not cover the default "Explain this decision" query.