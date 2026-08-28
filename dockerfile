FROM python:3.14-trixie

WORKDIR /app

RUN python -m venv /opt/venv

ENV VIRTURAL_ENV=/opt/env 
ENV PATH="$VIRTURAL_ENV/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN pip install -e .

CMD [ "/bin/bash" ]
