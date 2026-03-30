# CPCM-OperationalReport

pip install streamlit pandas plotly openpyxl

docker build -t cpcm-operational-report .
docker run -d -p 8502:8502 --name operational cpcm-operational-report
