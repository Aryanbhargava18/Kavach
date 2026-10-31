PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: install demo test eval lan clean llm-check sarvam-check cognee-load paytm-check

install:
	test -x $(BIN)/python || $(PY) -m venv $(VENV)
	$(BIN)/pip install -q -r requirements.txt
	@command -v tesseract >/dev/null || echo "\n>> Install OCR for screenshot reading:  brew install tesseract  (macOS)  |  sudo apt install tesseract-ocr  (Linux)\n"

demo: install
	$(BIN)/python -m uvicorn app.main:app --port 8000

# Same, reachable from a phone on the venue Wi-Fi (QR codes in packs will point here)
lan: install
	$(BIN)/python run.py

test: install
	KAVACH_PLANNER=offline $(BIN)/python -m pytest -q

eval: install
	$(BIN)/python -m eval.generate && KAVACH_PLANNER=offline $(BIN)/python -m eval.run
	$(BIN)/python -m eval.freeze_gen && KAVACH_PLANNER=offline $(BIN)/python -m eval.freeze_run

clean:
	rm -rf instance/packs

llm-check: install
	$(BIN)/python -m app.llm_smoke

sarvam-check: install
	$(BIN)/python -m app.sarvam_check

cognee-load: install
	$(BIN)/python -m app.cognee_load

paytm-check: install
	$(BIN)/python -m app.paytm_check $(ORDER)
