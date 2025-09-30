FROM python:3.11-slim

RUN apt-get update 
RUN apt-get install -y --no-install-recommends cron 
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app/cache_model.py /code/cache_model.py
RUN python /code/cache_model.py

COPY ./setup.py /code/setup.py
RUN pip install -e .

COPY ./app /code/app
COPY ./prompts /code/prompts

COPY ./ai-agent-cron /etc/cron.d/ai-agent-cron
RUN chmod 0644 /etc/cron.d/ai-agent-cron

COPY ./entrypoint.sh /code/entrypoint.sh
RUN chmod +x /code/entrypoint.sh
ENTRYPOINT ["/code/entrypoint.sh"]

# The command to run when the container starts (passed to the entrypoint)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
