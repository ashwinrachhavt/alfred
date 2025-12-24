
import pandas as pd
from alfred.connectors.firecrawl_connector import FirecrawlClient
from alfred.connectors.web_connector import WebConnector

if __name__ == "__main__":
    data = pd.read_csv("/Users/ashwin/Applications/Master/alfred/data/paraform.csv")
    firecrawl = FirecrawlClient()
    web_connector = WebConnector(
        mode="langsearch",
        ddg_max_results=3
    )
    for index, row in data.iterrows():
        company = row['Company']
        results = web_connector.search(f"{company} company research report")
        print(results)
        break
