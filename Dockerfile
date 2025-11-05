FROM python:3.11-slim

ENV HOME=/code \
    HUGGINGFACE_HUB_CACHE=/code/.cache/huggingface \
    TRANSFORMERS_CACHE=/code/.cache/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /code

RUN mkdir -p /code/.cache/huggingface && chmod -R 777 /code/.cache

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app/cache_model.py /code/cache_model.py
RUN python /code/cache_model.py

COPY ./setup.py /code/setup.py
RUN pip install -e .

COPY ./app /code/app
COPY ./prompts /code/prompts
COPY ./scripts /code/scripts
RUN chmod +x /code/scripts/entrypoint.sh
ENTRYPOINT ["/code/scripts/entrypoint.sh"]
# The command executed by the entrypoint. Defaults to running the hybrid runtime.
CMD ["python", "/code/app/main.py"]
