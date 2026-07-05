# Transaction PDF Pipeline

## Philosophy

The goal of this project is first of all to be a place to practice and learn how to use technologies. This means some things may be designed poorly, which is fine as the point is to go through the exercise, not reach the end goal as quickly as possible (thus development on this may go very slowly). As well, some things may be solved in a roundabout convoluted way or be overkill - again the main goal is to create scenarios to practice skills, not maximize efficiency.

With that said, let's get onto the project.

## Purpose

This main problem this project intends to solve is how to extract a transaction history from credit card/bank statements and use it to understand past spending patterns.

We assume that for closed accounts or historical data, past PDFs are easier to access and store. In many cases, financial institutions may not provide export functionality and may only display history in a paginated way - thus downloading twelve PDFs per year is easier than scraping a website.

## Technologies Used

- Python
- ETL methodologies (staging, transformation, enrichment as separate phases)

## Future

Building on the idea of ETL, this could be coordinated through Airflow or dbt.
data quality monitoring
package into a docker container to run more easily, as a self-hosted app (parameters through volume mounts and env files)
UI for easier tagging management
reducing logic into state machines
have a good input yaml format for state machines
test code coverage
swap to uv
