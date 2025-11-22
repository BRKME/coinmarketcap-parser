name: Run CMC Parser

on:
  schedule:
    - cron: '0 */6 * * *'  # Каждые 6 часов
  workflow_dispatch:  # Ручной запуск

jobs:
  run-parser:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install playwright beautifulsoup4 gspread oauth2client requests
        playwright install chromium
        playwright install-deps
    
    - name: Run parser
      env:
        MAX_QUESTIONS: 8
        MAX_RETRIES: 2
      run: |
        python parser.py
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: parser-results
        path: |
          cmc_full_data.json
          cmc_questions_answers.csv
          full_report.txt
        if-no-files-found: ignore
